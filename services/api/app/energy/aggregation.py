"""Energy Aggregation : consommation brute sur une période, à partir d'un
compteur cumulatif (`energy_meter_reading`, ex. SDM120 `total_active_energy`).

Un compteur cumulatif ne se somme pas : la consommation d'une période est la
différence entre le dernier relevé utilisable avant sa fin et le dernier
relevé utilisable avant son début (même principe qu'un relevé de facture).
Une valeur marquée douteuse à la réception n'est jamais utilisée comme borne
(même règle que app/equipment_status.py).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError
from app.points import list_points
from app.quality_flags import FLAG_CLOCK_SUSPECT, FLAG_OUT_OF_RANGE

_DOUBTFUL = (FLAG_OUT_OF_RANGE, FLAG_CLOCK_SUSPECT)


class EnergyDataInsufficient(DomainError, ValueError):
    status = 422


def _latest_usable(connection: Connection, point_id: uuid.UUID, before: datetime) -> dict | None:
    row = (
        connection.execute(
            text(
                "SELECT value, measured_at, origin, quality_flags FROM measurements "
                "WHERE point_id = :id AND measured_at < :before "
                "AND NOT (quality_flags && CAST(:doubtful AS varchar[])) "
                "ORDER BY measured_at DESC LIMIT 1"
            ),
            {"id": point_id, "before": before, "doubtful": list(_DOUBTFUL)},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def aggregate_energy_consumption(
    connection: Connection,
    *,
    point: dict[str, Any],
    period_start,
    period_end,
) -> dict[str, Any]:
    """`point` : dict issu de app/points.py::get_point (id, unit,
    expected_interval_seconds). `period_start`/`period_end` : dates,
    bornes incluses."""
    start_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(period_end + timedelta(days=1), datetime.min.time(), tzinfo=UTC)

    opening = _latest_usable(connection, point["id"], before=start_dt)
    closing = _latest_usable(connection, point["id"], before=end_dt)
    if opening is None or closing is None:
        raise EnergyDataInsufficient("ENERGY_DATA_INSUFFICIENT")
    raw_consumption = closing["value"] - opening["value"]
    if raw_consumption < 0:
        # Compteur remplacé ou remis à zéro pendant la période : aucun calcul
        # fiable possible ici. Découper la période autour du remplacement
        # reste à faire à la main pour la V1 (backlog).
        raise EnergyDataInsufficient("ENERGY_METER_RESET_DETECTED")

    rows = (
        connection.execute(
            text(
                "SELECT origin, cardinality(quality_flags) AS flag_count FROM measurements "
                "WHERE point_id = :id AND measured_at >= :start AND measured_at < :end"
            ),
            {"id": point["id"], "start": start_dt, "end": end_dt},
        )
        .mappings()
        .all()
    )
    origin_counts: dict[str, int] = {}
    flagged_count = 0
    for row in rows:
        origin_counts[row["origin"]] = origin_counts.get(row["origin"], 0) + 1
        if row["flag_count"]:
            flagged_count += 1

    completeness = None
    interval = point["expected_interval_seconds"]
    if interval:
        expected = max(1, int((end_dt - start_dt).total_seconds() // interval))
        completeness = round(min(1.0, len(rows) / expected), 3)

    return {
        "raw_consumption": raw_consumption,
        "raw_consumption_unit": point["unit"],
        "measurement_count": len(rows),
        "data_completeness": completeness,
        "quality_flags": {"flagged_count": flagged_count},
        "evidence": {
            "opening_measured_at": opening["measured_at"].isoformat(),
            "opening_value": opening["value"],
            "closing_measured_at": closing["measured_at"].isoformat(),
            "closing_value": closing["value"],
            "origin_counts": origin_counts,
        },
    }


def list_energy_meter_points(connection: Connection) -> list[dict[str, Any]]:
    """Compteurs d'énergie validés du tenant courant (RLS). Seule source
    utilisée pour le bloc Énergie du tableau de bord : jamais un point
    encore proposé ou rejeté (mapping_status != "validated")."""
    return list_points(connection, mapping_status="validated", point_class="energy_meter_reading")


def aggregate_portfolio_daily_energy(
    connection: Connection,
    *,
    reference_date: date,
) -> list[dict[str, Any]]:
    """Pour chaque compteur d'énergie validé, consommation du jour de
    référence (jour calendaire complet, borne UTC — même convention que
    `aggregate_energy_consumption`) et de la veille de ce jour, pour
    calculer une tendance. Un compteur sans donnée suffisante
    (`EnergyDataInsufficient`) n'empêche jamais les autres : chaque
    compteur est rapporté individuellement, avec `None` pour la valeur
    manquante plutôt qu'une erreur globale."""
    entries: list[dict[str, Any]] = []
    for point in list_energy_meter_points(connection):
        entry: dict[str, Any] = {
            "point_id": point["id"],
            "functional_location_id": point["functional_location_id"],
            "unit": point["unit"],
            "consumption": None,
            "previous_consumption": None,
        }
        try:
            current = aggregate_energy_consumption(
                connection, point=point, period_start=reference_date, period_end=reference_date
            )
            entry["consumption"] = current["raw_consumption"]
        except EnergyDataInsufficient:
            pass
        previous_date = reference_date - timedelta(days=1)
        try:
            previous = aggregate_energy_consumption(
                connection, point=point, period_start=previous_date, period_end=previous_date
            )
            entry["previous_consumption"] = previous["raw_consumption"]
        except EnergyDataInsufficient:
            pass
        entries.append(entry)
    return entries
