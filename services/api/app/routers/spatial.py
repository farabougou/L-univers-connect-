import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.schemas import (
    LocationSpaceChange,
    LocationSpaceHistoryOut,
    SpaceClose,
    SpaceCreate,
    SpaceOut,
)
from app.spatial import (
    SpatialConflict,
    SpatialNotFound,
    close_space,
    create_space,
    get_space,
    list_spaces,
    location_space_history,
    record_location_space,
)
from app.spatial_vocabulary import SpatialVocabularyError

router = APIRouter()

_MANAGE_REGISTRY_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SpatialNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, SpatialConflict):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/spaces", response_model=SpaceOut, status_code=status.HTTP_201_CREATED)
def create_space_route(
    body: SpaceCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> SpaceOut:
    try:
        space_id = create_space(
            connection,
            tenant_id=tenant_id,
            site_id=body.site_id,
            parent_id=body.parent_id,
            space_type=body.space_type,
            code=body.code,
            name=body.name,
            valid_from=body.valid_from or datetime.now(UTC),
        )
    except (SpatialNotFound, SpatialConflict, SpatialVocabularyError) as exc:
        raise _http_error(exc) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="space.created",
        entity_type="space",
        entity_id=str(space_id),
        payload={"space_type": body.space_type, "code": body.code, "name": body.name},
    )
    return SpaceOut(**get_space(connection, space_id))


@router.get("/spaces", response_model=list[SpaceOut])
def list_spaces_route(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    site_id: uuid.UUID | None = None,
    include_closed: bool = False,
) -> list[SpaceOut]:
    spaces = list_spaces(connection, site_id=site_id, include_closed=include_closed)
    return [SpaceOut(**space) for space in spaces]


@router.post("/spaces/{space_id}/close", response_model=SpaceOut)
def close_space_route(
    space_id: uuid.UUID,
    body: SpaceClose,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> SpaceOut:
    valid_to = body.valid_to or datetime.now(UTC)
    try:
        close_space(connection, space_id=space_id, valid_to=valid_to)
    except (SpatialNotFound, SpatialConflict, ValueError) as exc:
        raise _http_error(exc) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="space.closed",
        entity_type="space",
        entity_id=str(space_id),
        payload={"valid_to": valid_to.isoformat(), "reason": body.reason},
    )
    return SpaceOut(**get_space(connection, space_id))


@router.post(
    "/functional-locations/{functional_location_id}/space",
    response_model=list[LocationSpaceHistoryOut],
)
def change_location_space(
    functional_location_id: uuid.UUID,
    body: LocationSpaceChange,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> list[LocationSpaceHistoryOut]:
    """Place une position dans un espace (ou l'en retire) et renvoie tout son
    historique d'emplacements, le nouveau compris."""
    valid_from = body.valid_from or datetime.now(UTC)
    try:
        record_location_space(
            connection,
            tenant_id=tenant_id,
            functional_location_id=functional_location_id,
            space_id=body.space_id,
            valid_from=valid_from,
            changed_by=_actor(claims),
            reason=body.reason,
        )
    except (SpatialNotFound, SpatialConflict, ValueError) as exc:
        raise _http_error(exc) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="functional_location.space_changed",
        entity_type="functional_location",
        entity_id=str(functional_location_id),
        payload={
            "space_id": str(body.space_id) if body.space_id else None,
            "valid_from": valid_from.isoformat(),
            "reason": body.reason,
        },
    )
    return [
        LocationSpaceHistoryOut(**row)
        for row in location_space_history(connection, functional_location_id)
    ]


@router.get(
    "/functional-locations/{functional_location_id}/space-history",
    response_model=list[LocationSpaceHistoryOut],
)
def read_location_space_history(
    functional_location_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[LocationSpaceHistoryOut]:
    exists = connection.execute(
        text("SELECT 1 FROM functional_locations WHERE id = :id"), {"id": functional_location_id}
    ).scalar()
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="position fonctionnelle introuvable"
        )
    return [
        LocationSpaceHistoryOut(**row)
        for row in location_space_history(connection, functional_location_id)
    ]
