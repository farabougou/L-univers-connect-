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


class ClientRefConflict(ValueError):
    """Même référence client, contenu différent : rien n'est écrasé."""


_INTERVENTION_FIELDS = (
    "work_order_id",
    "functional_location_id",
    "physical_unit_id",
    "technician",
    "intervention_type",
    "started_at",
    "ended_at",
    "summary",
    "checklist",
)


def _insert_intervention(
    connection: Connection, values: dict[str, Any], *, skip_if_exists: bool
) -> uuid.UUID | None:
    on_conflict = " ON CONFLICT (tenant_id, client_ref) DO NOTHING" if skip_if_exists else ""
    return connection.execute(
        text(
            "INSERT INTO interventions "
            "(id, tenant_id, work_order_id, functional_location_id, physical_unit_id, "
            "technician, intervention_type, started_at, ended_at, summary, checklist, "
            "client_ref) "
            "VALUES (:id, :tenant_id, :work_order_id, :functional_location_id, "
            ":physical_unit_id, :technician, :intervention_type, :started_at, :ended_at, "
            f":summary, CAST(:checklist AS JSONB), :client_ref){on_conflict} RETURNING id"
        ),
        {
            **values,
            "id": uuid.uuid4(),
            "checklist": json.dumps(
                values["checklist"] or {}, sort_keys=True, separators=(",", ":")
            ),
        },
    ).scalar()


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
    values = {
        "tenant_id": tenant_id,
        "work_order_id": work_order_id,
        "functional_location_id": functional_location_id,
        "physical_unit_id": physical_unit_id,
        "technician": technician,
        "intervention_type": intervention_type,
        "started_at": started_at,
        "ended_at": ended_at,
        "summary": summary,
        "checklist": checklist,
        "client_ref": None,
    }
    return _insert_intervention(connection, values, skip_if_exists=False)


def log_intervention_once(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    client_ref: str,
    technician: str,
    started_at: datetime,
    intervention_type: str = "intervention",
    ended_at: datetime | None = None,
    summary: str | None = None,
    checklist: dict[str, Any] | None = None,
    work_order_id: uuid.UUID | None = None,
    functional_location_id: uuid.UUID | None = None,
    physical_unit_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, bool]:
    """Envoi rejouable : renvoie (identifiant, créée maintenant ?).

    Le renvoi d'un envoi déjà reçu (même référence, même contenu) rend
    l'intervention existante sans rien créer. Deux envois simultanés avec la
    même référence ne peuvent pas passer tous les deux : la contrainte
    d'unicité en base tranche (ON CONFLICT)."""
    values = {
        "tenant_id": tenant_id,
        "work_order_id": work_order_id,
        "functional_location_id": functional_location_id,
        "physical_unit_id": physical_unit_id,
        "technician": technician,
        "intervention_type": intervention_type,
        "started_at": started_at,
        "ended_at": ended_at,
        "summary": summary,
        "checklist": checklist or {},
        "client_ref": client_ref,
    }
    inserted = _insert_intervention(connection, values, skip_if_exists=True)
    if inserted is not None:
        return inserted, True

    existing = (
        connection.execute(
            text(
                f"SELECT id, {', '.join(_INTERVENTION_FIELDS)} FROM interventions "
                "WHERE client_ref = :client_ref"
            ),
            {"client_ref": client_ref},
        )
        .mappings()
        .one()
    )
    differing = [field for field in _INTERVENTION_FIELDS if existing[field] != values[field]]
    if differing:
        raise ClientRefConflict(
            "cette référence client désigne déjà une autre intervention "
            f"(champs différents : {', '.join(differing)})"
        )
    return existing["id"], False


def _insert_photo(
    connection: Connection, values: dict[str, Any], *, skip_if_exists: bool
) -> uuid.UUID | None:
    on_conflict = " ON CONFLICT (tenant_id, client_ref) DO NOTHING" if skip_if_exists else ""
    return connection.execute(
        text(
            "INSERT INTO intervention_photos "
            "(id, tenant_id, intervention_id, storage_key, caption, taken_at, client_ref) "
            "VALUES (:id, :tenant_id, :intervention_id, :storage_key, :caption, :taken_at, "
            f":client_ref){on_conflict} RETURNING id"
        ),
        {**values, "id": uuid.uuid4()},
    ).scalar()


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
    values = {
        "tenant_id": tenant_id,
        "intervention_id": intervention_id,
        "storage_key": storage_key,
        "caption": caption,
        "taken_at": taken_at,
        "client_ref": None,
    }
    return _insert_photo(connection, values, skip_if_exists=False)


def record_photo_once(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    client_ref: str,
    intervention_id: uuid.UUID,
    storage_key: str,
    taken_at: datetime,
    caption: str | None = None,
) -> tuple[uuid.UUID, bool]:
    """Confirmation rejouable : renvoie (identifiant, créée maintenant ?).

    Au nouvel essai, le téléphone a renvoyé la photo sous une autre clé de
    stockage : la première photo confirmée est gardée (rien n'est écrasé) ;
    le second fichier reste orphelin dans le stockage, sans lien en base."""
    values = {
        "tenant_id": tenant_id,
        "intervention_id": intervention_id,
        "storage_key": storage_key,
        "caption": caption,
        "taken_at": taken_at,
        "client_ref": client_ref,
    }
    inserted = _insert_photo(connection, values, skip_if_exists=True)
    if inserted is not None:
        return inserted, True

    existing = (
        connection.execute(
            text("SELECT id, intervention_id FROM intervention_photos WHERE client_ref = :ref"),
            {"ref": client_ref},
        )
        .mappings()
        .one()
    )
    if existing["intervention_id"] != intervention_id:
        raise ClientRefConflict("cette référence client désigne déjà une autre photo")
    return existing["id"], False


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
