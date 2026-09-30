"""Découverte BACnet (BACnet V1, directive de Mohamed du 27/09/2026 puis
30/09/2026 — exécution par l'Edge) : un scan produit des propositions à
valider avant qu'un point n'existe réellement — même principe que l'import
IFC (`app/routers/ifc_import.py`), dont ce routeur reprend volontairement
la forme.

Deux familles de routes : les routes humaines (`/bacnet-discovery/...`,
rôles applicatifs) et les routes Edge (`/edge/bacnet-discovery/...`, jeton
d'appareil, portée `discovery:execute`) par lesquelles l'agent sur site
récupère les scans à exécuter et rapporte leur résultat — voir l'en-tête de
`app.bacnet_discovery` pour pourquoi le scan ne s'exécute plus dans ce
processus API."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role, require_device_scope
from app.bacnet_discovery import (
    DiscoveryBatchConflict,
    DiscoveryBatchNotFound,
    DiscoveryProposalConflict,
    DiscoveryProposalNotFound,
    accept_proposal,
    complete_discovery,
    fail_discovery,
    get_batch,
    list_batches,
    list_pending_batches,
    list_proposals,
    reason_message,
    reject_proposal,
    request_discovery,
)
from app.connectors.bacnet import BacnetObjectInfo
from app.db import engine
from app.deps import get_tenant_connection, get_tenant_id
from app.errors import ApiError, api_error
from app.i18n import negotiate_locale
from app.point_vocabulary import PointVocabularyError
from app.points import PointConflict, PointNotFound
from app.schemas import (
    BacnetDiscoveryBatchOut,
    BacnetDiscoveryFailureSubmit,
    BacnetDiscoveryPendingOut,
    BacnetDiscoveryProposalAccept,
    BacnetDiscoveryProposalOut,
    BacnetDiscoveryProposalReject,
    BacnetDiscoveryResultSubmit,
    BacnetDiscoveryScanRequest,
)
from app.tenancy import set_tenant_context

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
    return BacnetDiscoveryBatchOut(**{**row, "timeout_seconds": float(row["timeout_seconds"])})


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
    """Demande de scan : crée le lot en 'processing' et renvoie
    immédiatement, sans appel réseau (un appareil BACnet vit sur le réseau
    du site, jamais joignable depuis cette API hébergée) — l'agent Edge sur
    site exécute le scan et rapporte le résultat via les routes
    `/edge/bacnet-discovery/...` ci-dessous. La personne revoit le lot
    passer à 'ready' ou 'failed' en rafraîchissant la fiche équipement."""
    _check_equipment_exists(connection, body.equipment_id)

    batch_id = request_discovery(
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
        action="bacnet_discovery.requested",
        entity_type="bacnet_discovery_batch",
        entity_id=str(batch_id),
        payload={
            "equipment_id": str(body.equipment_id),
            "address": body.address,
            "timeout": body.timeout,
        },
    )
    return _to_batch_out(batch)


@router.get(
    "/edge/bacnet-discovery/pending",
    response_model=list[BacnetDiscoveryPendingOut],
)
def list_pending_bacnet_discovery(
    equipment_id: uuid.UUID,
    claims: Annotated[dict, Depends(require_device_scope("discovery:execute"))],
) -> list[BacnetDiscoveryPendingOut]:
    """Les scans demandés par une personne et pas encore exécutés pour cet
    équipement — l'agent Edge (`scripts/bacnet_discovery_agent.py`) appelle
    cette route à intervalle régulier, comme il le fait déjà pour les
    commandes en attente (`GET /edge/commands`). Même schéma que les autres
    routes Edge (`app/routers/devices.py`, `app/routers/commands.py`) : un
    jeton d'appareil n'est jamais un jeton humain, donc jamais
    `get_tenant_connection`/`get_tenant_id` (qui décodent l'un, pas
    l'autre) — le tenant vient des claims de l'appareil lui-même."""
    tenant_id = uuid.UUID(claims["tenant_id"])
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        rows = list_pending_batches(connection, equipment_id=equipment_id)
    return [
        BacnetDiscoveryPendingOut(**{**row, "timeout_seconds": float(row["timeout_seconds"])})
        for row in rows
    ]


@router.post(
    "/edge/bacnet-discovery/{batch_id}/result",
    response_model=BacnetDiscoveryBatchOut,
)
def submit_bacnet_discovery_result(
    batch_id: uuid.UUID,
    body: BacnetDiscoveryResultSubmit,
    claims: Annotated[dict, Depends(require_device_scope("discovery:execute"))],
) -> BacnetDiscoveryBatchOut:
    """L'agent Edge rapporte ici ce qu'il a réellement lu sur le réseau
    BACnet du site (Who-Is puis inventaire) : ce processus API ne fait que
    la correspondance sémantique et la persistance, jamais le dialogue
    BACnet lui-même."""
    tenant_id = uuid.UUID(claims["tenant_id"])
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        try:
            batch = complete_discovery(
                connection,
                tenant_id=tenant_id,
                batch_id=batch_id,
                device_instance=body.device_instance,
                objects=[BacnetObjectInfo(**obj.model_dump()) for obj in body.objects],
            )
        except DiscoveryBatchNotFound as exc:
            raise api_error(exc, 404) from exc
        except DiscoveryBatchConflict as exc:
            raise api_error(exc, 409) from exc

        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor=f"edge:{claims['device_id']}",
            action="bacnet_discovery.completed",
            entity_type="bacnet_discovery_batch",
            entity_id=str(batch_id),
            payload={
                "device_instance": body.device_instance,
                "object_count": batch["object_count"],
                "proposal_count": batch["proposal_count"],
                "duplicate_count": batch["duplicate_count"],
            },
        )
    return _to_batch_out(batch)


@router.post(
    "/edge/bacnet-discovery/{batch_id}/failure",
    response_model=BacnetDiscoveryBatchOut,
)
def submit_bacnet_discovery_failure(
    batch_id: uuid.UUID,
    body: BacnetDiscoveryFailureSubmit,
    claims: Annotated[dict, Depends(require_device_scope("discovery:execute"))],
) -> BacnetDiscoveryBatchOut:
    """L'agent Edge rapporte ici un échec réel (appareil injoignable,
    inventaire refusé) : jamais une exception silencieuse — la personne voit
    toujours ce qui a été essayé, avec un code d'erreur traduit."""
    tenant_id = uuid.UUID(claims["tenant_id"])
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        try:
            batch = fail_discovery(connection, batch_id=batch_id, error_code=body.error_code)
        except DiscoveryBatchNotFound as exc:
            raise api_error(exc, 404) from exc
        except DiscoveryBatchConflict as exc:
            raise api_error(exc, 409) from exc

        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor=f"edge:{claims['device_id']}",
            action="bacnet_discovery.failed",
            entity_type="bacnet_discovery_batch",
            entity_id=str(batch_id),
            payload={"error_code": body.error_code},
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
