"""Commandes vers un appareil explicitement simulé — exception scopée à la
règle non négociable 1 (voir CLAUDE.md, décision de Mohamed du 24/09/2026,
et app/commands.py pour le détail des garde-fous).
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import get_current_claims, require_any_role, require_device_scope
from app.commands import (
    CommandConflict,
    CommandNotAllowed,
    CommandNotFound,
    acknowledge_command,
    claim_pending_commands,
    create_command,
    effective_status,
    get_command,
    list_commands_for_point,
)
from app.db import engine
from app.deps import get_tenant_connection, get_tenant_id
from app.errors import api_error
from app.monitoring import evaluate_command_timeout
from app.tenancy import set_tenant_context

router = APIRouter()

_COMMAND_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


class CommandCreate(BaseModel):
    point_id: uuid.UUID
    requested_value: float


class CommandOut(BaseModel):
    id: uuid.UUID
    point_id: uuid.UUID
    requested_value: float
    requested_by: str
    status: str
    actual_value: float | None
    failure_reason: str | None
    created_at: datetime
    sent_at: datetime | None
    acknowledged_at: datetime | None
    verified_at: datetime | None
    edge_device_id: uuid.UUID | None


class EdgeCommandOut(BaseModel):
    id: uuid.UUID
    point_id: uuid.UUID
    requested_value: float


class CommandAck(BaseModel):
    success: bool
    actual_value: float | None = None
    failure_reason: str | None = Field(default=None, max_length=200)


def _actor(claims: dict) -> str:
    return claims.get("sub") or "inconnu"


def _out(command: dict, *, now: datetime) -> CommandOut:
    return CommandOut(**{**command, "status": effective_status(command, now=now)})


@router.post("/commands", response_model=CommandOut, status_code=201)
def create_command_route(
    body: CommandCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_COMMAND_ROLES))],
) -> CommandOut:
    actor = _actor(claims)
    try:
        command_id = create_command(
            connection,
            tenant_id=tenant_id,
            point_id=body.point_id,
            requested_value=body.requested_value,
            requested_by=actor,
        )
    except CommandNotAllowed as exc:
        raise api_error(exc, 422) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=actor,
        action="command.created",
        entity_type="command",
        entity_id=str(command_id),
        payload={"point_id": str(body.point_id), "requested_value": body.requested_value},
    )
    return _out(get_command(connection, command_id), now=datetime.now(UTC))


@router.get("/commands/{command_id}", response_model=CommandOut)
def get_command_route(
    command_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(get_current_claims)],
) -> CommandOut:
    command = get_command(connection, command_id)
    if command is None:
        raise api_error(CommandNotFound("COMMAND_NOT_FOUND", command_id=str(command_id)), 404)
    now = datetime.now(UTC)
    command = evaluate_command_timeout(connection, tenant_id=tenant_id, command=command, at=now)
    return _out(command, now=now)


@router.get("/commands", response_model=list[CommandOut])
def list_commands_route(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(get_current_claims)],
    point_id: Annotated[uuid.UUID, Query()],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[CommandOut]:
    now = datetime.now(UTC)
    commands = [
        evaluate_command_timeout(connection, tenant_id=tenant_id, command=command, at=now)
        for command in list_commands_for_point(connection, point_id=point_id, limit=limit)
    ]
    return [_out(command, now=now) for command in commands]


@router.get("/edge/commands", response_model=list[EdgeCommandOut])
def get_edge_commands(
    equipment_id: uuid.UUID,
    claims: Annotated[dict, Depends(require_device_scope("command:execute"))],
) -> list[EdgeCommandOut]:
    """Récupère (et marque « sent ») les commandes en attente pour cet
    équipement — jamais renvoyées une seconde fois (voir claim_pending_commands)."""
    tenant_id = uuid.UUID(claims["tenant_id"])
    device_id = uuid.UUID(claims["device_id"])
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        claimed = claim_pending_commands(
            connection, equipment_id=equipment_id, edge_device_id=device_id, at=datetime.now(UTC)
        )
    return [EdgeCommandOut(**command) for command in claimed]


@router.post("/edge/commands/{command_id}/ack", response_model=CommandOut)
def acknowledge_command_route(
    command_id: uuid.UUID,
    body: CommandAck,
    claims: Annotated[dict, Depends(require_device_scope("command:execute"))],
) -> CommandOut:
    tenant_id = uuid.UUID(claims["tenant_id"])
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        try:
            command = acknowledge_command(
                connection,
                command_id=command_id,
                success=body.success,
                actual_value=body.actual_value,
                failure_reason=body.failure_reason,
                at=datetime.now(UTC),
            )
        except (CommandNotFound, CommandConflict) as exc:
            raise api_error(exc, exc.status) from exc

        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor=f"edge:{claims['device_id']}",
            action="command.acknowledged",
            entity_type="command",
            entity_id=str(command_id),
            payload={
                "success": body.success,
                "actual_value": body.actual_value,
                "status": command["status"],
                "failure_reason": command["failure_reason"],
            },
        )
    return _out(command, now=datetime.now(UTC))
