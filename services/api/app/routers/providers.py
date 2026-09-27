"""Prestataires de maintenance (ADR 012, section 2.2) : un répertoire simple,
seul type de nœud pouvant être l'objet du prédicat « maintainedBy »
(app/graph_vocabulary.py). Un site, un espace, une position fonctionnelle ou
un exemplaire déclare qui le maintient via POST /relations, pas ici — ce
routeur ne gère que l'identité du prestataire lui-même."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.errors import ApiError
from app.schemas import ProviderCreate, ProviderOut, ProviderUpdate

router = APIRouter()

_MANAGE_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")

_COLUMNS = "id, name, contact_name, contact_email, contact_phone, created_by, created_at"


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


def _read_provider(connection: Connection, provider_id: uuid.UUID) -> ProviderOut:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM providers WHERE id = :id"), {"id": provider_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "PROVIDER_NOT_FOUND")
    return ProviderOut(**row)


@router.post("/providers", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
def create_provider(
    body: ProviderCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> ProviderOut:
    provider_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO providers "
            "(id, tenant_id, name, contact_name, contact_email, contact_phone, created_by) "
            "VALUES (:id, :tenant_id, :name, :contact_name, :contact_email, :contact_phone, "
            ":created_by)"
        ),
        {
            "id": provider_id,
            "tenant_id": tenant_id,
            "name": body.name,
            "contact_name": body.contact_name,
            "contact_email": body.contact_email,
            "contact_phone": body.contact_phone,
            "created_by": _actor(claims),
        },
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="provider.created",
        entity_type="provider",
        entity_id=str(provider_id),
        payload={"name": body.name},
    )
    return _read_provider(connection, provider_id)


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[ProviderOut]:
    rows = connection.execute(
        text(f"SELECT {_COLUMNS} FROM providers ORDER BY name")
    ).mappings()
    return [ProviderOut(**row) for row in rows]


@router.get("/providers/{provider_id}", response_model=ProviderOut)
def read_provider(
    provider_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> ProviderOut:
    return _read_provider(connection, provider_id)


@router.put("/providers/{provider_id}", response_model=ProviderOut)
def update_provider(
    provider_id: uuid.UUID,
    body: ProviderUpdate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> ProviderOut:
    """Coordonnées d'un prestataire (nom, contact) : pas un fait historisé
    comme une intervention, une simple fiche à jour — contrairement aux
    propriétés techniques d'un actif (app/properties.py), aucun historique
    n'est attendu ici."""
    _read_provider(connection, provider_id)
    connection.execute(
        text(
            "UPDATE providers SET name = :name, contact_name = :contact_name, "
            "contact_email = :contact_email, contact_phone = :contact_phone WHERE id = :id"
        ),
        {
            "id": provider_id,
            "name": body.name,
            "contact_name": body.contact_name,
            "contact_email": body.contact_email,
            "contact_phone": body.contact_phone,
        },
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="provider.updated",
        entity_type="provider",
        entity_id=str(provider_id),
        payload={"name": body.name},
    )
    return _read_provider(connection, provider_id)
