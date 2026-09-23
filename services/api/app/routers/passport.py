import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.passport import build_passport
from app.properties import PropertyError, PropertyNotFound, list_properties, set_property
from app.schemas import PropertyOut, PropertySet, TagCreate, TagOut, TagRevoke
from app.tags import TagNotFound, TagRevoked, create_tag, list_tags, resolve_tag, revoke_tag

router = APIRouter()

_MANAGE_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


def _roles(claims: dict[str, Any]) -> set[str]:
    return set(claims.get("realm_access", {}).get("roles", []))


def _passport_or_404(connection: Connection, node_id: uuid.UUID, claims: dict) -> dict:
    passport = build_passport(connection, node_id, _roles(claims))
    if passport is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="nœud introuvable")
    return passport


# --- Passeport numérique ------------------------------------------------


@router.get("/graph/nodes/{node_id}/passport")
def read_passport(
    node_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> dict[str, Any]:
    return _passport_or_404(connection, node_id, claims)


@router.get("/tags/{code}")
def scan_tag(
    code: str,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> dict[str, Any]:
    """Ce qu'affiche l'application après avoir scanné un QR ou un NFC. Un code
    d'un autre client est « inconnu » ; un code révoqué est signalé (410)."""
    try:
        tag = resolve_tag(connection, code)
    except TagNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TagRevoked as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    return {"tag": TagOut(**tag), "passport": _passport_or_404(connection, tag["node_id"], claims)}


# --- Étiquettes ------------------------------------------------


@router.post(
    "/graph/nodes/{node_id}/tags", response_model=TagOut, status_code=status.HTTP_201_CREATED
)
def create_tag_route(
    node_id: uuid.UUID,
    body: TagCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> TagOut:
    try:
        tag = create_tag(
            connection,
            tenant_id=tenant_id,
            node_id=node_id,
            tag_type=body.tag_type,
            created_by=_actor(claims),
        )
    except TagNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="tag.created",
        entity_type="asset_tag",
        entity_id=str(tag["id"]),
        payload={"node_id": str(node_id), "tag_type": body.tag_type},
    )
    return TagOut(**tag)


@router.get("/graph/nodes/{node_id}/tags", response_model=list[TagOut])
def list_tags_route(
    node_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> list[TagOut]:
    return [TagOut(**tag) for tag in list_tags(connection, node_id)]


@router.post("/tags/{code}/revoke", response_model=TagOut)
def revoke_tag_route(
    code: str,
    body: TagRevoke,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> TagOut:
    try:
        tag = revoke_tag(
            connection,
            code=code,
            revoked_by=_actor(claims),
            reason=body.reason,
            revoked_at=datetime.now(UTC),
        )
    except TagNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TagRevoked as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="tag.revoked",
        entity_type="asset_tag",
        entity_id=str(tag["id"]),
        payload={"reason": body.reason},
    )
    return TagOut(**tag)


# --- Propriétés techniques ------------------------------------------------


@router.post(
    "/graph/nodes/{node_id}/properties",
    response_model=PropertyOut,
    status_code=status.HTTP_201_CREATED,
)
def set_property_route(
    node_id: uuid.UUID,
    body: PropertySet,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> PropertyOut:
    """Nouvelle valeur d'une propriété : l'ancienne est close à cette date,
    jamais écrasée."""
    try:
        property_id = set_property(
            connection,
            tenant_id=tenant_id,
            node_id=node_id,
            key=body.key,
            value=body.value,
            unit=body.unit,
            source=body.source,
            valid_from=body.valid_from or datetime.now(UTC),
            reason=body.reason,
            created_by=_actor(claims),
        )
    except PropertyNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PropertyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="property.set",
        entity_type="graph_node",
        entity_id=str(node_id),
        payload={"key": body.key, "value": body.value, "unit": body.unit, "reason": body.reason},
    )
    rows = list_properties(connection, node_id)
    return PropertyOut(**next(row for row in rows if row["id"] == property_id))


@router.get("/graph/nodes/{node_id}/properties", response_model=list[PropertyOut])
def list_properties_route(
    node_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    include_history: bool = False,
) -> list[PropertyOut]:
    return [
        PropertyOut(**row)
        for row in list_properties(connection, node_id, include_history=include_history)
    ]
