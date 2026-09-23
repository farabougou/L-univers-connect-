import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.desired_states import (
    DesiredStateInvalid,
    DesiredStateNotFound,
    declare_desired_state,
    end_desired_state,
    get_desired_state,
    list_desired_states,
)
from app.errors import ApiError, api_error
from app.findings import (
    FindingNotFound,
    change_finding_status,
    finding_history,
    get_finding,
    list_findings,
)
from app.points import get_point
from app.schemas import (
    DesiredStateCreate,
    DesiredStateEnd,
    DesiredStateOut,
    FindingOut,
    FindingStatusHistoryOut,
    FindingStatusUpdate,
    TrustOut,
)
from app.trust import compute_trust

router = APIRouter()

_MANAGE_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


# --- État souhaité (attentes déclarées) ------------------------------------------------


@router.post(
    "/points/{point_id}/desired-states",
    response_model=DesiredStateOut,
    status_code=status.HTTP_201_CREATED,
)
def declare_desired_state_route(
    point_id: uuid.UUID,
    body: DesiredStateCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> DesiredStateOut:
    try:
        desired_state_id = declare_desired_state(
            connection,
            tenant_id=tenant_id,
            point_id=point_id,
            value=body.value,
            valid_from=body.valid_from or datetime.now(UTC),
            daily_start=body.daily_start,
            daily_end=body.daily_end,
            timezone=body.timezone,
            reason=body.reason,
            created_by=_actor(claims),
        )
    except DesiredStateNotFound as exc:
        raise api_error(exc, 404) from exc
    except DesiredStateInvalid as exc:
        raise api_error(exc, 400) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="desired_state.declared",
        entity_type="desired_state",
        entity_id=str(desired_state_id),
        payload={"point_id": str(point_id), "value": body.value, "reason": body.reason},
    )
    return DesiredStateOut(**get_desired_state(connection, desired_state_id))


@router.get("/points/{point_id}/desired-states", response_model=list[DesiredStateOut])
def list_desired_states_route(
    point_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    include_ended: bool = False,
) -> list[DesiredStateOut]:
    if get_point(connection, point_id) is None:
        raise ApiError(404, "POINT_NOT_FOUND")
    rows = list_desired_states(connection, point_id, include_ended=include_ended)
    return [DesiredStateOut(**row) for row in rows]


@router.post("/desired-states/{desired_state_id}/end", response_model=DesiredStateOut)
def end_desired_state_route(
    desired_state_id: uuid.UUID,
    body: DesiredStateEnd,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> DesiredStateOut:
    valid_to = body.valid_to or datetime.now(UTC)
    try:
        end_desired_state(connection, desired_state_id=desired_state_id, valid_to=valid_to)
    except DesiredStateNotFound as exc:
        raise api_error(exc, 404) from exc
    except DesiredStateInvalid as exc:
        raise api_error(exc, 409) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="desired_state.ended",
        entity_type="desired_state",
        entity_id=str(desired_state_id),
        payload={"valid_to": valid_to.isoformat()},
    )
    return DesiredStateOut(**get_desired_state(connection, desired_state_id))


# --- Constats ------------------------------------------------


@router.get("/findings", response_model=list[FindingOut])
def list_findings_route(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    status_filter: Annotated[
        Literal["open", "acknowledged", "resolved", "false_positive"] | None,
        Query(alias="status"),
    ] = None,
    kind: Literal["data_quality", "commissioning", "anomaly", "fault", "prediction"] | None = None,
    subject_node_id: uuid.UUID | None = None,
) -> list[FindingOut]:
    rows = list_findings(
        connection, status=status_filter, kind=kind, subject_node_id=subject_node_id
    )
    return [FindingOut(**row) for row in rows]


@router.get("/findings/{finding_id}", response_model=FindingOut)
def read_finding(
    finding_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> FindingOut:
    finding = get_finding(connection, finding_id)
    if finding is None:
        raise ApiError(404, "FINDING_NOT_FOUND")
    return FindingOut(**finding)


@router.get("/findings/{finding_id}/history", response_model=list[FindingStatusHistoryOut])
def read_finding_history(
    finding_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[FindingStatusHistoryOut]:
    if get_finding(connection, finding_id) is None:
        raise ApiError(404, "FINDING_NOT_FOUND")
    return [FindingStatusHistoryOut(**row) for row in finding_history(connection, finding_id)]


@router.patch("/findings/{finding_id}/status", response_model=FindingOut)
def update_finding_status(
    finding_id: uuid.UUID,
    body: FindingStatusUpdate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> FindingOut:
    try:
        change_finding_status(
            connection,
            tenant_id=tenant_id,
            finding_id=finding_id,
            status=body.status,
            changed_by=_actor(claims),
            note=body.note,
        )
    except FindingNotFound as exc:
        raise api_error(exc, 404) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="finding.status_changed",
        entity_type="finding",
        entity_id=str(finding_id),
        payload={"status": body.status, "note": body.note},
    )
    return FindingOut(**get_finding(connection, finding_id))


# --- Confiance ------------------------------------------------


@router.get("/points/{point_id}/trust", response_model=TrustOut)
def read_point_trust(
    point_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> TrustOut:
    """Score de confiance du point maintenant, avec le détail de son calcul."""
    point = get_point(connection, point_id)
    if point is None:
        raise ApiError(404, "POINT_NOT_FOUND")
    return TrustOut(**compute_trust(connection, point, datetime.now(UTC)))
