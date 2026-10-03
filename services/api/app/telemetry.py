"""Télémétrie en lecture seule, organisée par point (ADR 012, étape F3).

Lecture seule par construction : ce module n'enregistre que des valeurs déjà
relevées, jamais il n'écrit vers un équipement (règle non négociable 1).

Principes :
- une valeur impossible pour le type du point (texte, infini, état inconnu)
  est refusée ;
- une valeur plausible mais douteuse (hors plage physique, horloge suspecte,
  arrivée très tardive, point pas encore validé) est **gardée et marquée** :
  on ne jette jamais une donnée, on la qualifie ;
- un relevé renvoyé deux fois (reprise après coupure) est reconnu et ignoré ;
  deux valeurs différentes pour le même point et le même instant sont un
  conflit signalé, jamais un écrasement.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError
from app.point_vocabulary import PointVocabularyError, check_value
from app.points import get_point
from app.quality_flags import (
    FLAG_CLOCK_SUSPECT,
    FLAG_LATE_ARRIVAL,
    FLAG_OUT_OF_RANGE,
    FLAG_UNVALIDATED_POINT,
)
from app.rules import evaluate_after_measurement

# Tolérance d'horloge : un relevé daté de plus de 5 minutes dans le futur
# révèle une horloge d'Edge ou de capteur déréglée.
CLOCK_TOLERANCE = timedelta(minutes=5)
# Au-delà de 24 h entre relevé et réception : arrivée tardive (stock envoyé
# après une longue coupure). La valeur reste bonne, mais on le sait.
LATE_ARRIVAL = timedelta(hours=24)


class MeasurementRejected(DomainError, ValueError):
    pass


class MeasurementConflict(DomainError, ValueError):
    status = 409


def compute_quality_flags(
    point: dict[str, Any], *, value: float, measured_at: datetime, received_at: datetime
) -> list[str]:
    flags = []
    if point["mapping_status"] != "validated":
        flags.append(FLAG_UNVALIDATED_POINT)
    if (point["min_value"] is not None and value < point["min_value"]) or (
        point["max_value"] is not None and value > point["max_value"]
    ):
        flags.append(FLAG_OUT_OF_RANGE)
    if measured_at > received_at + CLOCK_TOLERANCE:
        flags.append(FLAG_CLOCK_SUSPECT)
    elif received_at - measured_at > LATE_ARRIVAL:
        flags.append(FLAG_LATE_ARRIVAL)
    return flags


def record_measurement(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    point: dict[str, Any],
    value: float,
    measured_at: datetime,
    origin: str,
    source: str,
    received_at: datetime,
) -> str:
    """Enregistre un relevé. Renvoie « inserted » ou « duplicate »."""
    if point["mapping_status"] == "rejected":
        raise MeasurementRejected("POINT_REJECTED")
    try:
        check_value(value, value_type=point["value_type"], states=point["states"])
    except PointVocabularyError as exc:
        raise MeasurementRejected.from_error(exc) from exc

    flags = compute_quality_flags(
        point, value=value, measured_at=measured_at, received_at=received_at
    )
    inserted = connection.execute(
        text(
            "INSERT INTO measurements (point_id, measured_at, tenant_id, value, origin, source, "
            "quality_flags, received_at) VALUES (:point_id, :measured_at, :tenant_id, :value, "
            ":origin, :source, :quality_flags, :received_at) "
            "ON CONFLICT (point_id, measured_at) DO NOTHING RETURNING point_id"
        ),
        {
            "point_id": point["id"],
            "measured_at": measured_at,
            "tenant_id": tenant_id,
            "value": value,
            "origin": origin,
            "source": source,
            "quality_flags": flags,
            "received_at": received_at,
        },
    ).scalar()
    if inserted is not None:
        # Qualité puis règles, dans la même transaction : si l'évaluation
        # échoue, la mesure n'est pas enregistrée à moitié.
        evaluate_after_measurement(
            connection,
            tenant_id=tenant_id,
            point=point,
            value=value,
            measured_at=measured_at,
            quality_flags=flags,
        )
        return "inserted"

    existing = connection.execute(
        text("SELECT value FROM measurements WHERE point_id = :p AND measured_at = :m"),
        {"p": point["id"], "m": measured_at},
    ).scalar()
    if existing != value:
        raise MeasurementConflict("MEASUREMENT_CONFLICT", existing_value=existing)
    return "duplicate"


def ingest_measurements(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    items: list[dict[str, Any]],
    source: str,
    received_at: datetime,
) -> dict[str, Any]:
    """Réception par lot (envoi différé d'un Edge après coupure, par exemple).

    Chaque relevé est traité indépendamment : un relevé refusé n'empêche pas
    les autres d'être enregistrés, et le résultat dit exactement lequel a
    échoué et pourquoi.
    """
    summary: dict[str, Any] = {"inserted": 0, "duplicates": 0, "conflicts": 0, "rejected": 0}
    errors: list[dict[str, Any]] = []
    points: dict[uuid.UUID, dict[str, Any] | None] = {}

    for index, item in enumerate(items):
        point_id = item["point_id"]
        if point_id not in points:
            points[point_id] = get_point(connection, point_id)
        point = points[point_id]
        if point is None:
            summary["rejected"] += 1
            errors.append(
                {"index": index, "point_id": point_id, "code": "POINT_NOT_FOUND", "params": {}}
            )
            continue
        try:
            status = record_measurement(
                connection,
                tenant_id=tenant_id,
                point=point,
                value=item["value"],
                measured_at=item["measured_at"],
                origin=item["origin"],
                source=source,
                received_at=received_at,
            )
        except (MeasurementRejected, MeasurementConflict) as exc:
            summary["conflicts" if isinstance(exc, MeasurementConflict) else "rejected"] += 1
            errors.append(
                {"index": index, "point_id": point_id, "code": exc.code, "params": exc.params}
            )
            continue
        summary["inserted" if status == "inserted" else "duplicates"] += 1

    summary["errors"] = errors
    return summary


MEASUREMENT_COLUMNS = "point_id, measured_at, value, origin, source, quality_flags, received_at"


def read_measurement(
    connection: Connection, point_id: uuid.UUID, measured_at: datetime
) -> dict[str, Any]:
    return dict(
        connection.execute(
            text(
                f"SELECT {MEASUREMENT_COLUMNS} FROM measurements "
                "WHERE point_id = :p AND measured_at = :m"
            ),
            {"p": point_id, "m": measured_at},
        )
        .mappings()
        .one()
    )


def list_measurements(
    connection: Connection,
    *,
    point_id: uuid.UUID,
    since: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = f"SELECT {MEASUREMENT_COLUMNS} FROM measurements WHERE point_id = :point_id"
    params: dict[str, Any] = {"point_id": point_id, "limit": limit}
    if since is not None:
        query += " AND measured_at >= :since"
        params["since"] = since
    query += " ORDER BY measured_at DESC LIMIT :limit"
    return [dict(row) for row in connection.execute(text(query), params).mappings()]
