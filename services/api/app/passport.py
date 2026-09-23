"""Passeport numérique d'un actif (addendum V2, point 13).

Une vue, pas une base : tout ce qui s'affiche est lu, au moment de la
consultation, dans le registre, le graphe, la télémétrie et la GMAO, autour
d'un même identifiant (ADR 012, section 2.3). Tout est lu sous RLS : un
tenant ne voit que ses données.

Les « actions autorisées » sont calculées ici, côté serveur, à partir des
rôles : l'application n'en déduit jamais d'elle-même. Aucune action de
commande d'équipement n'existe (règle non négociable 1).
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.closure_vocabulary import label as closure_label
from app.findings import displayed
from app.graph import get_node
from app.i18n import DEFAULT_LOCALE
from app.lifecycle import lifecycle_history
from app.properties import list_properties
from app.tags import list_tags

_MANAGER_ROLES = {"responsable_exploitation", "admin_tenant"}
_FIELD_ROLES = {"technicien"} | _MANAGER_ROLES


def allowed_actions(roles: set[str], node_type: str) -> list[str]:
    actions: list[str] = []
    if roles & _FIELD_ROLES and node_type in ("functional_location", "physical_unit"):
        actions += [
            "log_intervention",
            "raise_alarm",
            "acknowledge_signal",
            "update_signal_handling",
            "confirm_finding",
        ]
    if roles & _MANAGER_ROLES:
        if node_type in ("functional_location", "physical_unit"):
            actions.append("create_work_order")
        if node_type == "functional_location":
            actions.append("assign_physical_unit")
        if node_type == "physical_unit":
            actions.append("change_lifecycle_state")
        actions += ["manage_tags", "set_properties"]
    return actions


def _one(connection: Connection, query: str, params: dict) -> dict[str, Any] | None:
    row = connection.execute(text(query), params).mappings().first()
    return dict(row) if row else None


def _all(connection: Connection, query: str, params: dict) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(text(query), params).mappings()]


def _space_path(connection: Connection, space_id: uuid.UUID | None) -> list[dict[str, Any]]:
    """Du bâtiment à la pièce : « Bâtiment A › Étage 1 › Bureau 104 »."""
    path: list[dict[str, Any]] = []
    while space_id is not None and len(path) < 20:
        space = _one(
            connection,
            "SELECT id, parent_id, space_type, code, name FROM spaces WHERE id = :id",
            {"id": space_id},
        )
        if space is None:
            break
        path.insert(0, {k: space[k] for k in ("id", "space_type", "code", "name")})
        space_id = space["parent_id"]
    return path


def _unit_summary(connection: Connection, unit_id: uuid.UUID) -> dict[str, Any] | None:
    unit = _one(
        connection,
        "SELECT u.id, u.serial_number, u.lifecycle_state, u.commissioned_at, "
        "m.manufacturer, m.reference, m.category FROM physical_units u "
        "JOIN product_models m ON m.id = u.product_model_id WHERE u.id = :id",
        {"id": unit_id},
    )
    if unit is not None:
        unit["properties"] = list_properties(connection, unit_id)
    return unit


def _points(connection: Connection, column: str, node_id: uuid.UUID) -> list[dict[str, Any]]:
    points = _all(
        connection,
        f"SELECT id, code, name, point_class, kind, unit, mapping_status FROM points "
        f"WHERE {column} = :id ORDER BY code",
        {"id": node_id},
    )
    for point in points:
        point["latest"] = _one(
            connection,
            "SELECT value, measured_at, origin, quality_flags FROM measurements "
            "WHERE point_id = :id ORDER BY measured_at DESC LIMIT 1",
            {"id": point["id"]},
        )
    return points


def _maintenance(connection: Connection, location_id: uuid.UUID, locale: str) -> dict[str, Any]:
    interventions = _all(
        connection,
        "SELECT i.id, i.intervention_type, i.started_at, i.summary, i.technician, "
        "c.symptom_code, c.action_code, c.verification_result FROM interventions i "
        "LEFT JOIN intervention_closures c ON c.intervention_id = i.id "
        "WHERE i.functional_location_id = :id ORDER BY i.started_at DESC LIMIT 5",
        {"id": location_id},
    )
    for intervention in interventions:
        intervention["symptom_label"] = closure_label(
            "symptoms", intervention["symptom_code"], locale
        )
        intervention["action_label"] = closure_label("actions", intervention["action_code"], locale)
    return {
        "open_alarms": _all(
            connection,
            "SELECT id, severity, message, condition_state, ack_state, handling_status, "
            "raised_at FROM alarms WHERE functional_location_id = :id "
            "AND handling_status IN ('open', 'in_progress') ORDER BY raised_at DESC",
            {"id": location_id},
        ),
        "open_work_orders": _all(
            connection,
            "SELECT id, title, priority, status, created_at FROM work_orders "
            "WHERE functional_location_id = :id AND status IN ('open', 'in_progress') "
            "ORDER BY created_at DESC",
            {"id": location_id},
        ),
        "recent_interventions": interventions,
    }


def _site(connection: Connection, site_id: uuid.UUID | None) -> dict[str, Any] | None:
    """Le site et son fuseau : les heures du passeport s'affichent dans ce
    fuseau quand il est connu."""
    if site_id is None:
        return None
    return _one(connection, "SELECT id, name, timezone FROM sites WHERE id = :id", {"id": site_id})


def build_passport(
    connection: Connection, node_id: uuid.UUID, roles: set[str], locale: str = DEFAULT_LOCALE
) -> dict[str, Any] | None:
    node = get_node(connection, node_id)
    if node is None:
        return None
    node_type = node["node_type"]
    passport: dict[str, Any] = {
        "node_id": node_id,
        "node_type": node_type,
        "tags": [t for t in list_tags(connection, node_id) if t["status"] == "active"],
        "allowed_actions": allowed_actions(roles, node_type),
    }

    location_id = None
    if node_type == "functional_location":
        location = _one(
            connection,
            "SELECT id, code, name, kind, site_id, space_id FROM functional_locations "
            "WHERE id = :id",
            {"id": node_id},
        )
        passport["functional_location"] = location
        passport["space_path"] = _space_path(connection, location["space_id"])
        occupant = connection.execute(
            text(
                "SELECT physical_unit_id FROM functional_location_assignments "
                "WHERE functional_location_id = :id AND valid_to IS NULL"
            ),
            {"id": node_id},
        ).scalar()
        passport["current_unit"] = _unit_summary(connection, occupant) if occupant else None
        passport["points"] = _points(connection, "functional_location_id", node_id)
        location_id = node_id

    elif node_type == "physical_unit":
        passport["physical_unit"] = _unit_summary(connection, node_id)
        passport["lifecycle"] = lifecycle_history(connection, node_id)[-10:]
        location_id = connection.execute(
            text(
                "SELECT functional_location_id FROM functional_location_assignments "
                "WHERE physical_unit_id = :id AND valid_to IS NULL"
            ),
            {"id": node_id},
        ).scalar()
        passport["current_location_id"] = location_id

    elif node_type == "space":
        passport["space_path"] = _space_path(connection, node_id)
        passport["points"] = _points(connection, "space_id", node_id)

    elif node_type == "point":
        passport["point"] = _one(
            connection,
            "SELECT id, code, name, point_class, unit, mapping_status, functional_location_id, "
            "space_id FROM points WHERE id = :id",
            {"id": node_id},
        )

    open_findings = _all(
        connection,
        "SELECT id, kind, severity, reason_code, reason_params, title, recommended_action, "
        "certainty, condition_state, ack_state, handling_status, occurrence_count, "
        "last_seen_at FROM findings WHERE handling_status IN ('open', 'in_progress') "
        "AND (subject_node_id = :id OR subject_node_id = :location) ORDER BY last_seen_at DESC",
        {"id": node_id, "location": location_id or node_id},
    )
    passport["open_findings"] = [displayed(finding, locale) for finding in open_findings]
    passport["site"] = _site(connection, _site_id(connection, node_type, node_id, location_id))
    if location_id is not None:
        passport.update(_maintenance(connection, location_id, locale))
    return passport


def _site_id(
    connection: Connection, node_type: str, node_id: uuid.UUID, location_id: uuid.UUID | None
) -> uuid.UUID | None:
    if location_id is not None:
        return connection.execute(
            text("SELECT site_id FROM functional_locations WHERE id = :id"), {"id": location_id}
        ).scalar()
    if node_type == "space":
        return connection.execute(
            text("SELECT site_id FROM spaces WHERE id = :id"), {"id": node_id}
        ).scalar()
    if node_type == "point":
        return connection.execute(
            text(
                "SELECT COALESCE(fl.site_id, s.site_id) FROM points p "
                "LEFT JOIN functional_locations fl ON fl.id = p.functional_location_id "
                "LEFT JOIN spaces s ON s.id = p.space_id WHERE p.id = :id"
            ),
            {"id": node_id},
        ).scalar()
    return None
