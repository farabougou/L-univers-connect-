import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection


def assign_physical_unit(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    functional_location_id: uuid.UUID,
    physical_unit_id: uuid.UUID,
    valid_from: datetime | None = None,
) -> uuid.UUID:
    """Installe un exemplaire physique à une position fonctionnelle.

    Si un autre exemplaire occupait déjà cette position, son affectation est
    close (valid_to renseigné) sans être supprimée ni modifiée dans son
    contenu : l'historique complet reste consultable, seule l'affectation
    courante change (voir ADR 001, modèle bitemporel).
    """
    valid_from = valid_from or datetime.now(UTC)

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
