"""Déclaration annuelle OPERAT / Éco Énergie Tertiaire (décret tertiaire,
arrêté du 10 avril 2020 — voir docs/regulatory/01-operat-eco-energie-tertiaire.md).

Une déclaration par site et par année de référence, workflow brouillon →
prêt → transmis. La transmission réelle au portail ADEME reste aujourd'hui
manuelle (aucun accès API officiel disponible, aucun identifiant fourni) :
`record_manual_submission` enregistre qu'une personne l'a faite sur le
portail, elle ne la simule jamais. `export_operat_summary` produit les
chiffres à saisir, dans le même ordre que le portail.

`OperatApiAdapter` est l'interface abstraite pour le jour où une
intégration programmatique existera (API officielle, identifiants client) :
`NotConfiguredOperatApiAdapter` est son unique implémentation aujourd'hui,
qui échoue explicitement plutôt que de prétendre réussir
(`DEFERRED_EXTERNAL_INTEGRATION`, directive de Mohamed du 02/10/2026).
"""

import uuid
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError

_COLUMNS = (
    "id, site_id, reference_year, status, floor_area_m2, activity_category, "
    "electricity_kwh, gas_kwh, heat_network_kwh, other_kwh, other_label, notes, "
    "created_by, created_at, updated_by, updated_at, submitted_by, submitted_at, "
    "submission_reference"
)


class OperatError(DomainError, ValueError):
    pass


class OperatDeclarationNotFound(DomainError, LookupError):
    status = 404


class OperatDeclarationConflict(DomainError, ValueError):
    status = 409


def get_declaration(connection: Connection, declaration_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM operat_declarations WHERE id = :id"),
            {"id": declaration_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_declarations(connection: Connection, *, site_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(
                f"SELECT {_COLUMNS} FROM operat_declarations WHERE site_id = :site_id "
                "ORDER BY reference_year DESC"
            ),
            {"site_id": site_id},
        ).mappings()
    ]


def create_draft_declaration(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    reference_year: int,
    created_by: str,
) -> dict[str, Any]:
    site_exists = connection.execute(
        text("SELECT 1 FROM sites WHERE id = :id"), {"id": site_id}
    ).scalar()
    if not site_exists:
        raise OperatDeclarationNotFound("SITE_NOT_FOUND")
    existing = connection.execute(
        text(
            "SELECT 1 FROM operat_declarations WHERE site_id = :site_id "
            "AND reference_year = :reference_year"
        ),
        {"site_id": site_id, "reference_year": reference_year},
    ).scalar()
    if existing:
        raise OperatDeclarationConflict("OPERAT_DECLARATION_ALREADY_EXISTS")

    declaration_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO operat_declarations (id, tenant_id, site_id, reference_year, "
            "created_by) VALUES (:id, :tenant_id, :site_id, :reference_year, :created_by)"
        ),
        {
            "id": declaration_id,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "reference_year": reference_year,
            "created_by": created_by,
        },
    )
    return get_declaration(connection, declaration_id)


def _check_non_negative(value: float | None, field: str) -> None:
    if value is not None and value < 0:
        raise OperatError("OPERAT_QUANTITY_NEGATIVE", field=field)


def update_declaration(
    connection: Connection,
    *,
    declaration_id: uuid.UUID,
    floor_area_m2: float | None = None,
    activity_category: str | None = None,
    electricity_kwh: float | None = None,
    gas_kwh: float | None = None,
    heat_network_kwh: float | None = None,
    other_kwh: float | None = None,
    other_label: str | None = None,
    notes: str | None = None,
    updated_by: str,
    updated_at: datetime,
) -> dict[str, Any]:
    """Modifie une déclaration : un brouillon librement, une déclaration
    « prête » aussi (elle n'est gelée qu'une fois transmise — voir le
    déclencheur `operat_declarations_protect_update`, qui refuse toute
    modification une fois `submitted`, quel que soit le domaine)."""
    declaration = get_declaration(connection, declaration_id)
    if declaration is None:
        raise OperatDeclarationNotFound("OPERAT_DECLARATION_NOT_FOUND")
    if declaration["status"] == "submitted":
        raise OperatError("OPERAT_DECLARATION_ALREADY_SUBMITTED")
    for value, field in (
        (floor_area_m2, "floor_area_m2"),
        (electricity_kwh, "electricity_kwh"),
        (gas_kwh, "gas_kwh"),
        (heat_network_kwh, "heat_network_kwh"),
        (other_kwh, "other_kwh"),
    ):
        _check_non_negative(value, field)

    connection.execute(
        text(
            "UPDATE operat_declarations SET floor_area_m2 = :floor_area_m2, "
            "activity_category = :activity_category, electricity_kwh = :electricity_kwh, "
            "gas_kwh = :gas_kwh, heat_network_kwh = :heat_network_kwh, "
            "other_kwh = :other_kwh, other_label = :other_label, notes = :notes, "
            "updated_by = :updated_by, updated_at = :updated_at WHERE id = :id"
        ),
        {
            "id": declaration_id,
            "floor_area_m2": floor_area_m2,
            "activity_category": activity_category,
            "electricity_kwh": electricity_kwh,
            "gas_kwh": gas_kwh,
            "heat_network_kwh": heat_network_kwh,
            "other_kwh": other_kwh,
            "other_label": other_label,
            "notes": notes,
            "updated_by": updated_by,
            "updated_at": updated_at,
        },
    )
    return get_declaration(connection, declaration_id)


