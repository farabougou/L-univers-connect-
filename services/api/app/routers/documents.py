"""Documents d'équipement (section 36, point 10 — directive UI/dashboard) :
manuels, certificats, garanties, fiches techniques, contrats, rapports de
conformité. Même mécanique que les plans 2D (URL présignée puis
confirmation), voir app/routers/floor_plans.py.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.documents import (
    DocumentInvalid,
    get_document,
    list_documents,
    list_portfolio_documents,
    record_document,
)
from app.errors import ApiError, api_error
from app.graph import get_node
from app.schemas import (
    DocumentCreate,
    DocumentOut,
    DocumentUploadUrlOut,
    DocumentUploadUrlRequest,
    PortfolioDocumentOut,
)
from app.storage import (
    build_document_object_key,
    create_presigned_download_url,
    create_presigned_upload_url,
    document_key_belongs_to,
)

router = APIRouter()

_MANAGE_REGISTRY_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict) -> str:
    return claims.get("sub") or "inconnu"


def _check_functional_location_exists(
    connection: Connection, functional_location_id: uuid.UUID
) -> None:
    if get_node(connection, functional_location_id) is None:
        raise ApiError(404, "FUNCTIONAL_LOCATION_NOT_FOUND")


def _to_out(row: dict) -> DocumentOut:
    return DocumentOut(
        id=row["id"],
        functional_location_id=row["functional_location_id"],
        category=row["category"],
        filename=row["filename"],
        content_type=row["content_type"],
        download_url=create_presigned_download_url(row["storage_key"]),
        uploaded_by=row["uploaded_by"],
        uploaded_at=row["uploaded_at"],
    )


def _to_portfolio_out(row: dict) -> PortfolioDocumentOut:
    return PortfolioDocumentOut(
        id=row["id"],
        functional_location_id=row["functional_location_id"],
        functional_location_code=row["functional_location_code"],
        functional_location_name=row["functional_location_name"],
        category=row["category"],
        filename=row["filename"],
        content_type=row["content_type"],
        download_url=create_presigned_download_url(row["storage_key"]),
        uploaded_by=row["uploaded_by"],
        uploaded_at=row["uploaded_at"],
    )


@router.post(
    "/functional-locations/{functional_location_id}/documents/upload-url",
    response_model=DocumentUploadUrlOut,
)
def create_document_upload_url(
    functional_location_id: uuid.UUID,
    body: DocumentUploadUrlRequest,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> DocumentUploadUrlOut:
    _check_functional_location_exists(connection, functional_location_id)

    object_key = build_document_object_key(
        tenant_id=tenant_id, functional_location_id=functional_location_id, filename=body.filename
    )
    upload_url = create_presigned_upload_url(object_key, content_type=body.content_type)
    return DocumentUploadUrlOut(upload_url=upload_url, object_key=object_key)


@router.post(
    "/functional-locations/{functional_location_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    functional_location_id: uuid.UUID,
    body: DocumentCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> DocumentOut:
    _check_functional_location_exists(connection, functional_location_id)
    if not document_key_belongs_to(
        body.object_key, tenant_id=tenant_id, functional_location_id=functional_location_id
    ):
        raise ApiError(422, "DOCUMENT_STORAGE_KEY_FOREIGN")

    try:
        document_id = record_document(
            connection,
            tenant_id=tenant_id,
            functional_location_id=functional_location_id,
            category=body.category,
            storage_key=body.object_key,
            content_type=body.content_type,
            filename=body.filename,
            sha256=body.sha256,
            uploaded_by=_actor(claims),
        )
    except DocumentInvalid as exc:
        raise api_error(exc, exc.status) from exc

    row = get_document(connection, document_id)
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="document.uploaded",
        entity_type="document",
        entity_id=str(document_id),
        payload={
            "functional_location_id": str(functional_location_id),
            "category": row["category"],
        },
    )
    return _to_out(row)


@router.get(
    "/functional-locations/{functional_location_id}/documents",
    response_model=list[DocumentOut],
)
def list_documents_route(
    functional_location_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[DocumentOut]:
    _check_functional_location_exists(connection, functional_location_id)
    return [_to_out(row) for row in list_documents(connection, functional_location_id)]


@router.get("/documents/portfolio", response_model=list[PortfolioDocumentOut])
def list_portfolio_documents_route(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[PortfolioDocumentOut]:
    """Bibliothèque de tout le portefeuille (page Documents, section 36,
    point 10) : tous les documents du tenant, avec l'équipement visé."""
    return [_to_portfolio_out(row) for row in list_portfolio_documents(connection)]


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document_route(
    document_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> DocumentOut:
    row = get_document(connection, document_id)
    if row is None:
        raise ApiError(404, "DOCUMENT_NOT_FOUND")
    return _to_out(row)
