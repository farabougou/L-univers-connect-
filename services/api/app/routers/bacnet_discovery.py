"""Découverte BACnet (BACnet V1, directive de Mohamed du 27/09/2026) : un
scan produit des propositions à valider avant qu'un point n'existe
réellement — même principe que l'import IFC (`app/routers/ifc_import.py`),
dont ce routeur reprend volontairement la forme."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.bacnet_discovery import (
    DiscoveryBatchNotFound,
    DiscoveryProposalConflict,
    DiscoveryProposalNotFound,
    accept_proposal,
    get_batch,
    list_batches,
    list_proposals,
    reason_message,
    reject_proposal,
    run_discovery,
)
from app.deps import get_tenant_connection, get_tenant_id
from app.errors import ApiError, api_error
from app.i18n import negotiate_locale
from app.point_vocabulary import PointVocabularyError
from app.points import PointConflict, PointNotFound
from app.schemas import (
    BacnetDiscoveryBatchOut,
    BacnetDiscoveryProposalAccept,
    BacnetDiscoveryProposalOut,
    BacnetDiscoveryProposalReject,
    BacnetDiscoveryScanRequest,
)

router = APIRouter()

_MANAGE_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict) -> str:
    return claims.get("sub") or "inconnu"


def _check_equipment_exists(connection: Connection, equipment_id: uuid.UUID) -> None:
    exists = connection.execute(
        text("SELECT 1 FROM functional_locations WHERE id = :id"), {"id": equipment_id}
    ).scalar()
    if not exists:
        raise ApiError(404, "FUNCTIONAL_LOCATION_NOT_FOUND")


def _batch_or_404(connection: Connection, batch_id: uuid.UUID) -> dict:
    batch = get_batch(connection, batch_id)
    if batch is None:
        raise ApiError(404, "BACNET_DISCOVERY_BATCH_NOT_FOUND")
    return batch


def _to_batch_out(row: dict) -> BacnetDiscoveryBatchOut:
    return BacnetDiscoveryBatchOut(**row)


def _to_proposal_out(row: dict, locale: str) -> BacnetDiscoveryProposalOut:
    return BacnetDiscoveryProposalOut(
        **row, reason_message=reason_message(row["reason_code"], locale)
    )


@router.post(
    "/bacnet-discovery/scan",
    response_model=BacnetDiscoveryBatchOut,
    status_code=status.HTTP_201_CREATED,
)
def scan_bacnet_device(
    body: BacnetDiscoveryScanRequest,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> BacnetDiscoveryBatchOut:
    """Scan synchrone (Who-Is puis inventaire des objets « point ») : un
    appareil injoignable ou une inventaire en échec referme le lot en
    'failed', jamais une erreur HTTP pour une simple indisponibilité réseau
    déjà tracée dans le lot lui-même (même principe que l'import IFC)."""
    _check_equipment_exists(connection, body.equipment_id)

    batch_id = run_discovery(
        connection,
        tenant_id=tenant_id,
        equipment_id=body.equipment_id,
        address=body.address,
        scanned_by=_actor(claims),
        timeout=body.timeout,
    )
    batch = _batch_or_404(connection, batch_id)

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="bacnet_discovery.scanned",
        entity_type="bacnet_discovery_batch",
        entity_id=str(batch_id),
        payload={
            "equipment_id": str(body.equipment_id),
            "address": body.address,
            "status": batch["status"],
            "error_code": batch["error_code"],
            "proposal_count": batch["proposal_count"],
        },
    )
    return _to_batch_out(batch)


@router.get("/bacnet-discovery/batches", response_model=list[BacnetDiscoveryBatchOut])
def list_bacnet_discovery_batches(
    equipment_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[BacnetDiscoveryBatchOut]:
    _check_equipment_exists(connection, equipment_id)
    return [_to_batch_out(row) for row in list_batches(connection, equipment_id=equipment_id)]


@router.get("/bacnet-discovery/batches/{batch_id}", response_model=BacnetDiscoveryBatchOut)
def read_bacnet_discovery_batch(
    batch_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> BacnetDiscoveryBatchOut:
    return _to_batch_out(_batch_or_404(connection, batch_id))


@router.get(
    "/bacnet-discovery/batches/{batch_id}/proposals",
    response_model=list[BacnetDiscoveryProposalOut],
)
def list_bacnet_discovery_proposals(
    batch_id: uuid.UUID,
    request: Request,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    proposal_status: str | None = None,
) -> list[BacnetDiscoveryProposalOut]:
    _batch_or_404(connection, batch_id)
    locale = negotiate_locale(request.headers.get("accept-language"))
    rows = list_proposals(connection, batch_id=batch_id, status=proposal_status)
    return [_to_proposal_out(row, locale) for row in rows]


@router.post(
    "/bacnet-discovery-proposals/{proposal_id}/accept",
    response_model=BacnetDiscoveryProposalOut,
)
def accept_bacnet_discovery_proposal(
    proposal_id: uuid.UUID,
    body: BacnetDiscoveryProposalAccept,
    request: Request,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> BacnetDiscoveryProposalOut:
    try:
        proposal = accept_proposal(
            connection,
            tenant_id=tenant_id,
            proposal_id=proposal_id,
            decided_by=_actor(claims),
            point_class=body.point_class,
            unit=body.unit,
            code=body.code,
            name=body.name,
        )
    except (DiscoveryProposalNotFound, DiscoveryBatchNotFound, PointNotFound) as exc:
        raise api_error(exc, 404) from exc
    except (DiscoveryProposalConflict, PointConflict) as exc:
        raise api_error(exc, 409) from exc
    except PointVocabularyError as exc:
        raise api_error(exc, 422) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="bacnet_discovery_proposal.accepted",
        entity_type="bacnet_discovery_proposal",
        entity_id=str(proposal_id),
        payload={
            "object_type": proposal["object_type"],
            "object_instance": proposal["object_instance"],
            "created_point_id": str(proposal["created_point_id"]),
        },
    )
    locale = negotiate_locale(request.headers.get("accept-language"))
    return _to_proposal_out(proposal, locale)


@router.post(
    "/bacnet-discovery-proposals/{proposal_id}/reject",
    response_model=BacnetDiscoveryProposalOut,
)
def reject_bacnet_discovery_proposal(
    proposal_id: uuid.UUID,
    body: BacnetDiscoveryProposalReject,
    request: Request,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> BacnetDiscoveryProposalOut:
    try:
        proposal = reject_proposal(
            connection, proposal_id=proposal_id, decided_by=_actor(claims), reason=body.reason
        )
    except DiscoveryProposalNotFound as exc:
        raise api_error(exc, 404) from exc
    except DiscoveryProposalConflict as exc:
        raise api_error(exc, 409) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="bacnet_discovery_proposal.rejected",
        entity_type="bacnet_discovery_proposal",
        entity_id=str(proposal_id),
        payload={"reason": body.reason},
    )
    locale = negotiate_locale(request.headers.get("accept-language"))
    return _to_proposal_out(proposal, locale)
