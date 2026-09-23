"""Cycle de vie d'un exemplaire physique (ADR 012, section 2.9).

Même principe que les statuts d'ordres de travail : un état courant pour la
lecture rapide, et une ligne d'historique jamais modifiée par changement.

« Installé » et « déposé » ne se déclarent pas à la main : ils découlent des
affectations (installer un exemplaire à une position, le remplacer), pour
que cycle de vie et historique d'occupation ne se contredisent jamais.
« Entretenu » n'est pas un état : c'est une suite d'interventions.

La date `occurred_at` (quand c'est arrivé) peut précéder des événements déjà
saisis : on peut enregistrer aujourd'hui une installation de 2019. L'ordre
des transitions, lui, suit l'ordre de saisie.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

STATES = (
    "planned",
    "ordered",
    "in_stock",
    "installed",
    "commissioned",
    "in_service",
    "out_of_service",
    "removed",
    "decommissioned",
    "disposed",
)

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "planned": ("ordered", "in_stock"),
    "ordered": ("in_stock",),
    "in_stock": ("installed", "decommissioned", "disposed"),
    "installed": ("commissioned", "removed"),
    "commissioned": ("in_service", "removed"),
    "in_service": ("out_of_service", "removed"),
    "out_of_service": ("in_service", "removed"),
    "removed": ("in_stock", "installed", "decommissioned"),
    "decommissioned": ("disposed",),
    "disposed": (),
}

# États imposés par les affectations, jamais déclarés à la main.
ASSIGNMENT_STATES = ("installed", "removed")
# États dans lesquels un exemplaire peut être installé à une position.
INSTALLABLE_STATES = ("in_stock", "removed")
# États d'un exemplaire occupant une position.
MOUNTED_STATES = ("installed", "commissioned", "in_service", "out_of_service")


class LifecycleError(ValueError):
    pass


class LifecycleNotFound(LookupError):
    pass


def current_state(connection: Connection, physical_unit_id: uuid.UUID) -> str:
    state = connection.execute(
        text("SELECT lifecycle_state FROM physical_units WHERE id = :id"),
        {"id": physical_unit_id},
    ).scalar()
    if state is None:
        raise LifecycleNotFound("exemplaire introuvable")
    return state


def change_state(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    physical_unit_id: uuid.UUID,
    to_state: str,
    occurred_at: datetime,
    changed_by: str,
    note: str | None = None,
    via_assignment: bool = False,
) -> None:
    if to_state not in STATES:
        raise LifecycleError(f"état inconnu : {to_state}")
    if to_state in ASSIGNMENT_STATES and not via_assignment:
        raise LifecycleError(
            f"« {to_state} » découle d'une affectation : installer ou remplacer l'exemplaire "
            "à sa position plutôt que de changer l'état à la main"
        )
    from_state = current_state(connection, physical_unit_id)
    if to_state not in TRANSITIONS[from_state]:
        raise LifecycleError(f"passage « {from_state} » → « {to_state} » impossible")

    connection.execute(
        text("UPDATE physical_units SET lifecycle_state = :state WHERE id = :id"),
        {"state": to_state, "id": physical_unit_id},
    )
    record_event(
        connection,
        tenant_id=tenant_id,
        physical_unit_id=physical_unit_id,
        from_state=from_state,
        to_state=to_state,
        occurred_at=occurred_at,
        changed_by=changed_by,
        note=note,
    )


def record_event(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    physical_unit_id: uuid.UUID,
    from_state: str | None,
    to_state: str,
    occurred_at: datetime,
    changed_by: str,
    note: str | None,
) -> None:
    connection.execute(
        text(
            "INSERT INTO physical_unit_lifecycle_events (id, tenant_id, physical_unit_id, "
            "from_state, to_state, occurred_at, changed_by, note) VALUES (:id, :tenant_id, "
            ":physical_unit_id, :from_state, :to_state, :occurred_at, :changed_by, :note)"
        ),
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "physical_unit_id": physical_unit_id,
            "from_state": from_state,
            "to_state": to_state,
            "occurred_at": occurred_at,
            "changed_by": changed_by,
            "note": note,
        },
    )


def lifecycle_history(connection: Connection, physical_unit_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(
                "SELECT id, physical_unit_id, from_state, to_state, occurred_at, recorded_at, "
                "changed_by, note FROM physical_unit_lifecycle_events "
                "WHERE physical_unit_id = :id ORDER BY recorded_at, occurred_at"
            ),
            {"id": physical_unit_id},
        ).mappings()
    ]
