"""Découverte BACnet (BACnet V1, directive de Mohamed du 27/09/2026 puis
30/09/2026 — exécution par l'Edge).

Un scan produit des propositions, jamais des points directement créés —
même principe que l'import IFC (`app.ifc_import`) et pour la même raison :
une correspondance sémantique incertaine (`app.connectors.bacnet_semantics`)
doit rester vérifiable/corrigeable par une personne avant de devenir un
vrai point du Universal Asset Model. Accepter une proposition passe par la
même fonction de création que la saisie manuelle (`app.points.create_point`) :
un seul chemin de création, jamais un second modèle de points pour la
découverte BACnet.

Ce module ne connaît jamais `bacpypes3` directement : seulement les
structures simples renvoyées par `app.connectors.bacnet` et
`app.connectors.bacnet_semantics`. Un changement de bibliothèque BACnet, y
compris une version majeure incompatible, ne touche jamais ce module
(règle non négociable 8). Il ne fait d'ailleurs plus aucun appel réseau du
tout (voir plus bas) : le connecteur BACnet ne s'exécute que côté Edge.

Un objet déjà accepté lors d'un scan précédent (même équipement, même
adresse, même adressage BACnet natif) redevient « duplicate » plutôt qu'une
nouvelle proposition : un scan répété (reconnexion, appareil redémarré) ne
doit jamais produire un second point pour le même objet physique.

Exécution par l'Edge, jamais par le cloud (directive de Mohamed, 30/09/2026) :
un appareil BACnet/IP vit sur le réseau local d'un site, injoignable depuis
l'API hébergée. `request_discovery` se contente donc de créer le lot en
'processing', sans réseau ; l'agent Edge sur site
(`scripts/bacnet_discovery_agent.py`) récupère les scans en attente
(`list_pending_batches`, via `GET /edge/bacnet-discovery/pending`), exécute
lui-même `app.connectors.bacnet.discover_device`/`read_device_objects`, puis
rapporte le résultat (`complete_discovery`) ou l'échec (`fail_discovery`).
Le contrat vu par une personne ne change pas : un lot naît déjà en
'processing' et passe à 'ready'/'failed' plus tard, ce que l'API et
l'interface web savent déjà afficher."""

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.connectors.bacnet import BacnetObjectInfo
from app.connectors.bacnet_semantics import guess_point_class
from app.errors import DomainError
from app.i18n import DEFAULT_LOCALE, load_catalog
from app.points import create_point

_UNCLASSIFIED_REASON = "NO_RELIABLE_SIGNAL"

_BATCH_COLUMNS = (
    "id, equipment_id, address, timeout_seconds, device_instance, status, error_code, "
    "object_count, proposal_count, duplicate_count, scanned_by, scanned_at"
)
_PROPOSAL_COLUMNS = (
    "id, batch_id, object_type, object_instance, object_name, description, "
    "bacnet_units, present_value_preview, value_type, states, "
    "proposed_point_class, proposed_unit, confidence, reason_code, status, "
    "created_point_id, decided_by, decided_at, rejection_reason, created_at"
)


class DiscoveryBatchNotFound(DomainError, LookupError):
    status = 404


class DiscoveryBatchConflict(DomainError, ValueError):
    """Un lot déjà terminé (ready/failed) ne peut plus recevoir de résultat
    ni d'échec — un agent Edge ne rapporte jamais deux fois le même scan."""

    status = 409


class DiscoveryProposalNotFound(DomainError, LookupError):
    status = 404


class DiscoveryProposalConflict(DomainError, ValueError):
    status = 409


def _slug(name: str, *, suffix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "point"
    return f"bacnet-{slug[:40]}-{suffix}"


def get_batch(connection: Connection, batch_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_BATCH_COLUMNS} FROM bacnet_discovery_batches WHERE id = :id"),
            {"id": batch_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_batches(
    connection: Connection, *, equipment_id: uuid.UUID, status: str | None = None
) -> list[dict[str, Any]]:
    query = (
        f"SELECT {_BATCH_COLUMNS} FROM bacnet_discovery_batches WHERE equipment_id = :equipment_id"
    )
    params: dict[str, Any] = {"equipment_id": equipment_id}
    if status is not None:
        query += " AND status = :status"
        params["status"] = status
    query += " ORDER BY scanned_at DESC"
    rows = connection.execute(text(query), params).mappings()
    return [dict(row) for row in rows]


def reason_message(reason_code: str, locale: str = DEFAULT_LOCALE) -> str:
    """La phrase du code de raison, dans la langue de la personne (ADR 013 :
    un code stable est stocké, jamais une phrase générée)."""
    catalog = load_catalog(locale, "bacnet_discovery")["reasons"]
    return catalog.get(reason_code, catalog[_UNCLASSIFIED_REASON])


def get_proposal(connection: Connection, proposal_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_PROPOSAL_COLUMNS} FROM bacnet_discovery_proposals WHERE id = :id"),
            {"id": proposal_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_proposals(
    connection: Connection, *, batch_id: uuid.UUID, status: str | None = None
) -> list[dict[str, Any]]:
    query = f"SELECT {_PROPOSAL_COLUMNS} FROM bacnet_discovery_proposals WHERE batch_id = :batch_id"
    params: dict[str, Any] = {"batch_id": batch_id}
    if status is not None:
        query += " AND status = :status"
        params["status"] = status
    query += " ORDER BY object_type, object_instance"
    rows = connection.execute(text(query), params).mappings()
    return [dict(row) for row in rows]


def _already_accepted(
    connection: Connection, *, equipment_id: uuid.UUID, address: str, obj: BacnetObjectInfo
) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT 1 FROM bacnet_discovery_proposals p "
                "JOIN bacnet_discovery_batches b ON b.id = p.batch_id "
                "WHERE b.equipment_id = :equipment_id AND b.address = :address "
                "AND p.object_type = :object_type AND p.object_instance = :object_instance "
                "AND p.status = 'accepted' LIMIT 1"
            ),
            {
                "equipment_id": equipment_id,
                "address": address,
                "object_type": obj.object_type,
                "object_instance": obj.object_instance,
            },
        ).scalar()
    )


