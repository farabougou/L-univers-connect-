"""Normalized Performance : assemble Energy Aggregation et Weather Context
selon une référence énergétique (Baseline) déjà activée, calcule un résultat
et le persiste tel quel dans `energy_normalized_results` — jamais réécrit,
jamais recalculé en silence (même principe que les constats et le journal
d'audit). Chaque colonne du résultat existe pour pouvoir expliquer, des
années plus tard, comment ce chiffre a été obtenu : source des mesures,
donnée météo utilisée, méthode et version, paramètres, données manquantes.
"""

import json
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config_versions import get_version
from app.energy.aggregation import aggregate_energy_consumption
from app.energy.baseline import ENERGY_BASELINE
from app.energy.methods import get_method
from app.energy.weather import aggregate_degree_days
from app.errors import DomainError
from app.points import get_point

_COLUMNS = (
    "id, tenant_id, functional_location_id, point_id, baseline_config_version_id, "
    "period_start, period_end, method, method_version, parameters, raw_consumption, "
    "raw_consumption_unit, measurement_count, data_completeness, quality_flags, "
    "degree_days, degree_day_base_temperature_celsius, degree_day_kind, weather_source, "
    "weather_days_missing, normalization_status, normalized_consumption, evidence, "
    "computed_at, computed_by, created_at"
)


class EnergyBaselineNotFound(DomainError, LookupError):
    status = 404


def get_normalized_result(connection: Connection, result_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM energy_normalized_results WHERE id = :id"),
            {"id": result_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_normalized_results(
    connection: Connection, *, functional_location_id: uuid.UUID
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(
                f"SELECT {_COLUMNS} FROM energy_normalized_results "
                "WHERE functional_location_id = :id ORDER BY period_start DESC"
            ),
            {"id": functional_location_id},
        ).mappings()
    ]


def _site_id_for_functional_location(
    connection: Connection, functional_location_id: uuid.UUID
) -> uuid.UUID:
    return connection.execute(
        text("SELECT site_id FROM functional_locations WHERE id = :id"),
        {"id": functional_location_id},
    ).scalar_one()


def compute_normalized_performance(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    baseline_config_version_id: uuid.UUID,
    period_start: date,
    period_end: date,
    computed_by: str,
    at: datetime,
) -> dict[str, Any]:
    """Calcule et persiste un résultat de performance normalisée pour la
    période analysée, selon les paramètres figés d'une référence énergétique
    déjà activée. Les degrés-jours de la période de référence sont
    recalculés ici à chaque appel à partir des observations météo (jamais
    mis en cache) : une correction ultérieure d'une observation se répercute
    ainsi sur tout nouveau calcul, sans jamais toucher un résultat déjà
    persisté."""
    version = get_version(connection, baseline_config_version_id)
    if version is None or version["config_type"] != ENERGY_BASELINE:
        raise EnergyBaselineNotFound("ENERGY_BASELINE_NOT_FOUND")
    content = version["content"]

    point = get_point(connection, uuid.UUID(content["point_id"]))
    site_id = _site_id_for_functional_location(connection, point["functional_location_id"])

    consumption = aggregate_energy_consumption(
        connection, point=point, period_start=period_start, period_end=period_end
    )

    base_temperature = content["degree_day_base_temperature_celsius"]
    degree_day_kind = content["degree_day_kind"]
    reference_period = content["reference_period"]
    reference_start = date.fromisoformat(reference_period["start"])
    reference_end = date.fromisoformat(reference_period["end"])

    degree_days_analyzed = aggregate_degree_days(
        connection,
        site_id=site_id,
        period_start=period_start,
        period_end=period_end,
        base_temperature_celsius=base_temperature,
        kind=degree_day_kind,
    )
    degree_days_reference = aggregate_degree_days(
        connection,
        site_id=site_id,
        period_start=reference_start,
        period_end=reference_end,
        base_temperature_celsius=base_temperature,
        kind=degree_day_kind,
    )

    normalized_consumption: float | None = None
    if degree_days_analyzed["degree_days"] is None or degree_days_reference["degree_days"] is None:
        normalization_status = "no_weather_data"
    else:
        method = get_method(content["method"], content["method_version"])
        normalized_consumption = method(
            raw_consumption=consumption["raw_consumption"],
            degree_days_analyzed=degree_days_analyzed["degree_days"],
            degree_days_reference=degree_days_reference["degree_days"],
        )
        normalization_status = "ok" if normalized_consumption is not None else "zero_degree_days"

    result_id = uuid.uuid4()
    evidence = {
        **consumption["evidence"],
        "reference_period_degree_days": degree_days_reference,
    }
    connection.execute(
        text(
            "INSERT INTO energy_normalized_results ("
            "id, tenant_id, functional_location_id, point_id, baseline_config_version_id, "
            "period_start, period_end, method, method_version, parameters, raw_consumption, "
            "raw_consumption_unit, measurement_count, data_completeness, quality_flags, "
            "degree_days, degree_day_base_temperature_celsius, degree_day_kind, "
            "weather_source, weather_days_missing, normalization_status, "
            "normalized_consumption, evidence, computed_at, computed_by"
            ") VALUES ("
            ":id, :tenant_id, :functional_location_id, :point_id, :baseline_config_version_id, "
            ":period_start, :period_end, :method, :method_version, "
            "CAST(:parameters AS JSONB), :raw_consumption, :raw_consumption_unit, "
            ":measurement_count, :data_completeness, CAST(:quality_flags AS JSONB), "
            ":degree_days, :degree_day_base_temperature_celsius, :degree_day_kind, "
            ":weather_source, :weather_days_missing, :normalization_status, "
            ":normalized_consumption, CAST(:evidence AS JSONB), :computed_at, :computed_by"
            ")"
        ),
        {
            "id": result_id,
            "tenant_id": tenant_id,
            "functional_location_id": point["functional_location_id"],
            "point_id": point["id"],
            "baseline_config_version_id": baseline_config_version_id,
            "period_start": period_start,
            "period_end": period_end,
            "method": content["method"],
            "method_version": content["method_version"],
            "parameters": json.dumps(content, sort_keys=True, separators=(",", ":")),
            "raw_consumption": consumption["raw_consumption"],
            "raw_consumption_unit": consumption["raw_consumption_unit"],
            "measurement_count": consumption["measurement_count"],
            "data_completeness": consumption["data_completeness"],
            "quality_flags": json.dumps(
                consumption["quality_flags"], sort_keys=True, separators=(",", ":")
            ),
            "degree_days": degree_days_analyzed["degree_days"],
            "degree_day_base_temperature_celsius": base_temperature,
            "degree_day_kind": degree_day_kind,
            "weather_source": ",".join(degree_days_analyzed["sources"]) or None,
            "weather_days_missing": degree_days_analyzed["days_missing"],
            "normalization_status": normalization_status,
            "normalized_consumption": normalized_consumption,
            "evidence": json.dumps(evidence, sort_keys=True, separators=(",", ":")),
            "computed_at": at,
            "computed_by": computed_by,
        },
    )
    return get_normalized_result(connection, result_id)
