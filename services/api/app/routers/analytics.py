import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, status
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
from app.findings import confirm_finding, displayed, get_finding, list_findings
from app.i18n import negotiate_locale
from app.monitoring import evaluate_data_freshness
from app.points import get_point
from app.schemas import (
    DesiredStateCreate,
    DesiredStateEnd,
    DesiredStateOut,
    FindingConfirmation,
    FindingOut,
    SignalHandlingUpdate,
    SignalHistoryOut,
    SignalNote,
    TrustOut,
)
from app.signals import acknowledge, get_axes, set_handling
from app.signals import history as signal_history
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


def _finding_out(connection: Connection, finding_id: uuid.UUID, request: Request) -> FindingOut:
    finding = get_finding(connection, finding_id)
    if finding is None:
        raise ApiError(404, "FINDING_NOT_FOUND")
    return FindingOut(**displayed(finding, _locale(request)))


def _locale(request: Request) -> str:
    return negotiate_locale(request.headers.get("accept-language"))


@router.get("/findings", response_model=list[FindingOut])
def list_findings_route(
    request: Request,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    handling_status: Literal["open", "in_progress", "closed", "false_positive"] | None = None,
    condition_state: Literal["active", "cleared"] | None = None,
    ack_state: Literal["unacknowledged", "acknowledged"] | None = None,
    kind: Literal["data_quality", "commissioning", "anomaly", "fault", "prediction"] | None = None,
    subject_node_id: uuid.UUID | None = None,
) -> list[FindingOut]:
    rows = list_findings(
        connection,
        handling_status=handling_status,
        condition_state=condition_state,
        ack_state=ack_state,
        kind=kind,
        subject_node_id=subject_node_id,
    )
    locale = _locale(request)
    return [FindingOut(**displayed(row, locale)) for row in rows]


@router.get("/findings/{finding_id}", response_model=FindingOut)
def read_finding(
    finding_id: uuid.UUID,
    request: Request,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> FindingOut:
    return _finding_out(connection, finding_id, request)


@router.get("/findings/{finding_id}/history", response_model=list[SignalHistoryOut])
def read_finding_history(
    finding_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[SignalHistoryOut]:
    get_axes(connection, "finding", finding_id)
    return [SignalHistoryOut(**row) for row in signal_history(connection, "finding", finding_id)]


def _audit_finding(connection, tenant_id, claims, action, finding_id, payload) -> None:
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action=action,
        entity_type="finding",
        entity_id=str(finding_id),
        payload=payload,
    )


@router.post("/findings/{finding_id}/acknowledge", response_model=FindingOut)
def acknowledge_finding(
    finding_id: uuid.UUID,
    body: SignalNote,
    request: Request,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> FindingOut:
    acknowledge(
        connection,
        kind="finding",
        tenant_id=tenant_id,
        signal_id=finding_id,
        changed_by=_actor(claims),
        note=body.note,
    )
    _audit_finding(connection, tenant_id, claims, "finding.acknowledged", finding_id, {})
    return _finding_out(connection, finding_id, request)


@router.patch("/findings/{finding_id}/handling", response_model=FindingOut)
def update_finding_handling(
    finding_id: uuid.UUID,
    body: SignalHandlingUpdate,
    request: Request,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> FindingOut:
    set_handling(
        connection,
        kind="finding",
        tenant_id=tenant_id,
        signal_id=finding_id,
        handling_status=body.handling_status,
        changed_by=_actor(claims),
        note=body.note,
    )
    _audit_finding(
        connection,
        tenant_id,
        claims,
        "finding.handling_changed",
        finding_id,
        {"handling_status": body.handling_status, "note": body.note},
    )
    return _finding_out(connection, finding_id, request)


@router.post("/findings/{finding_id}/confirm", response_model=FindingOut)
def confirm_finding_route(
    finding_id: uuid.UUID,
    body: FindingConfirmation,
    request: Request,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> FindingOut:
    """« Défaut confirmé » après vérification par une personne, avec ce qui a
    été vérifié. Jamais automatique, jamais pour une prédiction."""
    confirm_finding(
        connection,
        tenant_id=tenant_id,
        finding_id=finding_id,
        confirmed_by=_actor(claims),
        confirmed_at=datetime.now(UTC),
        note=body.note,
    )
    _audit_finding(
        connection, tenant_id, claims, "finding.confirmed", finding_id, {"note": body.note}
    )
    return _finding_out(connection, finding_id, request)


# --- Confiance ------------------------------------------------


@router.get("/points/{point_id}/trust", response_model=TrustOut)
def read_point_trust(
    point_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> TrustOut:
    """Score de confiance du point maintenant, avec le détail de son calcul.
    Une donnée périmée détectée ici lève ou referme une alerte (directive de
    Mohamed du 24/09/2026, voir app/monitoring.py)."""
    point = get_point(connection, point_id)
    if point is None:
        raise ApiError(404, "POINT_NOT_FOUND")
    at = datetime.now(UTC)
    trust = compute_trust(connection, point, at)
    evaluate_data_freshness(connection, tenant_id=tenant_id, point=point, trust=trust, at=at)
    return TrustOut(**trust)
