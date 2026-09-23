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


def _latest_usable(
    connection: Connection, point_id: uuid.UUID, at: datetime
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                "SELECT value, measured_at FROM measurements WHERE point_id = :id "
                "AND measured_at <= :at AND NOT (quality_flags && CAST(:doubtful AS varchar[])) "
                "ORDER BY measured_at DESC LIMIT 1"
            ),
            {"id": point_id, "at": at, "doubtful": list(_DOUBTFUL)},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


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
        result["reason"] = "NO_STATUS_POINT"
        return result

    values: dict[str, float] = {}
    freshness: list[bool] = []
    for point in points:
        latest = _latest_usable(connection, point["id"], at)
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
        result["reason"] = "NO_MEASUREMENT"
        return result

    result["as_of"] = max(source["measured_at"] for source in result["sources"])
    result["operational_status"] = _operational(values)
    if any(freshness):
        result["communication_status"] = "online"
    elif freshness:
        result["communication_status"] = "offline"
    result["current"] = result["communication_status"] == "online"
    return result
