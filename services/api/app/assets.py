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


def archive_site(
    connection: Connection, *, site_id: uuid.UUID, archived_by: str
) -> list[uuid.UUID]:
    """Masque un site des listes par défaut, sans toucher à son historique ni
    à ses relations : jamais une suppression (CLAUDE.md, règle non
    négociable 3 — rien n'est écrasé).

    Ses équipements encore actifs sont archivés avec lui (décision du
    23/10/2026) et marqués « archivés avec le site » : aucun équipement actif
    ne reste sur un site archivé, et le désarchivage du site ne remet en
    service que ceux-là. Retourne les équipements archivés par cette
    opération, pour que la route les audite un par un.

    Idempotent pour le site : archiver un site déjà archivé ne change rien et
    ne lève pas d'erreur. L'archivage des équipements est rejoué quand même,
    ce qui range un équipement resté actif sur un site archivé avant la règle."""
    now = datetime.now(UTC)
    updated = connection.execute(
        text(
            "UPDATE sites SET archived_at = :now, archived_by = :by "
            "WHERE id = :id AND archived_at IS NULL"
        ),
        {"now": now, "by": archived_by, "id": site_id},
    ).rowcount
    if not updated and not _site_exists(connection, site_id):
        raise SiteNotFound("SITE_NOT_FOUND")
    archived = connection.execute(
        text(
            "UPDATE functional_locations SET archived_at = :now, archived_by = :by, "
            "archived_with_site = true WHERE site_id = :id AND archived_at IS NULL RETURNING id"
        ),
        {"now": now, "by": archived_by, "id": site_id},
    ).scalars()
    return sorted(archived, key=str)


def unarchive_site(connection: Connection, *, site_id: uuid.UUID) -> list[uuid.UUID]:
    """Réversible par construction : remet le site dans les listes par défaut.

    Les équipements archivés AVEC le site reviennent avec lui ; ceux qu'une
    personne avait archivés elle-même restent archivés (elle ne voulait peut-être
    pas les voir revenir). Retourne les équipements remis en service."""
    updated = connection.execute(
        text(
            "UPDATE sites SET archived_at = NULL, archived_by = NULL "
            "WHERE id = :id AND archived_at IS NOT NULL"
        ),
        {"id": site_id},
    ).rowcount
    if not updated and not _site_exists(connection, site_id):
        raise SiteNotFound("SITE_NOT_FOUND")
    restored = connection.execute(
        text(
            "UPDATE functional_locations SET archived_at = NULL, archived_by = NULL, "
            "archived_with_site = false WHERE site_id = :id AND archived_with_site RETURNING id"
        ),
        {"id": site_id},
    ).scalars()
    return sorted(restored, key=str)


def _site_exists(connection: Connection, site_id: uuid.UUID) -> bool:
    return bool(
        connection.execute(text("SELECT 1 FROM sites WHERE id = :id"), {"id": site_id}).scalar()
    )


def archive_functional_location(
    connection: Connection, *, functional_location_id: uuid.UUID, archived_by: str
) -> None:
    """Même principe que `archive_site`, pour un équipement/emplacement.

    Archiver soi-même un équipement déjà archivé avec son site est une décision
    explicite : il cesse d'être « archivé avec le site » et ne reviendra plus avec lui."""
    updated = connection.execute(
        text(
            "UPDATE functional_locations SET archived_at = :now, archived_by = :by, "
            "archived_with_site = false WHERE id = :id AND archived_at IS NULL"
        ),
        {"now": datetime.now(UTC), "by": archived_by, "id": functional_location_id},
    ).rowcount
    if not updated:
        kept = connection.execute(
            text(
                "UPDATE functional_locations SET archived_with_site = false "
                "WHERE id = :id AND archived_with_site"
            ),
            {"id": functional_location_id},
        ).rowcount
        if not kept and get_functional_location(connection, functional_location_id) is None:
            raise FunctionalLocationNotFound("FUNCTIONAL_LOCATION_NOT_FOUND")


def unarchive_functional_location(
    connection: Connection, *, functional_location_id: uuid.UUID
) -> None:
    """Remet un équipement en service, sauf si son site est archivé : aucun
    équipement actif ne reste sur un site archivé (désarchivez d'abord le site).

    Le verrou partagé sur le site empêche un archivage du site concurrent de
    passer entre la vérification et la mise à jour (il attend la fin de celle-ci,
    puis archive aussi cet équipement)."""
    row = (
        connection.execute(
            text(
                "SELECT f.archived_at IS NOT NULL AS archived, "
                "s.archived_at IS NOT NULL AS site_archived "
                "FROM functional_locations f JOIN sites s ON s.id = f.site_id "
                "WHERE f.id = :id FOR SHARE OF s"
            ),
            {"id": functional_location_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise FunctionalLocationNotFound("FUNCTIONAL_LOCATION_NOT_FOUND")
    if row["archived"] and row["site_archived"]:
        raise FunctionalLocationConflict("SITE_ARCHIVED")
    connection.execute(
        text(
            "UPDATE functional_locations SET archived_at = NULL, archived_by = NULL, "
            "archived_with_site = false WHERE id = :id AND archived_at IS NOT NULL"
        ),
        {"id": functional_location_id},
    )


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
    # Verrou partagé : un archivage du site concurrent attend la fin de cette création,
    # puis archive aussi le nouvel équipement.
    site = (
        connection.execute(
            text("SELECT archived_at IS NOT NULL AS archived FROM sites WHERE id = :id FOR SHARE"),
            {"id": site_id},
        )
        .mappings()
        .first()
    )
    if site is None:
        raise FunctionalLocationNotFound("SITE_NOT_FOUND")
    if site["archived"]:
        raise FunctionalLocationConflict("SITE_ARCHIVED")
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
