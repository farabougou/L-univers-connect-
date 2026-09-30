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


# --- Chronologie portefeuille : bloc « Activité récente » du Global Command
# Center (directive UI/dashboard, section 16). Mêmes quatre sources et même
# forme d'entrée que `node_timeline`, mais sans filtre d'équipement et avec
# `functional_location_id` en plus (pour le lien de chaque ligne) — des
# fonctions dédiées plutôt qu'un paramètre optionnel sur les fonctions
# ci-dessus, pour ne jamais risquer de changer le comportement déjà testé de
# la chronologie par équipement. Chaque requête est bornée par `limit` :
# jamais l'historique complet d'un tenant chargé pour n'en garder que les
# derniers (directive, section 29).


def _portfolio_interventions(connection: Connection, limit: int) -> list[dict]:
    rows = connection.execute(
        text(
            "SELECT id, functional_location_id, intervention_type, started_at, summary, "
            "technician FROM interventions ORDER BY started_at DESC LIMIT :limit"
        ),
        {"limit": limit},
    ).mappings()
    return [
        {
            "kind": "intervention",
            "at": row["started_at"],
            "functional_location_id": row["functional_location_id"],
            "reference_id": row["id"],
            "title": row["summary"],
            "field": "intervention_type",
            "status": row["intervention_type"],
            "changed_by": row["technician"],
            "note": None,
        }
        for row in rows
    ]


def _portfolio_work_orders(connection: Connection, limit: int) -> list[dict]:
    rows = connection.execute(
        text(
            "SELECT h.work_order_id, h.status, h.changed_by, h.note, h.changed_at, "
            "w.title, w.functional_location_id FROM work_order_status_history h "
            "JOIN work_orders w ON w.id = h.work_order_id "
            "ORDER BY h.changed_at DESC LIMIT :limit"
        ),
        {"limit": limit},
    ).mappings()
    return [
        {
            "kind": "work_order",
            "at": row["changed_at"],
            "functional_location_id": row["functional_location_id"],
            "reference_id": row["work_order_id"],
            "title": row["title"],
            "field": "status",
            "status": row["status"],
            "changed_by": row["changed_by"],
            "note": row["note"],
        }
        for row in rows
    ]


def _portfolio_alarms(connection: Connection, limit: int) -> list[dict]:
    rows = connection.execute(
        text(
            "SELECT h.alarm_id, h.field, h.status, h.changed_by, h.note, h.changed_at, "
            "a.message, a.functional_location_id FROM alarm_status_history h "
            "JOIN alarms a ON a.id = h.alarm_id ORDER BY h.changed_at DESC LIMIT :limit"
        ),
        {"limit": limit},
    ).mappings()
    return [
        {
            "kind": "alarm",
            "at": row["changed_at"],
            "functional_location_id": row["functional_location_id"],
            "reference_id": row["alarm_id"],
            "title": row["message"],
            "field": row["field"],
            "status": row["status"],
            "changed_by": row["changed_by"],
            "note": row["note"],
        }
        for row in rows
    ]


def _portfolio_findings(connection: Connection, limit: int, locale: str) -> list[dict]:
    rows = connection.execute(
        text(
            "SELECT h.finding_id, h.field, h.status, h.changed_by, h.note, h.changed_at, "
            "f.reason_code, f.reason_params, f.title, f.recommended_action, f.subject_node_id "
            "FROM finding_status_history h JOIN findings f ON f.id = h.finding_id "
            "ORDER BY h.changed_at DESC LIMIT :limit"
        ),
        {"limit": limit},
    ).mappings()
    entries = []
    for row in rows:
        rendered = displayed(dict(row), locale)
        entries.append(
            {
                "kind": "finding",
                "at": row["changed_at"],
                # Un constat peut porter sur un équipement ou un exemplaire
                # (SUPPORTED_NODE_TYPES) : le lien du portefeuille ne
                # s'affiche que si c'est bien un équipement, jamais deviné.
                "functional_location_id": row["subject_node_id"],
                "reference_id": row["finding_id"],
                "title": rendered["title"],
                "field": row["field"],
                "status": row["status"],
                "changed_by": row["changed_by"],
                "note": row["note"],
            }
        )
    return entries


def portfolio_timeline(
    connection: Connection, *, locale: str = DEFAULT_LOCALE, limit: int = 20
) -> list[dict[str, Any]]:
    """Bloc « Activité récente » du Global Command Center : les quatre
    sources déjà unifiées par `node_timeline`, pour tout le portefeuille du
    tenant plutôt qu'un seul équipement. Volontairement absents (aucune
    trace exploitable aujourd'hui) : changements d'état d'équipement,
    événements énergétiques, incidents (distincts des alarmes, section 24) ;
    et présents dans `events` mais pas encore raccordés ici : événements
    Edge, changements de connectivité, commandes — DEFER, signalé dans
    docs/spec/feature-benchmark-matrix.md plutôt qu'ignoré."""
    entries = (
        _portfolio_interventions(connection, limit)
        + _portfolio_work_orders(connection, limit)
        + _portfolio_alarms(connection, limit)
        + _portfolio_findings(connection, limit, locale)
    )
    entries.sort(key=lambda entry: entry["at"], reverse=True)
    return entries[:limit]


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
