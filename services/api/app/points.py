"""Points de télémétrie (ADR 012, étape F3).

Cycle de mise en service : un point est créé « proposed » (découvert ou saisi,
pas encore fiable), peut être identifié et corrigé tant qu'il l'est, puis est
validé (fiable, description figée) ou rejeté. La base empêche toute
modification après décision, et interdit qu'un point soit inscriptible.
"""

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError
from app.point_vocabulary import check_point_definition, check_point_ready_for_validation

POINT_COLUMNS = (
    "id, functional_location_id, space_id, code, name, point_class, kind, value_type, unit, "
    "states, expected_interval_seconds, min_value, max_value, is_writable, mapping_status, "
    "mapping_confidence, created_by, created_at"
)

_EDITABLE_FIELDS = (
    "name",
    "point_class",
    "value_type",
    "unit",
    "states",
    "functional_location_id",
    "space_id",
    "expected_interval_seconds",
    "min_value",
    "max_value",
    "mapping_confidence",
)


class PointNotFound(DomainError, LookupError):
    status = 404


class PointConflict(DomainError, ValueError):
    status = 409


class PointInvalid(DomainError, ValueError):
    pass


def get_point(connection: Connection, point_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {POINT_COLUMNS} FROM points WHERE id = :id"), {"id": point_id}
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _require_point(connection: Connection, point_id: uuid.UUID) -> dict[str, Any]:
    point = get_point(connection, point_id)
    if point is None:
        raise PointNotFound("POINT_NOT_FOUND")
    return point


def _check_anchors(
    connection: Connection,
    *,
    functional_location_id: uuid.UUID | None,
    space_id: uuid.UUID | None,
) -> None:
    """Les rattachements existent pour ce tenant (lecture sous RLS) et, s'il y en
    a deux, sont sur le même site."""
    location_site = space_site = None
    if functional_location_id is not None:
        location_site = connection.execute(
            text("SELECT site_id FROM functional_locations WHERE id = :id"),
            {"id": functional_location_id},
        ).scalar()
        if location_site is None:
            raise PointNotFound("FUNCTIONAL_LOCATION_NOT_FOUND")
    if space_id is not None:
        space = (
            connection.execute(
                text("SELECT site_id, valid_to FROM spaces WHERE id = :id"), {"id": space_id}
            )
            .mappings()
            .first()
        )
        if space is None:
            raise PointNotFound("SPACE_NOT_FOUND")
        if space["valid_to"] is not None:
            raise PointConflict("SPACE_ENDED")
        space_site = space["site_id"]
    if location_site and space_site and location_site != space_site:
        raise PointConflict("POINT_SITE_MISMATCH")


def create_point(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    code: str,
    name: str,
    value_type: str,
    created_by: str,
    point_class: str | None = None,
    unit: str | None = None,
    states: dict[str, str] | None = None,
    functional_location_id: uuid.UUID | None = None,
    space_id: uuid.UUID | None = None,
    expected_interval_seconds: int | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    mapping_confidence: float | None = None,
) -> uuid.UUID:
    definition = check_point_definition(
        point_class=point_class, value_type=value_type, unit=unit, states=states
    )
    _check_anchors(connection, functional_location_id=functional_location_id, space_id=space_id)
    code_taken = connection.execute(
        text("SELECT 1 FROM points WHERE code = :code"), {"code": code}
    ).scalar()
    if code_taken:
        raise PointConflict("POINT_CODE_ALREADY_USED", code=code)

    point_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO points (id, tenant_id, functional_location_id, space_id, code, name, "
            "point_class, kind, value_type, unit, states, expected_interval_seconds, "
            "min_value, max_value, mapping_confidence, created_by) VALUES (:id, :tenant_id, "
            ":functional_location_id, :space_id, :code, :name, :point_class, :kind, "
            ":value_type, :unit, CAST(:states AS JSONB), :expected_interval_seconds, "
            ":min_value, :max_value, :mapping_confidence, :created_by)"
        ),
        {
            "id": point_id,
            "tenant_id": tenant_id,
            "functional_location_id": functional_location_id,
            "space_id": space_id,
            "code": code,
            "name": name,
            "point_class": point_class,
            "kind": definition.kind if definition else None,
            "value_type": value_type,
            "unit": unit,
            "states": _json(states),
            "expected_interval_seconds": expected_interval_seconds,
            "min_value": min_value,
            "max_value": max_value,
            "mapping_confidence": mapping_confidence,
            "created_by": created_by,
        },
    )
    return point_id


def identify_point(connection: Connection, *, point_id: uuid.UUID, changes: dict[str, Any]) -> None:
    """Complète ou corrige un point encore « proposed » (identification lors
    de la mise en service). Refusé une fois le point validé ou rejeté."""
    point = _require_point(connection, point_id)
    if point["mapping_status"] != "proposed":
        raise PointConflict("POINT_NOT_EDITABLE", status=point["mapping_status"])
    unknown = set(changes) - set(_EDITABLE_FIELDS)
    if unknown:
        raise PointConflict("POINT_FIELDS_NOT_EDITABLE", fields=sorted(unknown))

    merged = {**point, **changes}
    definition = check_point_definition(
        point_class=merged["point_class"],
        value_type=merged["value_type"],
        unit=merged["unit"],
        states=merged["states"],
    )
    _check_anchors(
        connection,
        functional_location_id=merged["functional_location_id"],
        space_id=merged["space_id"],
    )
    merged["kind"] = definition.kind if definition else None

    assignments = ", ".join(
        f"{field} = CAST(:{field} AS JSONB)" if field == "states" else f"{field} = :{field}"
        for field in (*_EDITABLE_FIELDS, "kind")
    )
    params = {field: merged[field] for field in (*_EDITABLE_FIELDS, "kind")}
    params["states"] = _json(merged["states"])
    params["id"] = point_id
    connection.execute(text(f"UPDATE points SET {assignments} WHERE id = :id"), params)


def decide_point(connection: Connection, *, point_id: uuid.UUID, decision: str) -> None:
    """Valide (le point devient fiable) ou rejette un point proposé."""
    if decision not in ("validated", "rejected"):
        raise PointInvalid("POINT_DECISION_UNKNOWN", decision=decision)
    point = _require_point(connection, point_id)
    if point["mapping_status"] != "proposed":
        raise PointConflict("POINT_ALREADY_DECIDED", status=point["mapping_status"])
    if decision == "validated":
        check_point_ready_for_validation(
            point_class=point["point_class"],
            value_type=point["value_type"],
            unit=point["unit"],
            states=point["states"],
            has_anchor=bool(point["functional_location_id"] or point["space_id"]),
        )
    connection.execute(
        text("UPDATE points SET mapping_status = :decision WHERE id = :id"),
        {"decision": decision, "id": point_id},
    )


def list_points(
    connection: Connection,
    *,
    functional_location_id: uuid.UUID | None = None,
    space_id: uuid.UUID | None = None,
    mapping_status: str | None = None,
) -> list[dict[str, Any]]:
    query = f"SELECT {POINT_COLUMNS} FROM points WHERE true"
    params: dict[str, Any] = {}
    for column, value in (
        ("functional_location_id", functional_location_id),
        ("space_id", space_id),
        ("mapping_status", mapping_status),
    ):
        if value is not None:
            query += f" AND {column} = :{column}"
            params[column] = value
    query += " ORDER BY code"
    return [dict(row) for row in connection.execute(text(query), params).mappings()]


def _json(value: dict | None) -> str | None:
    return None if value is None else json.dumps(value, sort_keys=True)
