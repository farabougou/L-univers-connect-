"""Modèle spatial (ADR 011, étape F2 de l'ADR 012).

Arbre des espaces (bâtiment, étage, pièce, zone) séparé de l'arbre technique
des positions fonctionnelles, et emplacement historisé de chaque position.
Toutes les lectures passent par la RLS : un élément d'un autre tenant est
simplement « introuvable ».
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError
from app.spatial_vocabulary import check_space_placement

_SPACE_COLUMNS = "id, site_id, parent_id, space_type, code, name, valid_from, valid_to, created_at"


class SpatialNotFound(DomainError, LookupError):
    status = 404


class SpatialConflict(DomainError, ValueError):
    status = 409


class SpatialInvalid(DomainError, ValueError):
    pass


def get_space(connection: Connection, space_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_SPACE_COLUMNS} FROM spaces WHERE id = :id"), {"id": space_id}
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _require_open_space(connection: Connection, space_id: uuid.UUID) -> dict[str, Any]:
    space = get_space(connection, space_id)
    if space is None:
        raise SpatialNotFound("SPACE_NOT_FOUND")
    if space["valid_to"] is not None:
        raise SpatialConflict("SPACE_ENDED")
    return space


def create_space(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    space_type: str,
    code: str,
    name: str,
    valid_from: datetime,
) -> uuid.UUID:
    site_exists = connection.execute(
        text("SELECT 1 FROM sites WHERE id = :id"), {"id": site_id}
    ).scalar()
    if not site_exists:
        raise SpatialNotFound("SITE_NOT_FOUND")

    parent_type = None
    if parent_id is not None:
        parent = _require_open_space(connection, parent_id)
        if parent["site_id"] != site_id:
            raise SpatialConflict("SPACE_PARENT_OTHER_SITE")
        parent_type = parent["space_type"]
    check_space_placement(space_type, parent_type)

    code_taken = connection.execute(
        text("SELECT 1 FROM spaces WHERE site_id = :site_id AND code = :code AND valid_to IS NULL"),
        {"site_id": site_id, "code": code},
    ).scalar()
    if code_taken:
        raise SpatialConflict("SPACE_CODE_ALREADY_USED", code=code)

    space_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO spaces (id, tenant_id, site_id, parent_id, space_type, code, name, "
            "valid_from) VALUES (:id, :tenant_id, :site_id, :parent_id, :space_type, :code, "
            ":name, :valid_from)"
        ),
        {
            "id": space_id,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "parent_id": parent_id,
            "space_type": space_type,
            "code": code,
            "name": name,
            "valid_from": valid_from,
        },
    )
    return space_id


def close_space(connection: Connection, *, space_id: uuid.UUID, valid_to: datetime) -> None:
    """Clôt un espace (démolition, rénovation, fusion). Il reste dans
    l'historique. Refusé tant qu'il contient encore quelque chose."""
    space = _require_open_space(connection, space_id)
    if valid_to <= space["valid_from"]:
        raise SpatialInvalid("SPACE_END_BEFORE_CREATION")

    open_children = connection.execute(
        text("SELECT 1 FROM spaces WHERE parent_id = :id AND valid_to IS NULL"), {"id": space_id}
    ).scalar()
    if open_children:
        raise SpatialConflict("SPACE_HAS_OPEN_CHILDREN")
    located = connection.execute(
        text("SELECT 1 FROM functional_locations WHERE space_id = :id"), {"id": space_id}
    ).scalar()
    if located:
        raise SpatialConflict("SPACE_HAS_FUNCTIONAL_LOCATIONS")

    connection.execute(
        text("UPDATE spaces SET valid_to = :valid_to WHERE id = :id"),
        {"valid_to": valid_to, "id": space_id},
    )


def list_spaces(
    connection: Connection, *, site_id: uuid.UUID | None = None, include_closed: bool = False
) -> list[dict[str, Any]]:
    query = f"SELECT {_SPACE_COLUMNS} FROM spaces WHERE true"
    params: dict[str, Any] = {}
    if site_id is not None:
        query += " AND site_id = :site_id"
        params["site_id"] = site_id
    if not include_closed:
        query += " AND valid_to IS NULL"
    query += " ORDER BY code"
    return [dict(row) for row in connection.execute(text(query), params).mappings()]


def check_space_for_location(
    connection: Connection, *, space_id: uuid.UUID, site_id: uuid.UUID
) -> None:
    """Un espace peut accueillir une position s'il est ouvert et dans le même
    site (la base le garantit aussi par une clé étrangère composée)."""
    space = _require_open_space(connection, space_id)
    if space["site_id"] != site_id:
        raise SpatialConflict("SPACE_OTHER_SITE_THAN_LOCATION")


def record_location_space(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    functional_location_id: uuid.UUID,
    space_id: uuid.UUID | None,
    valid_from: datetime,
    changed_by: str,
    reason: str | None,
) -> None:
    """Place (ou retire, avec space_id=None) une position dans un espace.

    Même principe que les statuts d'ordres de travail : la valeur courante est
    mise à jour pour la lecture rapide, et une ligne d'historique jamais
    modifiée garde la trace du changement (règle « rien n'est écrasé »).
    """
    location = (
        connection.execute(
            text("SELECT site_id, space_id FROM functional_locations WHERE id = :id"),
            {"id": functional_location_id},
        )
        .mappings()
        .first()
    )
    if location is None:
        raise SpatialNotFound("FUNCTIONAL_LOCATION_NOT_FOUND")
    if space_id is not None:
        check_space_for_location(connection, space_id=space_id, site_id=location["site_id"])
    if space_id == location["space_id"]:
        raise SpatialConflict("LOCATION_ALREADY_IN_SPACE")

    last_change = connection.execute(
        text(
            "SELECT max(valid_from) FROM functional_location_space_history "
            "WHERE functional_location_id = :id"
        ),
        {"id": functional_location_id},
    ).scalar()
    if last_change is not None and valid_from <= last_change:
        raise SpatialInvalid("LOCATION_MOVE_BEFORE_PREVIOUS")

    connection.execute(
        text("UPDATE functional_locations SET space_id = :space_id WHERE id = :id"),
        {"space_id": space_id, "id": functional_location_id},
    )
    connection.execute(
        text(
            "INSERT INTO functional_location_space_history "
            "(id, tenant_id, functional_location_id, space_id, valid_from, changed_by, reason) "
            "VALUES (:id, :tenant_id, :functional_location_id, :space_id, :valid_from, "
            ":changed_by, :reason)"
        ),
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "functional_location_id": functional_location_id,
            "space_id": space_id,
            "valid_from": valid_from,
            "changed_by": changed_by,
            "reason": reason,
        },
    )


def location_space_history(
    connection: Connection, functional_location_id: uuid.UUID
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(
                "SELECT id, functional_location_id, space_id, valid_from, recorded_at, "
                "changed_by, reason FROM functional_location_space_history "
                "WHERE functional_location_id = :id ORDER BY valid_from"
            ),
            {"id": functional_location_id},
        ).mappings()
    ]