def _insert_proposal(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    obj: BacnetObjectInfo,
    is_duplicate: bool,
) -> None:
    guess = guess_point_class(
        object_type=obj.object_type,
        value_type=obj.value_type,
        units=obj.units,
        object_name=obj.object_name,
        description=obj.description,
    )
    connection.execute(
        text(
            "INSERT INTO bacnet_discovery_proposals "
            "(id, tenant_id, batch_id, object_type, object_instance, object_name, description, "
            "bacnet_units, present_value_preview, value_type, states, proposed_point_class, "
            "proposed_unit, confidence, reason_code, status) VALUES "
            "(:id, :tenant_id, :batch_id, :object_type, :object_instance, :object_name, "
            ":description, :bacnet_units, :present_value_preview, :value_type, "
            "CAST(:states AS JSONB), :proposed_point_class, :proposed_unit, :confidence, "
            ":reason_code, :status)"
        ),
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "batch_id": batch_id,
            "object_type": obj.object_type,
            "object_instance": obj.object_instance,
            "object_name": obj.object_name,
            "description": obj.description,
            "bacnet_units": obj.units,
            "present_value_preview": obj.present_value_preview,
            "value_type": obj.value_type,
            "states": _json(obj.states),
            "proposed_point_class": guess.point_class,
            "proposed_unit": guess.unit,
            "confidence": guess.confidence,
            "reason_code": guess.reason_code,
            "status": "duplicate" if is_duplicate else "proposed",
        },
    )


def _json(value: dict[str, Any] | None) -> str | None:
    return json.dumps(value, sort_keys=True) if value is not None else None


def request_discovery(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    equipment_id: uuid.UUID,
    address: str,
    scanned_by: str,
    timeout: float = 3.0,
) -> uuid.UUID:
    """Demande de scan : crée le lot en 'processing', sans aucun appel
    réseau (voir l'en-tête du module — l'exécution revient à l'agent Edge).
    La personne voit immédiatement son lot « en cours », comme un import IFC
    ou un ordre de travail vient de naître avant d'être traité."""
    batch_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO bacnet_discovery_batches "
            "(id, tenant_id, equipment_id, address, timeout_seconds, scanned_by) "
            "VALUES (:id, :tenant_id, :equipment_id, :address, :timeout_seconds, :scanned_by)"
        ),
        {
            "id": batch_id,
            "tenant_id": tenant_id,
            "equipment_id": equipment_id,
            "address": address,
            "timeout_seconds": timeout,
            "scanned_by": scanned_by,
        },
    )
    return batch_id


