import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.closure_vocabulary import (
    ACTIONS,
    CAUSES,
    CLOSURE_VOCABULARY_VERSION,
    SYMPTOMS,
    VERIFICATION_RESULTS,
)
from app.closures import (
    ClosureConflict,
    ClosureError,
    ClosureNotFound,
    close_intervention,
    get_closure,
)
from app.deps import get_tenant_connection, get_tenant_id
from app.errors import ApiError, api_error
from app.maintenance import (
    ClientRefConflict,
    change_work_order_status,
    create_work_order,
    log_intervention,
    log_intervention_once,
    raise_alarm,
    record_photo,
    record_photo_once,
)
from app.schemas import (
    AlarmCreate,
    AlarmOut,
    ClosureCreate,
    ClosureOut,
    HandlingStatus,
    InterventionCreate,
    InterventionOut,
    PhotoCreate,
    PhotoOut,
    PhotoUploadUrlOut,
    PhotoUploadUrlRequest,
    SignalHandlingUpdate,
    SignalHistoryOut,
    SignalNote,
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderStatusHistoryOut,
    WorkOrderStatusUpdate,
)
from app.signals import acknowledge, clear_condition, get_axes, set_handling
from app.signals import history as signal_history
from app.storage import (
    build_object_key,
    create_presigned_download_url,
    create_presigned_upload_url,
    key_belongs_to,
)

router = APIRouter()

_PLAN_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


def _check_targets_exist(
    connection: Connection,
    *,
    functional_location_id: uuid.UUID | None,
    physical_unit_id: uuid.UUID | None,
) -> None:
    if functional_location_id is not None:
        exists = connection.execute(
            text("SELECT 1 FROM functional_locations WHERE id = :id"),
            {"id": functional_location_id},
        ).scalar()
        if not exists:
            raise ApiError(404, "FUNCTIONAL_LOCATION_NOT_FOUND")
    if physical_unit_id is not None:
        exists = connection.execute(
            text("SELECT 1 FROM physical_units WHERE id = :id"), {"id": physical_unit_id}
        ).scalar()
        if not exists:
            raise ApiError(404, "PHYSICAL_UNIT_NOT_FOUND")


# --- Ordres de travail ------------------------------------------------


@router.post("/work-orders", response_model=WorkOrderOut, status_code=status.HTTP_201_CREATED)
def create_work_order_route(
    body: WorkOrderCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_PLAN_ROLES))],
) -> WorkOrderOut:
    _check_targets_exist(
        connection,
        functional_location_id=body.functional_location_id,
        physical_unit_id=body.physical_unit_id,
    )

    work_order_id = create_work_order(
        connection,
        tenant_id=tenant_id,
        created_by=_actor(claims),
        title=body.title,
        description=body.description,
        work_order_type=body.work_order_type,
        priority=body.priority,
        functional_location_id=body.functional_location_id,
        physical_unit_id=body.physical_unit_id,
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="work_order.created",
        entity_type="work_order",
        entity_id=str(work_order_id),
        payload={
            "title": body.title,
            "priority": body.priority,
            "work_order_type": body.work_order_type,
        },
    )
    return _read_work_order(connection, work_order_id)


