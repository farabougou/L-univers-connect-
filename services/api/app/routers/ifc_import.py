"""Import BIM/IFC (ADR 011, section 2) : envoi d'un fichier IFC, propositions
d'espaces et d'équipements à valider avant qu'ils ne rejoignent le
registre. Même dance en deux temps que les photos et les plans (ADR 006) :
URL présignée, envoi direct au stockage, puis confirmation qui déclenche
l'analyse."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.errors import ApiError, api_error
from app.ifc_import import (
    ImportBatchNotFound,
    ImportProposalConflict,
    ImportProposalInvalid,
    ImportProposalNotFound,
    accept_proposal,
    create_batch,
    get_batch,
    list_batches,
    list_proposals,
    mark_batch_failed,
    reject_proposal,
    store_parse_result,
)
from app.importers.ifc_parser import MAX_FILE_SIZE_BYTES, IfcParseError, parse_ifc_bytes
from app.schemas import (
    IfcImportBatchCreate,
    IfcImportBatchOut,
    IfcImportProposalOut,
    IfcImportProposalReject,
    IfcImportUploadUrlOut,
    IfcImportUploadUrlRequest,
)
from app.spatial import SpatialConflict, SpatialNotFound
from app.storage import (
    ObjectTooLarge,
    build_ifc_import_object_key,
    create_presigned_upload_url,
    download_object_bytes,
    ifc_import_key_belongs_to,
)

router = APIRouter()

_MANAGE_REGISTRY_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict) -> str:
    return claims.get("sub") or "inconnu"


def _check_site_exists(connection: Connection, site_id: uuid.UUID) -> None:
    exists = connection.execute(
        text("SELECT 1 FROM sites WHERE id = :id"), {"id": site_id}
    ).scalar()
    if not exists:
        raise ApiError(404, "SITE_NOT_FOUND")


def _batch_or_404(connection: Connection, batch_id: uuid.UUID) -> dict:
    batch = get_batch(connection, batch_id)
    if batch is None:
        raise ApiError(404, "IFC_IMPORT_BATCH_NOT_FOUND")
    return batch


def _to_batch_out(row: dict) -> IfcImportBatchOut:
    return IfcImportBatchOut(
        id=row["id"],
        site_id=row["site_id"],
        filename=row["filename"],
        sha256=row["sha256"],
        status=row["status"],
        error_code=row["error_code"],
        ifc_schema=row["ifc_schema"],
        space_proposal_count=row["space_proposal_count"],
        equipment_proposal_count=row["equipment_proposal_count"],
        skipped_element_count=row["skipped_element_count"],
        uploaded_by=row["uploaded_by"],
        uploaded_at=row["uploaded_at"],
    )


def _to_proposal_out(row: dict) -> IfcImportProposalOut:
    return IfcImportProposalOut(**row)


@router.post("/sites/{site_id}/ifc-imports/upload-url", response_model=IfcImportUploadUrlOut)
def create_ifc_import_upload_url(
    site_id: uuid.UUID,
    body: IfcImportUploadUrlRequest,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> IfcImportUploadUrlOut:
    _check_site_exists(connection, site_id)
    object_key = build_ifc_import_object_key(
        tenant_id=tenant_id, site_id=site_id, filename=body.filename
    )
    upload_url = create_presigned_upload_url(object_key, content_type="application/octet-stream")
    return IfcImportUploadUrlOut(upload_url=upload_url, object_key=object_key)


@router.post(
    "/sites/{site_id}/ifc-imports",
    response_model=IfcImportBatchOut,
    status_code=status.HTTP_201_CREATED,
)
def create_ifc_import(
    site_id: uuid.UUID,
    body: IfcImportBatchCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> IfcImportBatchOut:
    """Confirme l'envoi et lance l'analyse tout de suite : un fichier IFC
    reste de taille raisonnable (bâtiment par bâtiment), contrairement à un
    modèle 3D complet. Le lot renvoyé porte son statut (prêt ou échoué) :
    jamais une erreur HTTP pour un fichier simplement invalide, qui reste
    une réponse normale et déjà tracée."""
    _check_site_exists(connection, site_id)
    if not ifc_import_key_belongs_to(body.object_key, tenant_id=tenant_id, site_id=site_id):
        raise ApiError(422, "IFC_IMPORT_STORAGE_KEY_FOREIGN")

    batch_id = create_batch(
        connection,
        tenant_id=tenant_id,
        site_id=site_id,
        storage_key=body.object_key,
        filename=body.filename,
        sha256=body.sha256,
        uploaded_by=_actor(claims),
    )

    try:
        content = download_object_bytes(body.object_key, max_size_bytes=MAX_FILE_SIZE_BYTES)
        result = parse_ifc_bytes(content)
    except ObjectTooLarge:
        mark_batch_failed(connection, batch_id=batch_id, error_code="IFC_IMPORT_FILE_TOO_LARGE")
    except IfcParseError as exc:
        mark_batch_failed(connection, batch_id=batch_id, error_code=exc.code)
    else:
        store_parse_result(connection, tenant_id=tenant_id, batch_id=batch_id, result=result)
        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor=_actor(claims),
            action="ifc_import.parsed",
            entity_type="ifc_import_batch",
            entity_id=str(batch_id),
            payload={
                "space_proposal_count": len(result.spaces),
                "equipment_proposal_count": len(result.equipment),
            },
        )

    return _to_batch_out(_batch_or_404(connection, batch_id))


@router.get("/sites/{site_id}/ifc-imports", response_model=list[IfcImportBatchOut])
def list_ifc_imports(
    site_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[IfcImportBatchOut]:
    _check_site_exists(connection, site_id)
    return [_to_batch_out(row) for row in list_batches(connection, site_id=site_id)]


@router.get("/ifc-imports/{batch_id}", response_model=IfcImportBatchOut)
def read_ifc_import(
    batch_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> IfcImportBatchOut:
    return _to_batch_out(_batch_or_404(connection, batch_id))


@router.get("/ifc-imports/{batch_id}/proposals", response_model=list[IfcImportProposalOut])
def list_ifc_import_proposals(
    batch_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    proposal_type: str | None = None,
    proposal_status: str | None = None,
) -> list[IfcImportProposalOut]:
    _batch_or_404(connection, batch_id)
    rows = list_proposals(
        connection, batch_id=batch_id, proposal_type=proposal_type, status=proposal_status
    )
    return [_to_proposal_out(row) for row in rows]


@router.post("/ifc-import-proposals/{proposal_id}/accept", response_model=IfcImportProposalOut)
def accept_ifc_import_proposal(
    proposal_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> IfcImportProposalOut:
    try:
        proposal = accept_proposal(
            connection, tenant_id=tenant_id, proposal_id=proposal_id, decided_by=_actor(claims)
        )
    except (ImportProposalNotFound, ImportBatchNotFound) as exc:
        raise api_error(exc, 404) from exc
    except (ImportProposalConflict, SpatialConflict) as exc:
        raise api_error(exc, 409) from exc
    except (ImportProposalInvalid, SpatialNotFound) as exc:
        raise api_error(exc, 422) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="ifc_import_proposal.accepted",
        entity_type="ifc_import_proposal",
        entity_id=str(proposal_id),
        payload={
            "proposal_type": proposal["proposal_type"],
            "created_node_id": str(proposal["created_node_id"]),
        },
    )
    return _to_proposal_out(proposal)


@router.post("/ifc-import-proposals/{proposal_id}/reject", response_model=IfcImportProposalOut)
def reject_ifc_import_proposal(
    proposal_id: uuid.UUID,
    body: IfcImportProposalReject,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> IfcImportProposalOut:
    try:
        proposal = reject_proposal(
            connection, proposal_id=proposal_id, decided_by=_actor(claims), reason=body.reason
        )
    except ImportProposalNotFound as exc:
        raise api_error(exc, 404) from exc
    except ImportProposalConflict as exc:
        raise api_error(exc, 409) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="ifc_import_proposal.rejected",
        entity_type="ifc_import_proposal",
        entity_id=str(proposal_id),
        payload={"reason": body.reason},
    )
    return _to_proposal_out(proposal)
