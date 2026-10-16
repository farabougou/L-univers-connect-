import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError
from app.lifecycle import (
    INSTALLABLE_STATES,
    MOUNTED_STATES,
    LifecycleError,
    change_state,
    current_state,
)
from app.spatial import check_space_for_location, record_location_space


class FunctionalLocationNotFound(DomainError, LookupError):
    status = 404


class FunctionalLocationConflict(DomainError, ValueError):
    status = 409


class SiteNotFound(DomainError, LookupError):
    status = 404


def archive_site(connection: Connection, *, site_id: uuid.UUID, archived_by: str) -> None:
    """Masque un site des listes par défaut, sans toucher à son historique ni
    à ses relations : jamais une suppression (CLAUDE.md, règle non
    négociable 3 — rien n'est écrasé). Idempotent : archiver un site déjà
    archivé ne change rien et ne lève pas d'erreur."""
    updated = connection.execute(
        text(
            "UPDATE sites SET archived_at = :now, archived_by = :by "
            "WHERE id = :id AND archived_at IS NULL"
        ),
        {"now": datetime.now(UTC), "by": archived_by, "id": site_id},
    ).rowcount
    if not updated and not _site_exists(connection, site_id):
        raise SiteNotFound("SITE_NOT_FOUND")


def unarchive_site(connection: Connection, *, site_id: uuid.UUID) -> None:
    """Réversible par construction : remet le site dans les listes par défaut,
    rien d'autre n'a jamais été modifié pendant l'archivage."""
    updated = connection.execute(
        text(
            "UPDATE sites SET archived_at = NULL, archived_by = NULL "
            "WHERE id = :id AND archived_at IS NOT NULL"
        ),
        {"id": site_id},
    ).rowcount
    if not updated and not _site_exists(connection, site_id):
        raise SiteNotFound("SITE_NOT_FOUND")


def _site_exists(connection: Connection, site_id: uuid.UUID) -> bool:
    return bool(
        connection.execute(text("SELECT 1 FROM sites WHERE id = :id"), {"id": site_id}).scalar()
    )


def archive_functional_location(
    connection: Connection, *, functional_location_id: uuid.UUID, archived_by: str
) -> None:
    """Même principe que `archive_site`, pour un équipement/emplacement."""
    updated = connection.execute(
        text(
            "UPDATE functional_locations SET archived_at = :now, archived_by = :by "
            "WHERE id = :id AND archived_at IS NULL"
        ),
        {"now": datetime.now(UTC), "by": archived_by, "id": functional_location_id},
    ).rowcount
    if not updated and get_functional_location(connection, functional_location_id) is None:
        raise FunctionalLocationNotFound("FUNCTIONAL_LOCATION_NOT_FOUND")


def unarchive_functional_location(
    connection: Connection, *, functional_location_id: uuid.UUID
) -> None:
    updated = connection.execute(
        text(
            "UPDATE functional_locations SET archived_at = NULL, archived_by = NULL "
            "WHERE id = :id AND archived_at IS NOT NULL"
        ),
        {"id": functional_location_id},
    ).rowcount
    if not updated and get_functional_location(connection, functional_location_id) is None:
        raise FunctionalLocationNotFound("FUNCTIONAL_LOCATION_NOT_FOUND")


def create_functional_location(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    code: str,
    name: str,
    kind: str,
    space_id: uuid.UUID | None,
    created_by: str,
) -> uuid.UUID:
    """Crée une position fonctionnelle, avec son emplacement initial si
    fourni. Utilisée à la fois par la console web (saisie directe) et par
    l'import IFC (une fois une proposition acceptée) : un seul chemin de
    création, jamais deux modèles de la même chose."""
    site_exists = connection.execute(
        text("SELECT 1 FROM sites WHERE id = :id"), {"id": site_id}
    ).scalar()
    if not site_exists:
        raise FunctionalLocationNotFound("SITE_NOT_FOUND")
    if parent_id is not None:
        # Lecture sous RLS : un parent d'un autre tenant est introuvable. La clé
        # étrangère seule ne suffirait pas, elle ignore l'isolation des tenants.
        parent_site = connection.execute(
            text("SELECT site_id FROM functional_locations WHERE id = :id"), {"id": parent_id}
        ).scalar()
        if parent_site is None:
            raise FunctionalLocationNotFound("PARENT_FUNCTIONAL_LOCATION_NOT_FOUND")
        if parent_site != site_id:
            raise FunctionalLocationConflict("PARENT_FUNCTIONAL_LOCATION_OTHER_SITE")
    if space_id is not None:
        check_space_for_location(connection, space_id=space_id, site_id=site_id)

    location_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO functional_locations (id, tenant_id, site_id, parent_id, code, name, "
            "kind) VALUES (:id, :tenant_id, :site_id, :parent_id, :code, :name, :kind)"
        ),
        {
            "id": location_id,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "parent_id": parent_id,
            "code": code,
            "name": name,
            "kind": kind,
        },
    )
    if space_id is not None:
        record_location_space(
            connection,
            tenant_id=tenant_id,
            functional_location_id=location_id,
            space_id=space_id,
            valid_from=datetime.now(UTC),
            changed_by=created_by,
            reason="emplacement initial",
        )
    return location_id