@router.get("/work-orders", response_model=list[WorkOrderOut])
def list_work_orders(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[WorkOrderOut]:
    rows = (
        connection.execute(
            text(
                "SELECT id, functional_location_id, physical_unit_id, title, description, "
                "work_order_type, priority, status, created_by, created_at "
                "FROM work_orders ORDER BY created_at"
            )
        )
        .mappings()
        .all()
    )
    return [WorkOrderOut(**row) for row in rows]


@router.patch(
    "/work-orders/{work_order_id}/status",
    response_model=WorkOrderOut,
)
def update_work_order_status(
    work_order_id: uuid.UUID,
    body: WorkOrderStatusUpdate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> WorkOrderOut:
    exists = connection.execute(
        text("SELECT 1 FROM work_orders WHERE id = :id"), {"id": work_order_id}
    ).scalar()
    if not exists:
        raise ApiError(404, "WORK_ORDER_NOT_FOUND")

    change_work_order_status(
        connection,
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        status=body.status,
        changed_by=_actor(claims),
        note=body.note,
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="work_order.status_changed",
        entity_type="work_order",
        entity_id=str(work_order_id),
        payload={"status": body.status},
    )
    return _read_work_order(connection, work_order_id)


@router.get(
    "/work-orders/{work_order_id}/history",
    response_model=list[WorkOrderStatusHistoryOut],
)
def read_work_order_history(
    work_order_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[WorkOrderStatusHistoryOut]:
    exists = connection.execute(
        text("SELECT 1 FROM work_orders WHERE id = :id"), {"id": work_order_id}
    ).scalar()
    if not exists:
        raise ApiError(404, "WORK_ORDER_NOT_FOUND")

    rows = (
        connection.execute(
            text(
                "SELECT id, work_order_id, status, changed_by, note, changed_at "
                "FROM work_order_status_history WHERE work_order_id = :id ORDER BY changed_at"
            ),
            {"id": work_order_id},
        )
        .mappings()
        .all()
    )
    return [WorkOrderStatusHistoryOut(**row) for row in rows]


def _read_work_order(connection: Connection, work_order_id: uuid.UUID) -> WorkOrderOut:
    row = (
        connection.execute(
            text(
                "SELECT id, functional_location_id, physical_unit_id, title, description, "
                "work_order_type, priority, status, created_by, created_at "
                "FROM work_orders WHERE id = :id"
            ),
            {"id": work_order_id},
        )
        .mappings()
        .one()
    )
    return WorkOrderOut(**row)


# --- Interventions ------------------------------------------------


_INTERVENTION_COLUMNS = (
    "id, work_order_id, functional_location_id, physical_unit_id, technician, "
    "intervention_type, started_at, ended_at, summary, checklist, created_at, client_ref"
)


@router.post("/interventions", response_model=InterventionOut, status_code=status.HTTP_201_CREATED)
def create_intervention(
    body: InterventionCreate,
    response: Response,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> InterventionOut:
    """Avec `client_ref`, l'envoi est rejouable : un renvoi identique rend
    l'intervention déjà créée (200) ; un contenu différent est refusé (409)."""
    if body.work_order_id is not None:
        exists = connection.execute(
            text("SELECT 1 FROM work_orders WHERE id = :id"), {"id": body.work_order_id}
        ).scalar()
        if not exists:
            raise ApiError(404, "WORK_ORDER_NOT_FOUND")
    _check_targets_exist(
        connection,
        functional_location_id=body.functional_location_id,
        physical_unit_id=body.physical_unit_id,
    )

    fields = {
        "tenant_id": tenant_id,
        "technician": _actor(claims),
        "started_at": body.started_at or datetime.now(UTC),
        "intervention_type": body.intervention_type,
        "ended_at": body.ended_at,
        "summary": body.summary,
        "checklist": body.checklist,
        "work_order_id": body.work_order_id,
        "functional_location_id": body.functional_location_id,
        "physical_unit_id": body.physical_unit_id,
    }
    if body.client_ref is None:
        intervention_id, created = log_intervention(connection, **fields), True
    else:
        try:
            intervention_id, created = log_intervention_once(
                connection, client_ref=body.client_ref, **fields
            )
        except ClientRefConflict as exc:
            raise api_error(exc, 409) from exc

    if created:
        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor=_actor(claims),
            action="intervention.logged",
            entity_type="intervention",
            entity_id=str(intervention_id),
            payload={
                "work_order_id": str(body.work_order_id) if body.work_order_id else None,
                "intervention_type": body.intervention_type,
            },
        )
    else:
        response.status_code = status.HTTP_200_OK
    row = (
        connection.execute(
            text(f"SELECT {_INTERVENTION_COLUMNS} FROM interventions WHERE id = :id"),
            {"id": intervention_id},
        )
        .mappings()
        .one()
    )
    return InterventionOut(**row)


@router.get("/interventions", response_model=list[InterventionOut])
def list_interventions(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[InterventionOut]:
    rows = (
        connection.execute(
            text(f"SELECT {_INTERVENTION_COLUMNS} FROM interventions ORDER BY started_at")
        )
        .mappings()
        .all()
    )
    return [InterventionOut(**row) for row in rows]


# --- Photos d'intervention ------------------------------------------------


def _check_intervention_exists(connection: Connection, intervention_id: uuid.UUID) -> None:
    exists = connection.execute(
        text("SELECT 1 FROM interventions WHERE id = :id"), {"id": intervention_id}
    ).scalar()
    if not exists:
        raise ApiError(404, "INTERVENTION_NOT_FOUND")


@router.post(
    "/interventions/{intervention_id}/photos/upload-url",
    response_model=PhotoUploadUrlOut,
)
def create_photo_upload_url(
    intervention_id: uuid.UUID,
    body: PhotoUploadUrlRequest,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> PhotoUploadUrlOut:
    """Donne au client mobile une URL temporaire pour envoyer une photo
    directement au stockage (voir ADR 006), sans jamais lui transmettre les
    identifiants d'accès. L'API n'enregistre la photo en base qu'une fois
    l'envoi terminé, via POST .../photos."""
    _check_intervention_exists(connection, intervention_id)

    object_key = build_object_key(
        tenant_id=tenant_id, intervention_id=intervention_id, filename=body.filename
    )
    upload_url = create_presigned_upload_url(object_key, content_type=body.content_type)
    return PhotoUploadUrlOut(upload_url=upload_url, object_key=object_key)


@router.post(
    "/interventions/{intervention_id}/photos",
    response_model=PhotoOut,
    status_code=status.HTTP_201_CREATED,
)
def create_photo(
    intervention_id: uuid.UUID,
    body: PhotoCreate,
    response: Response,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> PhotoOut:
    _check_intervention_exists(connection, intervention_id)
    if not key_belongs_to(body.object_key, tenant_id=tenant_id, intervention_id=intervention_id):
        raise ApiError(422, "PHOTO_STORAGE_KEY_FOREIGN")

    fields = {
        "tenant_id": tenant_id,
        "intervention_id": intervention_id,
        "storage_key": body.object_key,
        "taken_at": body.taken_at or datetime.now(UTC),
        "caption": body.caption,
    }
    if body.client_ref is None:
        photo_id, created = record_photo(connection, **fields), True
    else:
        try:
            photo_id, created = record_photo_once(connection, client_ref=body.client_ref, **fields)
        except ClientRefConflict as exc:
            raise api_error(exc, 409) from exc

    if created:
        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor=_actor(claims),
            action="intervention.photo_added",
            entity_type="intervention_photo",
            entity_id=str(photo_id),
            payload={"intervention_id": str(intervention_id)},
        )
    else:
        response.status_code = status.HTTP_200_OK
    return _read_photo(connection, photo_id)


@router.get(
    "/interventions/{intervention_id}/photos",
    response_model=list[PhotoOut],
)
def list_photos(
    intervention_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[PhotoOut]:
    _check_intervention_exists(connection, intervention_id)

    rows = (
        connection.execute(
            text(
                "SELECT id, intervention_id, storage_key, caption, taken_at, uploaded_at "
                "FROM intervention_photos WHERE intervention_id = :id ORDER BY taken_at"
            ),
            {"id": intervention_id},
        )
        .mappings()
        .all()
    )
    return [_to_photo_out(row) for row in rows]


def _read_photo(connection: Connection, photo_id: uuid.UUID) -> PhotoOut:
    row = (
        connection.execute(
            text(
                "SELECT id, intervention_id, storage_key, caption, taken_at, uploaded_at "
                "FROM intervention_photos WHERE id = :id"
            ),
            {"id": photo_id},
        )
        .mappings()
        .one()
    )
    return _to_photo_out(row)


def _to_photo_out(row: Any) -> PhotoOut:
    return PhotoOut(
        id=row["id"],
        intervention_id=row["intervention_id"],
        download_url=create_presigned_download_url(row["storage_key"]),
        caption=row["caption"],
        taken_at=row["taken_at"],
        uploaded_at=row["uploaded_at"],
    )


# --- Alarmes ------------------------------------------------


@router.post("/alarms", response_model=AlarmOut, status_code=status.HTTP_201_CREATED)
def create_alarm(
    body: AlarmCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> AlarmOut:
    _check_targets_exist(
        connection,
        functional_location_id=body.functional_location_id,
        physical_unit_id=body.physical_unit_id,
    )

    alarm_id = raise_alarm(
        connection,
        tenant_id=tenant_id,
        raised_by=_actor(claims),
        severity=body.severity,
        message=body.message,
        functional_location_id=body.functional_location_id,
        physical_unit_id=body.physical_unit_id,
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="alarm.raised",
        entity_type="alarm",
        entity_id=str(alarm_id),
        payload={"severity": body.severity, "message": body.message},
    )
    return _read_alarm(connection, alarm_id)


_ALARM_COLUMNS = (
    "id, functional_location_id, physical_unit_id, severity, message, condition_state, "
    "ack_state, handling_status, raised_by, raised_at"
)


@router.get("/alarms", response_model=list[AlarmOut])
def list_alarms(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    handling_status: HandlingStatus | None = None,
    condition_state: Literal["active", "cleared"] | None = None,
    ack_state: Literal["unacknowledged", "acknowledged"] | None = None,
) -> list[AlarmOut]:
    query = f"SELECT {_ALARM_COLUMNS} FROM alarms WHERE true"
    params: dict[str, Any] = {}
    for column, value in (
        ("handling_status", handling_status),
        ("condition_state", condition_state),
        ("ack_state", ack_state),
    ):
        if value is not None:
            query += f" AND {column} = :{column}"
            params[column] = value
    rows = connection.execute(text(query + " ORDER BY raised_at"), params).mappings().all()
    return [AlarmOut(**row) for row in rows]


def _audit_alarm(connection, tenant_id, claims, action, alarm_id, payload) -> None:
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action=action,
        entity_type="alarm",
        entity_id=str(alarm_id),
        payload=payload,
    )


@router.post("/alarms/{alarm_id}/acknowledge", response_model=AlarmOut)
def acknowledge_alarm(
    alarm_id: uuid.UUID,
    body: SignalNote,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> AlarmOut:
    """« J'ai pris connaissance de l'alarme » ; ne dit pas qu'elle est réglée."""
    acknowledge(
        connection,
        kind="alarm",
        tenant_id=tenant_id,
        signal_id=alarm_id,
        changed_by=_actor(claims),
        note=body.note,
    )
    _audit_alarm(connection, tenant_id, claims, "alarm.acknowledged", alarm_id, {})
    return _read_alarm(connection, alarm_id)


@router.patch("/alarms/{alarm_id}/handling", response_model=AlarmOut)
def update_alarm_handling(
    alarm_id: uuid.UUID,
    body: SignalHandlingUpdate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> AlarmOut:
    set_handling(
        connection,
        kind="alarm",
        tenant_id=tenant_id,
        signal_id=alarm_id,
        handling_status=body.handling_status,
        changed_by=_actor(claims),
        note=body.note,
    )
    _audit_alarm(
        connection,
        tenant_id,
        claims,
        "alarm.handling_changed",
        alarm_id,
        {"handling_status": body.handling_status},
    )
    return _read_alarm(connection, alarm_id)


@router.post("/alarms/{alarm_id}/clear", response_model=AlarmOut)
def clear_alarm(
    alarm_id: uuid.UUID,
    body: SignalNote,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> AlarmOut:
    """Retour à la normale constaté par une personne (alarme saisie à la main :
    aucune mesure ne peut le détecter)."""
    clear_condition(
        connection,
        kind="alarm",
        tenant_id=tenant_id,
        signal_id=alarm_id,
        changed_by=_actor(claims),
        note=body.note,
    )
    _audit_alarm(connection, tenant_id, claims, "alarm.cleared", alarm_id, {})
    return _read_alarm(connection, alarm_id)


@router.get("/alarms/{alarm_id}/history", response_model=list[SignalHistoryOut])
def read_alarm_history(
    alarm_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[SignalHistoryOut]:
    get_axes(connection, "alarm", alarm_id)
    return [SignalHistoryOut(**row) for row in signal_history(connection, "alarm", alarm_id)]


def _read_alarm(connection: Connection, alarm_id: uuid.UUID) -> AlarmOut:
    row = (
        connection.execute(
            text(f"SELECT {_ALARM_COLUMNS} FROM alarms WHERE id = :id"), {"id": alarm_id}
        )
        .mappings()
        .one()
    )
    return AlarmOut(**row)


# --- Clôture structurée ------------------------------------------------


@router.get("/closure-vocabulary")
def read_closure_vocabulary(
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> dict[str, Any]:
    """Codes de clôture et leurs libellés, pour construire les formulaires."""
    return {
        "version": CLOSURE_VOCABULARY_VERSION,
        "symptoms": SYMPTOMS,
        "causes": CAUSES,
        "actions": ACTIONS,
        "verification_results": VERIFICATION_RESULTS,
    }


@router.post(
    "/interventions/{intervention_id}/closure",
    response_model=ClosureOut,
    status_code=status.HTTP_201_CREATED,
)
def create_closure(
    intervention_id: uuid.UUID,
    body: ClosureCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> ClosureOut:
    try:
        close_intervention(
            connection,
            tenant_id=tenant_id,
            intervention_id=intervention_id,
            symptom_code=body.symptom_code,
            cause_code=body.cause_code,
            action_code=body.action_code,
            parts=[part.model_dump(exclude_none=True) for part in body.parts],
            labor_minutes=body.labor_minutes,
            verification_result=body.verification_result,
            note=body.note,
            closed_by=_actor(claims),
        )
    except ClosureNotFound as exc:
        raise api_error(exc, 404) from exc
    except ClosureConflict as exc:
        raise api_error(exc, 409) from exc
    except ClosureError as exc:
        raise api_error(exc, 400) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="intervention.closed",
        entity_type="intervention",
        entity_id=str(intervention_id),
        payload={
            "symptom_code": body.symptom_code,
            "cause_code": body.cause_code,
            "action_code": body.action_code,
            "verification_result": body.verification_result,
        },
    )
    return ClosureOut(**get_closure(connection, intervention_id))


@router.get("/interventions/{intervention_id}/closure", response_model=ClosureOut)
def read_closure(
    intervention_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> ClosureOut:
    closure = get_closure(connection, intervention_id)
    if closure is None:
        raise ApiError(404, "CLOSURE_NOT_FOUND")
    return ClosureOut(**closure)
