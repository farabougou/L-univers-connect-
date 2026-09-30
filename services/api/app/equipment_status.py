"""État d'un équipement : fonctionnement et communication (ADR 013, 4.5, étape L6).

Deux axes qui ne se remplacent jamais l'un l'autre :
- fonctionnement (`running`, `stopped`, `disabled`, `fault`, `unknown`),
  déduit des points d'état validés de l'équipement ;
- communication (`online`, `offline`, `unknown` ; `unreachable` viendra avec
  l'agent Edge en M3, qui saura dire qu'une tentative a échoué).

« Hors ligne » n'est pas un état de fonctionnement : c'est l'absence de
donnée récente. L'état affiché est alors le dernier état connu, avec sa date,
et `current` est faux. Sans intervalle attendu sur les points (remontée sur
changement seulement), l'actualité ne peut pas être affirmée : communication
« inconnue », jamais « en ligne » par supposition.

Calcul à la lecture, jamais stocké : rien à historiser en double, la source
(les mesures) l'est déjà. Une valeur marquée douteuse à la réception n'est
jamais utilisée.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.quality_flags import FLAG_CLOCK_SUSPECT, FLAG_OUT_OF_RANGE
from app.trust import STALE_AFTER_INTERVALS

STATUS_CLASSES = ("run_status", "fault_status", "enable_status")
OPERATIONAL_STATUSES = ("running", "stopped", "disabled", "fault", "unknown")
COMMUNICATION_STATUSES = ("online", "offline", "unreachable", "unknown")
_DOUBTFUL = (FLAG_OUT_OF_RANGE, FLAG_CLOCK_SUSPECT)


def latest_usable_bulk(
    connection: Connection, point_ids: list[uuid.UUID], at: datetime
) -> dict[uuid.UUID, dict[str, Any]]:
    """Dernier relevé exploitable pour chaque point de `point_ids`, en une
    seule requête (`DISTINCT ON`) plutôt qu'une par point — condition posée
    par la directive UI/dashboard (section 29) avant qu'un calcul portefeuille
    (bloc « Santé des actifs », page Telemetry) puisse interroger tout le
    tenant sans faire un aller-retour par point. Publique : réutilisée par
    app/telemetry_overview.py, jamais dupliquée une deuxième fois."""
    if not point_ids:
        return {}
    rows = (
        connection.execute(
            text(
                "SELECT DISTINCT ON (point_id) point_id, value, measured_at FROM measurements "
                "WHERE point_id = ANY(:ids) AND measured_at <= :at "
                "AND NOT (quality_flags && CAST(:doubtful AS varchar[])) "
                "ORDER BY point_id, measured_at DESC"
            ),
            {"ids": point_ids, "at": at, "doubtful": list(_DOUBTFUL)},
        )
        .mappings()
        .all()
    )
    return {row["point_id"]: dict(row) for row in rows}


def _status_from_points(
    points: list[dict[str, Any]],
    latest_by_point: dict[uuid.UUID, dict[str, Any]],
    at: datetime,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "operational_status": "unknown",
        "communication_status": "unknown",
        "current": False,
        "as_of": None,
        "reason": None,
        "evaluated_at": at,
        "sources": [],
    }
    if not points:
        result["reason"] = "no_status_point"
        return result

    values: dict[str, float] = {}
    freshness: list[bool] = []
    for point in points:
        latest = latest_by_point.get(point["id"])
        if latest is None:
            continue
        values[point["point_class"]] = latest["value"]
        result["sources"].append(
            {
                "point_id": point["id"],
                "point_class": point["point_class"],
                "value": latest["value"],
                "measured_at": latest["measured_at"],
            }
        )
        interval = point["expected_interval_seconds"]
        if interval:
            limit = STALE_AFTER_INTERVALS * timedelta(seconds=interval)
            freshness.append(at - latest["measured_at"] <= limit)

    if not result["sources"]:
        result["reason"] = "no_measurement"
        return result

    result["as_of"] = max(source["measured_at"] for source in result["sources"])
    result["operational_status"] = _operational(values)
    if any(freshness):
        result["communication_status"] = "online"
    elif freshness:
        result["communication_status"] = "offline"
    result["current"] = result["communication_status"] == "online"
    return result


def _operational(values: dict[str, float]) -> str:
    # Ordre de priorité : un défaut signalé l'emporte, puis l'interdiction de
    # marche, puis l'état de marche. Sans état de marche : inconnu.
    if values.get("fault_status") == 1:
        return "fault"
    if values.get("enable_status") == 0:
        return "disabled"
    if "run_status" in values:
        return "running" if values["run_status"] == 1 else "stopped"
    return "unknown"


def compute_equipment_status(
    connection: Connection, functional_location_id: uuid.UUID, at: datetime
) -> dict[str, Any]:
    points = (
        connection.execute(
            text(
                "SELECT id, point_class, expected_interval_seconds FROM points "
                "WHERE functional_location_id = :id AND mapping_status = 'validated' "
                "AND point_class IN ('run_status', 'fault_status', 'enable_status') "
                "ORDER BY code"
            ),
            {"id": functional_location_id},
        )
        .mappings()
        .all()
    )
    points = [dict(point) for point in points]
    latest_by_point = latest_usable_bulk(connection, [point["id"] for point in points], at)
    return _status_from_points(points, latest_by_point, at)


def compute_portfolio_equipment_status(
    connection: Connection, at: datetime
) -> dict[uuid.UUID, dict[str, Any]]:
    """Comme `compute_equipment_status`, mais pour tous les équipements non
    archivés du tenant courant (RLS) en une poignée de requêtes plutôt
    qu'une par équipement — condition posée par la directive UI/dashboard
    (section 29) avant de construire le bloc « Santé des actifs » du Global
    Command Center. Ne déclenche jamais `evaluate_communication_status` :
    ce calcul reste un affichage pur, comme `compute_equipment_status` lui-
    même ; le balayage périodique (`app/supervision_sweep.py`) reste le seul
    déclencheur d'alerte pour une communication perdue."""
    location_ids = [
        row[0]
        for row in connection.execute(
            text("SELECT id FROM functional_locations WHERE archived_at IS NULL")
        ).all()
    ]
    points = [
        dict(row)
        for row in connection.execute(
            text(
                "SELECT id, functional_location_id, point_class, expected_interval_seconds "
                "FROM points WHERE mapping_status = 'validated' "
                "AND point_class IN ('run_status', 'fault_status', 'enable_status') "
                "ORDER BY functional_location_id, code"
            )
        )
        .mappings()
        .all()
    ]
    by_location: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for point in points:
        by_location.setdefault(point["functional_location_id"], []).append(point)

    latest_by_point = latest_usable_bulk(connection, [point["id"] for point in points], at)

    return {
        location_id: _status_from_points(by_location.get(location_id, []), latest_by_point, at)
        for location_id in location_ids
    }
