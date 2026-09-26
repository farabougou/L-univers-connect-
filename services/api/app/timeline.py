"""Mémoire opérationnelle : « pourquoi cette configuration existe-t-elle,
des années après » (feature-benchmark-matrix.md, ligne « Mémoire
opérationnelle »). Pas de nouvelle base : un assemblage, au moment de la
consultation, des historiques qui existent déjà séparément (interventions,
ordres de travail, alarmes, constats, cycle de vie d'un exemplaire) — une
vue pure, comme le passeport (app/passport.py), jamais un effet de bord.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.findings import displayed
from app.i18n import DEFAULT_LOCALE
from app.lifecycle import lifecycle_history

SUPPORTED_NODE_TYPES = ("functional_location", "physical_unit")

_LOCATION_COLUMN = {
    "functional_location": "functional_location_id",
    "physical_unit": "physical_unit_id",
}


def _interventions(connection: Connection, column: str, node_id: uuid.UUID) -> list[dict]:
    rows = connection.execute(
        text(
            f"SELECT id, intervention_type, started_at, summary, technician "
            f"FROM interventions WHERE {column} = :id"
        ),
        {"id": node_id},
    ).mappings()
    return [
        {
            "kind": "intervention",
            "at": row["started_at"],
            "reference_id": row["id"],
            "title": row["summary"],
            "field": "intervention_type",
            "status": row["intervention_type"],
            "changed_by": row["technician"],
            "note": None,
        }
        for row in rows
    ]


def _work_orders(connection: Connection, column: str, node_id: uuid.UUID) -> list[dict]:
    rows = connection.execute(
        text(
            "SELECT h.work_order_id, h.status, h.changed_by, h.note, h.changed_at, w.title "
            "FROM work_order_status_history h "
            f"JOIN work_orders w ON w.id = h.work_order_id WHERE w.{column} = :id"
        ),
        {"id": node_id},
    ).mappings()
    return [
        {
            "kind": "work_order",
            "at": row["changed_at"],
            "reference_id": row["work_order_id"],
            "title": row["title"],
            "field": "status",
            "status": row["status"],
            "changed_by": row["changed_by"],
            "note": row["note"],
        }
        for row in rows
    ]


def _alarms(connection: Connection, column: str, node_id: uuid.UUID) -> list[dict]:
    rows = connection.execute(
        text(
            "SELECT h.alarm_id, h.field, h.status, h.changed_by, h.note, h.changed_at, "
            "a.message FROM alarm_status_history h "
            f"JOIN alarms a ON a.id = h.alarm_id WHERE a.{column} = :id"
        ),
        {"id": node_id},
    ).mappings()
    return [
        {
            "kind": "alarm",
            "at": row["changed_at"],
            "reference_id": row["alarm_id"],
            "title": row["message"],
            "field": row["field"],
            "status": row["status"],
            "changed_by": row["changed_by"],
            "note": row["note"],
        }
        for row in rows
    ]


def _findings(connection: Connection, node_id: uuid.UUID, locale: str) -> list[dict]:
    rows = connection.execute(
        text(
            "SELECT h.finding_id, h.field, h.status, h.changed_by, h.note, h.changed_at, "
            "f.reason_code, f.reason_params, f.title, f.recommended_action "
            "FROM finding_status_history h "
            "JOIN findings f ON f.id = h.finding_id WHERE f.subject_node_id = :id"
        ),
        {"id": node_id},
    ).mappings()
    entries = []
    for row in rows:
        rendered = displayed(dict(row), locale)
        entries.append(
            {
                "kind": "finding",
                "at": row["changed_at"],
                "reference_id": row["finding_id"],
                "title": rendered["title"],
                "field": row["field"],
                "status": row["status"],
                "changed_by": row["changed_by"],
                "note": row["note"],
            }
        )
    return entries


def _lifecycle(connection: Connection, physical_unit_id: uuid.UUID) -> list[dict]:
    return [
        {
            "kind": "lifecycle",
            "at": event["occurred_at"],
            "reference_id": physical_unit_id,
            "title": None,
            "field": "lifecycle_state",
            "status": event["to_state"],
            "changed_by": event["changed_by"],
            "note": event["note"],
        }
        for event in lifecycle_history(connection, physical_unit_id)
    ]


def node_timeline(
    connection: Connection,
    *,
    node_id: uuid.UUID,
    node_type: str,
    locale: str = DEFAULT_LOCALE,
    before: datetime | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Chronologie fusionnée, la plus récente d'abord. `before` permet de
    remonter dans une longue histoire sans jamais tout charger d'un coup."""
    column = _LOCATION_COLUMN[node_type]
    entries = (
        _interventions(connection, column, node_id)
        + _work_orders(connection, column, node_id)
        + _alarms(connection, column, node_id)
        + _findings(connection, node_id, locale)
    )
    if node_type == "physical_unit":
        entries += _lifecycle(connection, node_id)

    entries.sort(key=lambda entry: entry["at"], reverse=True)
    if before is not None:
        entries = [entry for entry in entries if entry["at"] < before]
    return entries[:limit]