def list_pending_batches(
    connection: Connection, *, equipment_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Les lots en attente d'exécution pour cet équipement (statut
    'processing') : ce que l'agent Edge doit encore aller scanner. Filtré
    par équipement, jamais par tenant explicitement ici — la connexion est
    déjà bornée au tenant de l'appareil authentifié par la RLS (voir
    `GET /edge/bacnet-discovery/pending`)."""
    return list_batches(connection, equipment_id=equipment_id, status="processing")


def _batch_or_404(connection: Connection, batch_id: uuid.UUID) -> dict[str, Any]:
    batch = get_batch(connection, batch_id)
    if batch is None:
        raise DiscoveryBatchNotFound("BACNET_DISCOVERY_BATCH_NOT_FOUND")
    return batch


def complete_discovery(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    device_instance: int,
    objects: list[BacnetObjectInfo],
) -> dict[str, Any]:
    """Rapporte le résultat d'un scan exécuté par l'agent Edge : construit
    les propositions (même logique qu'avant, seulement déplacée ici) et
    referme le lot en 'ready'. Jamais appelé deux fois pour le même lot
    (`DiscoveryBatchConflict` sinon) : un scan Edge est un événement, pas
    un flux répété."""
    batch = _batch_or_404(connection, batch_id)
    if batch["status"] != "processing":
        raise DiscoveryBatchConflict("BACNET_DISCOVERY_BATCH_ALREADY_COMPLETED")

    connection.execute(
        text("UPDATE bacnet_discovery_batches SET device_instance = :di WHERE id = :id"),
        {"di": device_instance, "id": batch_id},
    )

    proposal_count = 0
    duplicate_count = 0
    for obj in objects:
        is_duplicate = _already_accepted(
            connection, equipment_id=batch["equipment_id"], address=batch["address"], obj=obj
        )
        _insert_proposal(
            connection, tenant_id=tenant_id, batch_id=batch_id, obj=obj, is_duplicate=is_duplicate
        )
        if is_duplicate:
            duplicate_count += 1
        else:
            proposal_count += 1

    connection.execute(
        text(
            "UPDATE bacnet_discovery_batches SET status = 'ready', object_count = :object_count, "
            "proposal_count = :proposal_count, duplicate_count = :duplicate_count WHERE id = :id"
        ),
        {
            "object_count": len(objects),
            "proposal_count": proposal_count,
            "duplicate_count": duplicate_count,
            "id": batch_id,
        },
    )
    return _batch_or_404(connection, batch_id)


def fail_discovery(
    connection: Connection, *, batch_id: uuid.UUID, error_code: str
) -> dict[str, Any]:
    """Rapporte l'échec d'un scan exécuté par l'agent Edge (appareil
    injoignable, inventaire en échec) : referme le lot en 'failed', jamais
    une exception qui remonterait sans laisser de trace du scan lui-même —
    l'opérateur voit toujours ce qui a été essayé, même en échec."""
    batch = _batch_or_404(connection, batch_id)
    if batch["status"] != "processing":
        raise DiscoveryBatchConflict("BACNET_DISCOVERY_BATCH_ALREADY_COMPLETED")
    _mark_batch_failed(connection, batch_id=batch_id, error_code=error_code)
    return _batch_or_404(connection, batch_id)


def _mark_batch_failed(connection: Connection, *, batch_id: uuid.UUID, error_code: str) -> None:
    connection.execute(
        text(
            "UPDATE bacnet_discovery_batches SET status = 'failed', error_code = :error_code "
            "WHERE id = :id"
        ),
        {"error_code": error_code, "id": batch_id},
    )


def accept_proposal(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    proposal_id: uuid.UUID,
    decided_by: str,
    point_class: str | None = None,
    unit: str | None = None,
    code: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Crée le point réel (`app.points.create_point`) : reste « proposed »
    côté mise en service (mapping_status), la validation reste une étape
    séparée — accepter une découverte n'est pas la commissionner. Une
    personne peut corriger la classe ou l'unité proposées avant d'accepter
    (`point_class`/`unit`), jamais après."""
    proposal = get_proposal(connection, proposal_id)
    if proposal is None:
        raise DiscoveryProposalNotFound("BACNET_DISCOVERY_PROPOSAL_NOT_FOUND")
    if proposal["status"] != "proposed":
        raise DiscoveryProposalConflict("BACNET_DISCOVERY_PROPOSAL_ALREADY_DECIDED")
    batch = get_batch(connection, proposal["batch_id"])

    final_point_class = point_class if point_class is not None else proposal["proposed_point_class"]
    final_unit = unit if unit is not None else proposal["proposed_unit"]
    final_name = (
        name
        or proposal["object_name"]
        or f"{proposal['object_type']} {proposal['object_instance']}"
    )
    final_code = code or _slug(
        final_name, suffix=f"{proposal['object_type']}-{proposal['object_instance']}"
    )

    point_id = create_point(
        connection,
        tenant_id=tenant_id,
        code=final_code,
        name=final_name,
        value_type=proposal["value_type"],
        created_by=decided_by,
        point_class=final_point_class,
        unit=final_unit,
        states=proposal["states"],
        functional_location_id=batch["equipment_id"],
        mapping_confidence=(
            float(proposal["confidence"]) if proposal["confidence"] is not None else None
        ),
    )

    connection.execute(
        text(
            "UPDATE bacnet_discovery_proposals SET status = 'accepted', "
            "created_point_id = :point_id, decided_by = :decided_by, decided_at = :decided_at "
            "WHERE id = :id"
        ),
        {
            "point_id": point_id,
            "decided_by": decided_by,
            "decided_at": datetime.now(UTC),
            "id": proposal_id,
        },
    )
    return get_proposal(connection, proposal_id)


def reject_proposal(
    connection: Connection, *, proposal_id: uuid.UUID, decided_by: str, reason: str
) -> dict[str, Any]:
    proposal = get_proposal(connection, proposal_id)
    if proposal is None:
        raise DiscoveryProposalNotFound("BACNET_DISCOVERY_PROPOSAL_NOT_FOUND")
    if proposal["status"] != "proposed":
        raise DiscoveryProposalConflict("BACNET_DISCOVERY_PROPOSAL_ALREADY_DECIDED")

    connection.execute(
        text(
            "UPDATE bacnet_discovery_proposals SET status = 'rejected', decided_by = :decided_by, "
            "decided_at = :decided_at, rejection_reason = :reason WHERE id = :id"
        ),
        {
            "decided_by": decided_by,
            "decided_at": datetime.now(UTC),
            "reason": reason,
            "id": proposal_id,
        },
    )
    return get_proposal(connection, proposal_id)
