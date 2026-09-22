import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

WORK_ORDER_STATUSES = ("open", "in_progress", "completed", "cancelled")
WORK_ORDER_TYPES = ("corrective", "preventive", "predictive", "inspection")
ALARM_STATUSES = ("open", "acknowledged", "resolved")


def create_work_order(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    created_by: str,
    title: str,
    description: str | None = None,
    work_order_type: str = "corrective",
    priority: str = "medium",
    functional_location_id: uuid.UUID | None = None,
    physical_unit_id: uuid.UUID | None = None,
) -> uuid.UUID:
    work_order_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO work_orders "
            "(id, tenant_id, functional_location_id, physical_unit_id, "
            "title, description, work_order_type, priority, status, created_by) "
            "VALUES (:id, :tenant_id, :functional_location_id, :physical_unit_id, "
            ":title, :description, :work_order_type, :priority, 'open', :created_by)"
        ),
        {
            "id": work_order_id,
            "tenant_id": tenant_id,
            "functional_location_id": functional_location_id,
            "physical_unit_id": physical_unit_id,
            "title": title,
            "description": description,
            "work_order_type": work_order_type,
            "priority": priority,
            "created_by": created_by,
        },
    )
    _insert_work_order_status_history(
        connection,
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        status="open",
        changed_by=created_by,
        note=None,
    )
    return work_order_id


def change_work_order_status(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    work_order_id: uuid.UUID,
    status: str,
    changed_by: str,
    note: str | None = None,
) -> None:
    """Change le statut courant et ajoute une ligne d'historique.

    Le statut courant de work_orders est dénormalisé pour la lecture rapide,
    mais la ligne d'historique n'est jamais modifiée : elle reste la preuve
    de ce qui s'est réellement passé, même si le statut courant change
    encore ensuite (voir la règle « rien n'est écrasé »).
    """
    if status not in WORK_ORDER_STATUSES:
        raise ValueError(f"statut inconnu : {status}")

    connection.execute(
        text("UPDATE work_orders SET status = :status WHERE id = :id"),
        {"status": status, "id": work_order_id},
    )
    _insert_work_order_status_history(
        connection,
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        status=status,
        changed_by=changed_by,
        note=note,
    )


def _insert_work_order_status_history(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    work_order_id: uuid.UUID,
    status: str,
    changed_by: str,
    note: str | None,
) -> None:
    connection.execute(
        text(
            "INSERT INTO work_order_status_history "
            "(id, tenant_id, work_order_id, status, changed_by, note) "
            "VALUES (:id, :tenant_id, :work_order_id, :status, :changed_by, :note)"
        ),
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "work_order_id": work_order_id,
            "status": status,
            "changed_by": changed_by,
            "note": note,
        },
    )


def log_intervention(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    technician: str,
    started_at: datetime,
    intervention_type: str = "intervention",
    ended_at: datetime | None = None,
    summary: str | None = None,
    checklist: dict[str, Any] | None = None,
    work_order_id: uuid.UUID | None = None,
    functional_location_id: uuid.UUID | None = None,
    physical_unit_id: uuid.UUID | None = None,
) -> uuid.UUID:
    intervention_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO interventions "
            "(id, tenant_id, work_order_id, functional_location_id, physical_unit_id, "
            "technician, intervention_type, started_at, ended_at, summary, checklist) "
            "VALUES (:id, :tenant_id, :work_order_id, :functional_location_id, "
            ":physical_unit_id, :technician, :intervention_type, :started_at, :ended_at, "
            ":summary, CAST(:checklist AS JSONB))"
        ),
        {
            "id": intervention_id,
            "tenant_id": tenant_id,
            "work_order_id": work_order_id,
            "functional_location_id": functional_location_id,
            "physical_unit_id": physical_unit_id,
            "technician": technician,
            "intervention_type": intervention_type,
            "started_at": started_at,
            "ended_at": ended_at,
            "summary": summary,
            "checklist": json.dumps(checklist or {}, sort_keys=True, separators=(",", ":")),
        },
    )
    return intervention_id


def record_photo(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    intervention_id: uuid.UUID,
    storage_key: str,
    taken_at: datetime,
    caption: str | None = None,
) -> uuid.UUID:
    """Enregistre la référence d'une photo déjà envoyée au stockage (voir
    ADR 006). Le contenu de la photo n'est jamais manipulé ici, seule la clé
    de stockage l'est."""
    photo_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO intervention_photos "
            "(id, tenant_id, intervention_id, storage_key, caption, taken_at) "
            "VALUES (:id, :tenant_id, :intervention_id, :storage_key, :caption, :taken_at)"
        ),
        {
            "id": photo_id,
            "tenant_id": tenant_id,
            "intervention_id": intervention_id,
            "storage_key": storage_key,
            "caption": caption,
            "taken_at": taken_at,
        },
    )
    return photo_id


def raise_alarm(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    raised_by: str,
    severity: str,
    message: str,
    functional_location_id: uuid.UUID | None = None,
    physical_unit_id: uuid.UUID | None = None,
) -> uuid.UUID:
    alarm_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO alarms "
            "(id, tenant_id, functional_location_id, physical_unit_id, "
            "severity, message, status, raised_by) "
            "VALUES (:id, :tenant_id, :functional_location_id, :physical_unit_id, "
            ":severity, :message, 'open', :raised_by)"
        ),
        {
            "id": alarm_id,
            "tenant_id": tenant_id,
            "functional_location_id": functional_location_id,
            "physical_unit_id": physical_unit_id,
            "severity": severity,
            "message": message,
            "raised_by": raised_by,
        },
    )
    _insert_alarm_status_history(
        connection,
        tenant_id=tenant_id,
        alarm_id=alarm_id,
        status="open",
        changed_by=raised_by,
        note=None,
    )
    return alarm_id


def change_alarm_status(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    alarm_id: uuid.UUID,
    status: str,
    changed_by: str,
    note: str | None = None,
) -> None:
    if status not in ALARM_STATUSES:
        raise ValueError(f"statut inconnu : {status}")

    connection.execute(
        text("UPDATE alarms SET status = :status WHERE id = :id"),
        {"status": status, "id": alarm_id},
    )
    _insert_alarm_status_history(
        connection,
        tenant_id=tenant_id,
        alarm_id=alarm_id,
        status=status,
        changed_by=changed_by,
        note=note,
    )


def _insert_alarm_status_history(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    alarm_id: uuid.UUID,
    status: str,
    changed_by: str,
    note: str | None,
) -> None:
    connection.execute(
        text(
            "INSERT INTO alarm_status_history "
            "(id, tenant_id, alarm_id, status, changed_by, note) "
            "VALUES (:id, :tenant_id, :alarm_id, :status, :changed_by, :note)"
        ),
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "alarm_id": alarm_id,
            "status": status,
            "changed_by": changed_by,
            "note": note,
        },
    )
