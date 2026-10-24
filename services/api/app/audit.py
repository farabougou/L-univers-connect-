import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

GENESIS_HASH = "0" * 64


def _canonical_entry(
    tenant_id: uuid.UUID,
    actor: str,
    action: str,
    entity_type: str | None,
    entity_id: str | None,
    payload: dict[str, Any],
    previous_hash: str,
) -> str:
    data = {
        "tenant_id": str(tenant_id),
        "actor": actor,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload,
        "previous_hash": previous_hash,
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _hash_entry(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_audit_entry(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    actor: str,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Ajoute une entrée au journal d'audit du tenant, chaînée à la précédente.

    Un verrou consultatif par tenant évite qu'une écriture concurrente ne
    calcule la même empreinte "précédente" et ne casse la chaîne.
    """
    payload = payload or {}

    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(tenant_id)}
    )

    previous_hash = connection.execute(
        text(
            "SELECT entry_hash FROM audit_log WHERE tenant_id = :tenant_id "
            "ORDER BY seq DESC LIMIT 1"
        ),
        {"tenant_id": tenant_id},
    ).scalar()
    previous_hash = previous_hash or GENESIS_HASH

    canonical = _canonical_entry(
        tenant_id, actor, action, entity_type, entity_id, payload, previous_hash
    )
    entry_hash = _hash_entry(canonical)
    entry_id = uuid.uuid4()

    connection.execute(
        text(
            """
            INSERT INTO audit_log
                (id, tenant_id, actor, action, entity_type, entity_id,
                 payload, previous_hash, entry_hash)
            VALUES
                (:id, :tenant_id, :actor, :action, :entity_type, :entity_id,
                 CAST(:payload AS JSONB), :previous_hash, :entry_hash)
            """
        ),
        {
            "id": entry_id,
            "tenant_id": tenant_id,
            "actor": actor,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": json.dumps(payload, sort_keys=True, separators=(",", ":")),
            "previous_hash": previous_hash,
            "entry_hash": entry_hash,
        },
    )
    return entry_id


@dataclass
class ChainVerificationResult:
    valid: bool
    broken_at_seq: int | None = None
    reason: str | None = None


def verify_chain_integrity(
    connection: Connection, *, tenant_id: uuid.UUID
) -> ChainVerificationResult:
    """Rejoue la chaîne de hachage d'un tenant et vérifie qu'elle est intacte."""
    rows = (
        connection.execute(
            text(
                "SELECT seq, actor, action, entity_type, entity_id, payload, "
                "previous_hash, entry_hash FROM audit_log "
                "WHERE tenant_id = :tenant_id ORDER BY seq ASC"
            ),
            {"tenant_id": tenant_id},
        )
        .mappings()
        .all()
    )

    expected_previous = GENESIS_HASH
    for row in rows:
        if row["previous_hash"] != expected_previous:
            return ChainVerificationResult(
                valid=False,
                broken_at_seq=row["seq"],
                reason="previous_hash ne correspond pas à l'entrée précédente",
            )

        canonical = _canonical_entry(
            tenant_id,
            row["actor"],
            row["action"],
            row["entity_type"],
            row["entity_id"],
            row["payload"],
            row["previous_hash"],
        )
        recomputed = _hash_entry(canonical)
        if recomputed != row["entry_hash"]:
            return ChainVerificationResult(
                valid=False,
                broken_at_seq=row["seq"],
                reason="entry_hash ne correspond pas au contenu de l'entrée",
            )

        expected_previous = row["entry_hash"]

    return ChainVerificationResult(valid=True)