_REQUIRED_FOR_READY = ("floor_area_m2", "activity_category")


def mark_ready(connection: Connection, *, declaration_id: uuid.UUID) -> dict[str, Any]:
    """Un brouillon devient prêt seulement si l'essentiel est renseigné et
    qu'au moins une consommation est déclarée — jamais une déclaration vide
    transmise par automatisme."""
    declaration = get_declaration(connection, declaration_id)
    if declaration is None:
        raise OperatDeclarationNotFound("OPERAT_DECLARATION_NOT_FOUND")
    if declaration["status"] != "draft":
        raise OperatError("OPERAT_DECLARATION_NOT_DRAFT")
    missing = [field for field in _REQUIRED_FOR_READY if not declaration[field]]
    consumptions = (
        declaration["electricity_kwh"],
        declaration["gas_kwh"],
        declaration["heat_network_kwh"],
        declaration["other_kwh"],
    )
    if all(value is None for value in consumptions):
        missing.append("consumption")
    if missing:
        raise OperatError("OPERAT_DECLARATION_INCOMPLETE", fields=sorted(missing))

    connection.execute(
        text("UPDATE operat_declarations SET status = 'ready' WHERE id = :id"),
        {"id": declaration_id},
    )
    return get_declaration(connection, declaration_id)


def record_manual_submission(
    connection: Connection,
    *,
    declaration_id: uuid.UUID,
    submitted_by: str,
    submitted_at: datetime,
    submission_reference: str | None = None,
) -> dict[str, Any]:
    """Enregistre qu'une personne a transmis la déclaration sur le portail
    OPERAT (aucune transmission automatique aujourd'hui, voir le module).
    Gelée dès cet instant (déclencheur en base)."""
    declaration = get_declaration(connection, declaration_id)
    if declaration is None:
        raise OperatDeclarationNotFound("OPERAT_DECLARATION_NOT_FOUND")
    if declaration["status"] != "ready":
        raise OperatError("OPERAT_DECLARATION_NOT_READY")

    connection.execute(
        text(
            "UPDATE operat_declarations SET status = 'submitted', submitted_by = :submitted_by, "
            "submitted_at = :submitted_at, submission_reference = :submission_reference "
            "WHERE id = :id"
        ),
        {
            "id": declaration_id,
            "submitted_by": submitted_by,
            "submitted_at": submitted_at,
            "submission_reference": submission_reference,
        },
    )
    return get_declaration(connection, declaration_id)


def export_operat_summary(declaration: dict[str, Any]) -> dict[str, Any]:
    """Chiffres à saisir sur le portail OPERAT, dans l'ordre où il les
    demande — jamais un format de fichier réglementaire deviné (aucune
    spécification d'import officielle publiée à ce jour)."""
    return {
        "annee_reference": declaration["reference_year"],
        "surface_m2": declaration["floor_area_m2"],
        "categorie_activite": declaration["activity_category"],
        "electricite_kwh": declaration["electricity_kwh"],
        "gaz_kwh": declaration["gas_kwh"],
        "reseau_chaleur_kwh": declaration["heat_network_kwh"],
        "autre_kwh": declaration["other_kwh"],
        "autre_libelle": declaration["other_label"],
    }


# --- Interface abstraite pour une future intégration programmatique --------
# Aucun identifiant, aucun accès API ADEME fourni à ce jour : l'interface et
# son adaptateur existent, l'appel réel est différé
# (`DEFERRED_EXTERNAL_INTEGRATION`), jamais simulé par un faux succès.


class OperatApiAdapter(Protocol):
    def submit(self, summary: dict[str, Any]) -> dict[str, Any]:
        """Transmet une déclaration via l'API officielle OPERAT. Renvoie un
        accusé de réception réel (référence, date) — jamais une valeur
        inventée."""
        ...


class NotConfiguredOperatApiAdapter:
    """Seule implémentation aujourd'hui : échoue explicitement plutôt que de
    prétendre avoir transmis quoi que ce soit."""

    def submit(self, summary: dict[str, Any]) -> dict[str, Any]:
        raise OperatError("OPERAT_API_NOT_CONFIGURED")


DEFAULT_API_ADAPTER: OperatApiAdapter = NotConfiguredOperatApiAdapter()
