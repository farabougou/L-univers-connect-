"""Mémoire opérationnelle : « pourquoi cette configuration existe-t-elle,
des années après » (feature-benchmark-matrix.md, ligne « Mémoire
opérationnelle »). Pas de nouvelle base : un assemblage, au moment de la
consultation, des historiques qui existent déjà séparément (interventions,
ordres de travail, alarmes, constats, cycle de vie d'un exemplaire, et
depuis le 02/10/2026 le journal système `app/events.py` — hors ligne/en
ligne, donnée périmée/rétablie, cycle de vie d'une commande) — une vue pure,
comme le passeport (app/passport.py), jamais un effet de bord.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.findings import displayed
from app.i18n import DEFAULT_LOCALE, load_catalog, render_text
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


# Un équipement a toujours une identité d'appareil Edge au plus, et chacun de
# ses points porte au plus une commande à la fois — jamais vrai pour deux
# équipements à la fois, donc une seule requête suffit, jamais du N+1.
_EVENTS_FOR_LOCATION_SQL = text(
    "SELECT id, event_type, subject_id, payload, occurred_at FROM events WHERE "
    "(subject_type = 'functional_location' AND subject_id = :id) OR "
    "(subject_type = 'point' AND subject_id IN "
    "  (SELECT id FROM points WHERE functional_location_id = :id)) OR "
    "(subject_type = 'command' AND subject_id IN "
    "  (SELECT id FROM commands WHERE point_id IN "
    "    (SELECT id FROM points WHERE functional_location_id = :id))) "
    "ORDER BY occurred_at DESC LIMIT :limit"
)


def _render_event_title(event_type: str, payload: dict[str, Any], locale: str) -> str:
    """Code stable + paramètres, jamais une phrase stockée (ADR 013) — même
    principe que `app.findings.displayed`."""
    catalog = load_catalog(locale, "events")
    return render_text(catalog["titles"][event_type], payload)


def _events(
    connection: Connection, node_id: uuid.UUID, locale: str, limit: int = 200
) -> list[dict]:
    """Journal système (`app/events.py`) : hors ligne/en ligne de
    l'équipement, donnée périmée/rétablie sur l'un de ses points, cycle de
    vie d'une commande sur l'un de ses points — jamais pour un exemplaire
    (`physical_unit`), ces trois faits ne concernent qu'une position
    fonctionnelle. Longtemps documenté comme un écart volontaire (« présents
    dans events mais pas encore raccordés ici »), comblé le 02/10/2026."""
    rows = connection.execute(_EVENTS_FOR_LOCATION_SQL, {"id": node_id, "limit": limit}).mappings()
    return [
        {
            "kind": "event",
            "at": row["occurred_at"],
            "reference_id": row["id"],
            "title": _render_event_title(row["event_type"], row["payload"], locale),
            "field": None,
            "status": row["event_type"],
            "changed_by": None,
            "note": None,
        }
        for row in rows
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


def _portfolio_events(connection: Connection, limit: int, locale: str) -> list[dict]:
    rows = connection.execute(
        text(
            "SELECT e.id, e.event_type, e.payload, e.occurred_at, "
            "COALESCE(p.functional_location_id, c_fl.functional_location_id, e.subject_id) "
            "AS functional_location_id "
            "FROM events e "
            "LEFT JOIN points p ON e.subject_type = 'point' AND p.id = e.subject_id "
            "LEFT JOIN commands c ON e.subject_type = 'command' AND c.id = e.subject_id "
            "LEFT JOIN points c_fl ON c_fl.id = c.point_id "
            "WHERE e.subject_type IN ('functional_location', 'point', 'command') "
            "ORDER BY e.occurred_at DESC LIMIT :limit"
        ),
        {"limit": limit},
    ).mappings()
    return [
        {
            "kind": "event",
            "at": row["occurred_at"],
            "functional_location_id": row["functional_location_id"],
            "reference_id": row["id"],
            "title": _render_event_title(row["event_type"], row["payload"], locale),
            "field": None,
            "status": row["event_type"],
            "changed_by": None,
            "note": None,
        }
        for row in rows
    ]


def portfolio_timeline(
    connection: Connection, *, locale: str = DEFAULT_LOCALE, limit: int = 20
) -> list[dict[str, Any]]:
    """Bloc « Activité récente » du Global Command Center : les cinq sources
    désormais unifiées par `node_timeline`, pour tout le portefeuille du
    tenant plutôt qu'un seul équipement — `events` raccordé le 02/10/2026
    (écart volontaire jusqu'ici, signalé plutôt qu'ignoré). Volontairement
    toujours absents (aucune trace exploitable à ce jour) : événements
    énergétiques, incidents (distincts des alarmes, section 24)."""
    entries = (
        _portfolio_interventions(connection, limit)
        + _portfolio_work_orders(connection, limit)
        + _portfolio_alarms(connection, limit)
        + _portfolio_findings(connection, limit, locale)
        + _portfolio_events(connection, limit, locale)
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
    else:
        # Hors ligne/en ligne, donnée périmée/rétablie, cycle de vie d'une
        # commande : trois faits qui ne concernent qu'une position
        # fonctionnelle, jamais un exemplaire (voir `_events`).
        entries += _events(connection, node_id, locale)

    entries.sort(key=lambda entry: entry["at"], reverse=True)
    if before is not None:
        entries = [entry for entry in entries if entry["at"] < before]
    return entries[:limit]