def get_functional_location(
    connection: Connection, location_id: uuid.UUID
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                "SELECT id, site_id, parent_id, code, name, kind, space_id, created_at, "
                "archived_at FROM functional_locations WHERE id = :id"
            ),
            {"id": location_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def assign_physical_unit(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    functional_location_id: uuid.UUID,
    physical_unit_id: uuid.UUID,
    valid_from: datetime | None = None,
    changed_by: str = "systeme:affectation",
) -> uuid.UUID:
    """Installe un exemplaire physique à une position fonctionnelle.

    Si un autre exemplaire occupait déjà cette position, son affectation est
    close (valid_to renseigné) sans être supprimée ni modifiée dans son
    contenu : l'historique complet reste consultable, seule l'affectation
    courante change (voir ADR 001, modèle bitemporel).

    Le cycle de vie suit (ADR 012, 2.9) : le nouvel exemplaire passe
    « installé », l'ancien « déposé ». Un exemplaire déjà monté ailleurs, hors
    service définitif ou éliminé ne peut pas être installé.
    """
    valid_from = valid_from or datetime.now(UTC)

    previous = get_current_occupant(connection, functional_location_id=functional_location_id)
    if previous == physical_unit_id:
        raise LifecycleError("UNIT_ALREADY_AT_LOCATION")
    state = current_state(connection, physical_unit_id)
    if state not in INSTALLABLE_STATES:
        raise LifecycleError("UNIT_NOT_INSTALLABLE", state=state)

    connection.execute(
        text(
            "UPDATE functional_location_assignments SET valid_to = :valid_from "
            "WHERE functional_location_id = :functional_location_id AND valid_to IS NULL"
        ),
        {"valid_from": valid_from, "functional_location_id": functional_location_id},
    )

    assignment_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO functional_location_assignments
                (id, tenant_id, functional_location_id, physical_unit_id, valid_from)
            VALUES
                (:id, :tenant_id, :functional_location_id, :physical_unit_id, :valid_from)
            """
        ),
        {
            "id": assignment_id,
            "tenant_id": tenant_id,
            "functional_location_id": functional_location_id,
            "physical_unit_id": physical_unit_id,
            "valid_from": valid_from,
        },
    )

    if previous is not None and current_state(connection, previous) in MOUNTED_STATES:
        change_state(
            connection,
            tenant_id=tenant_id,
            physical_unit_id=previous,
            to_state="removed",
            occurred_at=valid_from,
            changed_by=changed_by,
            note="remplacé à sa position",
            via_assignment=True,
        )
    change_state(
        connection,
        tenant_id=tenant_id,
        physical_unit_id=physical_unit_id,
        to_state="installed",
        occurred_at=valid_from,
        changed_by=changed_by,
        via_assignment=True,
    )
    return assignment_id


def get_current_occupant(
    connection: Connection, *, functional_location_id: uuid.UUID
) -> uuid.UUID | None:
    """Renvoie l'exemplaire physique occupant actuellement cette position."""
    return connection.execute(
        text(
            "SELECT physical_unit_id FROM functional_location_assignments "
            "WHERE functional_location_id = :functional_location_id AND valid_to IS NULL"
        ),
        {"functional_location_id": functional_location_id},
    ).scalar()


def get_occupant_as_of(
    connection: Connection, *, functional_location_id: uuid.UUID, as_of: datetime
) -> uuid.UUID | None:
    """Reconstruit quel exemplaire occupait cette position à une date donnée."""
    return connection.execute(
        text(
            "SELECT physical_unit_id FROM functional_location_assignments "
            "WHERE functional_location_id = :functional_location_id "
            "AND valid_from <= :as_of AND (valid_to IS NULL OR valid_to > :as_of)"
        ),
        {"functional_location_id": functional_location_id, "as_of": as_of},
    ).scalar()
