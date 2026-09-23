import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.point_vocabulary import PointVocabularyError
from app.points import (
    PointConflict,
    PointNotFound,
    create_point,
    decide_point,
    get_point,
    identify_point,
    list_points,
)
from app.schemas import PointCreate, PointDecision, PointOut, PointUpdate

router = APIRouter()

_MANAGE_REGISTRY_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PointNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, PointConflict):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


_ERRORS = (PointNotFound, PointConflict, PointVocabularyError)


@router.post("/points", response_model=PointOut, status_code=status.HTTP_201_CREATED)
def create_point_route(
    body: PointCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> PointOut:
    try:
        point_id = create_point(
            connection, tenant_id=tenant_id, created_by=_actor(claims), **body.model_dump()
        )
    except _ERRORS as exc:
        raise _http_error(exc) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="point.created",
        entity_type="point",
        entity_id=str(point_id),
        payload={"code": body.code, "point_class": body.point_class},
    )
    return PointOut(**get_point(connection, point_id))


@router.get("/points", response_model=list[PointOut])
def list_points_route(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    functional_location_id: uuid.UUID | None = None,
    space_id: uuid.UUID | None = None,
    mapping_status: Literal["proposed", "validated", "rejected"] | None = None,
) -> list[PointOut]:
    points = list_points(
        connection,
        functional_location_id=functional_location_id,
        space_id=space_id,
        mapping_status=mapping_status,
    )
    return [PointOut(**point) for point in points]


@router.get("/points/{point_id}", response_model=PointOut)
def read_point(
    point_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> PointOut:
    point = get_point(connection, point_id)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="point introuvable")
    return PointOut(**point)


@router.patch("/points/{point_id}", response_model=PointOut)
def identify_point_route(
    point_id: uuid.UUID,
    body: PointUpdate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> PointOut:
    changes = body.model_dump(exclude_unset=True)
    try:
        identify_point(connection, point_id=point_id, changes=changes)
    except _ERRORS as exc:
        raise _http_error(exc) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="point.identified",
        entity_type="point",
        entity_id=str(point_id),
        payload={field: str(value) for field, value in changes.items()},
    )
    return PointOut(**get_point(connection, point_id))


def _decide(
    decision: str,
    point_id: uuid.UUID,
    body: PointDecision,
    connection: Connection,
    tenant_id: uuid.UUID,
    claims: dict,
) -> PointOut:
    try:
        decide_point(connection, point_id=point_id, decision=decision)
    except _ERRORS as exc:
        raise _http_error(exc) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action=f"point.{decision}",
        entity_type="point",
        entity_id=str(point_id),
        payload={"reason": body.reason},
    )
    return PointOut(**get_point(connection, point_id))


@router.post("/points/{point_id}/validate", response_model=PointOut)
def validate_point_route(
    point_id: uuid.UUID,
    body: PointDecision,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> PointOut:
    """Mise en service : le point devient fiable et sa description est figée."""
    return _decide("validated", point_id, body, connection, tenant_id, claims)


@router.post("/points/{point_id}/reject", response_model=PointOut)
def reject_point_route(
    point_id: uuid.UUID,
    body: PointDecision,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> PointOut:
    if not body.reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="une raison est obligatoire pour rejeter un point",
        )
    return _decide("rejected", point_id, body, connection, tenant_id, claims)
