import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.maintenance import (
    change_alarm_status,
    change_work_order_status,
    create_work_order,
    log_intervention,
    raise_alarm,
    record_photo,
)
from app.schemas import (
    AlarmCreate,
    AlarmOut,
    AlarmStatusHistoryOut,
    AlarmStatusUpdate,
    InterventionCreate,
    InterventionOut,
    PhotoCreate,
    PhotoOut,
    PhotoUploadUrlOut,
    PhotoUploadUrlRequest,
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderStatusHistoryOut,
    WorkOrderStatusUpdate,
)
from app.storage import build_object_key, create_presigned_download_url, create_presigned_upload_url

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="position fonctionnelle introuvable"
            )
    if physical_unit_id is not None:
        exists = connection.execute(
            text("SELECT 1 FROM physical_units WHERE id = :id"), {"id": physical_unit_id}
        ).scalar()
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="exemplaire introuvable"
            )


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ordre de travail introuvable"
        )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ordre de travail introuvable"
        )

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


@router.post("/interventions", response_model=InterventionOut, status_code=status.HTTP_201_CREATED)
def create_intervention(
    body: InterventionCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> InterventionOut:
    if body.work_order_id is not None:
        exists = connection.execute(
            text("SELECT 1 FROM work_orders WHERE id = :id"), {"id": body.work_order_id}
        ).scalar()
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="ordre de travail introuvable"
            )
    _check_targets_exist(
        connection,
        functional_location_id=body.functional_location_id,
        physical_unit_id=body.physical_unit_id,
    )

    intervention_id = log_intervention(
        connection,
        tenant_id=tenant_id,
        technician=_actor(claims),
        started_at=body.started_at or datetime.now(UTC),
        intervention_type=body.intervention_type,
        ended_at=body.ended_at,
        summary=body.summary,
        checklist=body.checklist,
        work_order_id=body.work_order_id,
        functional_location_id=body.functional_location_id,
        physical_unit_id=body.physical_unit_id,
    )
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
    row = (
        connection.execute(
            text(
                "SELECT id, work_order_id, functional_location_id, physical_unit_id, "
                "technician, intervention_type, started_at, ended_at, summary, checklist, "
                "created_at FROM interventions WHERE id = :id"
            ),
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
            text(
                "SELECT id, work_order_id, functional_location_id, physical_unit_id, "
                "technician, intervention_type, started_at, ended_at, summary, checklist, "
                "created_at FROM interventions ORDER BY started_at"
            )
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="intervention introuvable"
        )


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
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> PhotoOut:
    _check_intervention_exists(connection, intervention_id)

    photo_id = record_photo(
        connection,
        tenant_id=tenant_id,
        intervention_id=intervention_id,
        storage_key=body.object_key,
        taken_at=body.taken_at or datetime.now(UTC),
        caption=body.caption,
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="intervention.photo_added",
        entity_type="intervention_photo",
        entity_id=str(photo_id),
        payload={"intervention_id": str(intervention_id)},
    )
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


@router.get("/alarms", response_model=list[AlarmOut])
def list_alarms(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[AlarmOut]:
    rows = (
        connection.execute(
            text(
                "SELECT id, functional_location_id, physical_unit_id, severity, message, "
                "status, raised_by, raised_at FROM alarms ORDER BY raised_at"
            )
        )
        .mappings()
        .all()
    )
    return [AlarmOut(**row) for row in rows]


@router.patch("/alarms/{alarm_id}/status", response_model=AlarmOut)
def update_alarm_status(
    alarm_id: uuid.UUID,
    body: AlarmStatusUpdate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> AlarmOut:
    exists = connection.execute(
        text("SELECT 1 FROM alarms WHERE id = :id"), {"id": alarm_id}
    ).scalar()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alarme introuvable")

    change_alarm_status(
        connection,
        tenant_id=tenant_id,
        alarm_id=alarm_id,
        status=body.status,
        changed_by=_actor(claims),
        note=body.note,
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="alarm.status_changed",
        entity_type="alarm",
        entity_id=str(alarm_id),
        payload={"status": body.status},
    )
    return _read_alarm(connection, alarm_id)


@router.get("/alarms/{alarm_id}/history", response_model=list[AlarmStatusHistoryOut])
def read_alarm_history(
    alarm_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[AlarmStatusHistoryOut]:
    exists = connection.execute(
        text("SELECT 1 FROM alarms WHERE id = :id"), {"id": alarm_id}
    ).scalar()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alarme introuvable")

    rows = (
        connection.execute(
            text(
                "SELECT id, alarm_id, status, changed_by, note, changed_at "
                "FROM alarm_status_history WHERE alarm_id = :id ORDER BY changed_at"
            ),
            {"id": alarm_id},
        )
        .mappings()
        .all()
    )
    return [AlarmStatusHistoryOut(**row) for row in rows]


def _read_alarm(connection: Connection, alarm_id: uuid.UUID) -> AlarmOut:
    row = (
        connection.execute(
            text(
                "SELECT id, functional_location_id, physical_unit_id, severity, message, "
                "status, raised_by, raised_at FROM alarms WHERE id = :id"
            ),
            {"id": alarm_id},
        )
        .mappings()
        .one()
    )
    return AlarmOut(**row)
