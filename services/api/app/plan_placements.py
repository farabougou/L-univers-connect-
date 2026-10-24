"""Placement des actifs sur un plan (ADR 011, étape S4) : « tel espace /
telle position / tel point est dessiné ici, à ces coordonnées normalisées,
sur telle version de plan ». Aucun nom, aucune caractéristique d'équipement
n'est stocké ici : tout est lu depuis le registre au moment de l'affichage.
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError

_COLUMNS = (
    "id, floor_plan_id, space_id, functional_location_id, point_id, "
    "x_ratio, y_ratio, status, created_by, created_at, validated_by, validated_at"
)


class PlacementNotFound(DomainError, LookupError):
    status = 404


class PlacementConflict(DomainError, ValueError):
    status = 409


class PlacementInvalid(DomainError, ValueError):
    status = 422


def record_placement(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    space_id: uuid.UUID | None,
    functional_location_id: uuid.UUID | None,
    point_id: uuid.UUID | None,
    x_ratio: float,
    y_ratio: float,
    created_by: str,
) -> uuid.UUID:
    targets = (space_id, functional_location_id, point_id)
    if sum(1 for target in targets if target is not None) != 1:
        raise PlacementInvalid("PLAN_PLACEMENT_EXACTLY_ONE_TARGET")

    placement_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO plan_placements
                (id, tenant_id, floor_plan_id, space_id, functional_location_id, point_id,
                 x_ratio, y_ratio, created_by)
            VALUES
                (:id, :tenant_id, :floor_plan_id, :space_id, :functional_location_id, :point_id,
                 :x_ratio, :y_ratio, :created_by)
            """
        ),
        {
            "id": placement_id,
            "tenant_id": tenant_id,
            "floor_plan_id": floor_plan_id,
            "space_id": space_id,
            "functional_location_id": functional_location_id,
            "point_id": point_id,
            "x_ratio": x_ratio,
            "y_ratio": y_ratio,
            "created_by": created_by,
        },
    )
    return placement_id


def get_placement(connection: Connection, placement_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM plan_placements WHERE id = :id"), {"id": placement_id}
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_placements(connection: Connection, floor_plan_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"SELECT {_COLUMNS} FROM plan_placements "
            "WHERE floor_plan_id = :floor_plan_id ORDER BY created_at"
        ),
        {"floor_plan_id": floor_plan_id},
    ).mappings()
    return [dict(row) for row in rows]


def validate_placement(
    connection: Connection, *, placement_id: uuid.UUID, validated_by: str
) -> None:
    result = connection.execute(
        text(
            """
            UPDATE plan_placements
            SET status = 'validated', validated_by = :validated_by, validated_at = now()
            WHERE id = :id AND status = 'proposed'
            """
        ),
        {"id": placement_id, "validated_by": validated_by},
    )
    if result.rowcount == 0:
        existing = get_placement(connection, placement_id)
        if existing is None:
            raise PlacementNotFound("PLAN_PLACEMENT_NOT_FOUND")
        raise PlacementConflict("PLAN_PLACEMENT_ALREADY_VALIDATED")


def delete_placement(connection: Connection, placement_id: uuid.UUID) -> None:
    result = connection.execute(
        text("DELETE FROM plan_placements WHERE id = :id"), {"id": placement_id}
    )
    if result.rowcount == 0:
        raise PlacementNotFound("PLAN_PLACEMENT_NOT_FOUND")
