import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.graph import (
    NodeNotFound,
    RelationConflict,
    RelationNotFound,
    create_relation,
    end_relation,
    get_node,
    list_node_relations,
)
from app.graph_vocabulary import VocabularyError
from app.schemas import GraphNodeOut, RelationCreate, RelationEnd, RelationOut

router = APIRouter()

_MANAGE_GRAPH_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


@router.get("/graph/nodes/{node_id}", response_model=GraphNodeOut)
def read_node(
    node_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> GraphNodeOut:
    node = get_node(connection, node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="nœud introuvable")
    return GraphNodeOut(**node)


@router.get("/graph/nodes/{node_id}/relations", response_model=list[RelationOut])
def read_node_relations(
    node_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    include_ended: bool = False,
) -> list[RelationOut]:
    try:
        edges = list_node_relations(connection, node_id, include_ended=include_ended)
    except NodeNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="nœud introuvable"
        ) from exc
    return [RelationOut(**edge) for edge in edges]


@router.post("/relations", response_model=RelationOut, status_code=status.HTTP_201_CREATED)
def create_relation_route(
    body: RelationCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_GRAPH_ROLES))],
) -> RelationOut:
    try:
        relation_id = create_relation(
            connection,
            tenant_id=tenant_id,
            subject_id=body.subject_id,
            predicate=body.predicate,
            object_id=body.object_id,
            created_by=_actor(claims),
            valid_from=body.valid_from or datetime.now(UTC),
            confidence=body.confidence,
        )
    except NodeNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="nœud introuvable"
        ) from exc
    except VocabularyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RelationConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="relation.created",
        entity_type="relation",
        entity_id=str(relation_id),
        payload={
            "subject_id": str(body.subject_id),
            "predicate": body.predicate,
            "object_id": str(body.object_id),
        },
    )
    return _read_relation_from_subject(connection, body.subject_id, relation_id)


@router.post("/relations/{relation_id}/end", response_model=RelationOut)
def end_relation_route(
    relation_id: uuid.UUID,
    body: RelationEnd,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_GRAPH_ROLES))],
) -> RelationOut:
    valid_to = body.valid_to or datetime.now(UTC)
    try:
        subject_id = end_relation(connection, relation_id=relation_id, valid_to=valid_to)
    except RelationNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="relation introuvable"
        ) from exc
    except RelationConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="relation.ended",
        entity_type="relation",
        entity_id=str(relation_id),
        payload={"valid_to": valid_to.isoformat(), "reason": body.reason},
    )
    return _read_relation_from_subject(connection, subject_id, relation_id)


def _read_relation_from_subject(
    connection: Connection, subject_id: uuid.UUID, relation_id: uuid.UUID
) -> RelationOut:
    edges = list_node_relations(connection, subject_id, include_ended=True)
    edge = next(edge for edge in edges if edge["id"] == relation_id)
    return RelationOut(**edge)
