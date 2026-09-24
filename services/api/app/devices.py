"""Identité technique d'un appareil Edge (M4, ADR 012 §2.10 — première brique).

Secret partagé haute entropie, haché (jamais stocké en clair) : suffisant
pour la V1, conçu pour évoluer vers un certificat (mTLS) sans réécriture —
`credential_type` distingue déjà le type de créance, même si
« shared_secret » est la seule valeur possible pour l'instant.

L'authentification d'un appareil est la seule opération qui a lieu avant de
connaître son tenant : l'appareil annonce son tenant_id, la connexion est
positionnée dessus (set_tenant_context) puis la recherche se fait sous RLS
comme toute autre requête — un tenant_id mensonger ne trouve simplement
aucune ligne. Jamais de contournement de l'isolation (règle non négociable 2).

Le statut de communication (online/offline/unknown) se calcule à la lecture
à partir de `last_seen_at`, jamais stocké (même principe que
app/equipment_status.py) : rien à réconcilier en double.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError

_COLUMNS = (
    "id, tenant_id, site_id, device_id, credential_type, status, created_by, created_at, "
    "last_seen_at, revoked_at, revoked_by, revoked_reason"
)

# Au-delà de ce délai sans relève, un appareil est considéré hors ligne
# plutôt qu'en ligne par supposition : pas de statut positif sans donnée
# récente, même esprit que la communication d'un équipement.
ONLINE_AFTER = timedelta(minutes=5)


class DeviceConflict(DomainError, ValueError):
    status = 409


class DeviceAuthInvalid(DomainError, ValueError):
    status = 401


def generate_secret() -> str:
    """256 bits aléatoires : jamais un mot de passe choisi, un secret émis."""
    return secrets.token_urlsafe(32)


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def provision_device(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    device_id: str,
    created_by: str,
    site_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, str]:
    """Crée un nouvel appareil. Renvoie (id, secret en clair) : le secret
    n'est jamais recalculable ensuite, à transmettre une seule fois."""
    existing = connection.execute(
        text("SELECT 1 FROM edge_devices WHERE tenant_id = :t AND device_id = :d"),
        {"t": tenant_id, "d": device_id},
    ).scalar()
    if existing:
        raise DeviceConflict("DEVICE_ID_ALREADY_USED", device_id=device_id)

    new_id = uuid.uuid4()
    secret = generate_secret()
    connection.execute(
        text(
            "INSERT INTO edge_devices (id, tenant_id, site_id, device_id, secret_hash, created_by) "
            "VALUES (:id, :tenant_id, :site_id, :device_id, :secret_hash, :created_by)"
        ),
        {
            "id": new_id,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "device_id": device_id,
            "secret_hash": _hash_secret(secret),
            "created_by": created_by,
        },
    )
    return new_id, secret


def authenticate_device(connection: Connection, *, device_id: str, secret: str) -> dict[str, Any]:
    """Vérifie l'appareil sous le tenant déjà positionné sur la connexion.

    Un tenant_id mensonger, un device_id inconnu ou un secret erroné donnent
    la même erreur générique : rien qui permette de deviner laquelle des
    trois raisons a joué."""
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS}, secret_hash FROM edge_devices WHERE device_id = :d"),
            {"d": device_id},
        )
        .mappings()
        .first()
    )
    if row is None or not hmac.compare_digest(row["secret_hash"], _hash_secret(secret)):
        raise DeviceAuthInvalid("DEVICE_AUTH_INVALID")
    if row["status"] != "active":
        raise DeviceAuthInvalid("DEVICE_AUTH_INVALID")
    return dict(row)


def touch_last_seen(connection: Connection, *, device_id: uuid.UUID, at: datetime) -> None:
    connection.execute(
        text("UPDATE edge_devices SET last_seen_at = :at WHERE id = :id"),
        {"at": at, "id": device_id},
    )


def revoke_device(
    connection: Connection, *, device_id: uuid.UUID, revoked_by: str, reason: str, at: datetime
) -> None:
    updated = connection.execute(
        text(
            "UPDATE edge_devices SET status = 'revoked', revoked_at = :at, revoked_by = :by, "
            "revoked_reason = :reason WHERE id = :id AND status = 'active'"
        ),
        {"at": at, "by": revoked_by, "reason": reason, "id": device_id},
    ).rowcount
    if not updated:
        raise DeviceConflict("DEVICE_ALREADY_REVOKED_OR_NOT_FOUND")


def get_device(connection: Connection, device_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM edge_devices WHERE id = :id"), {"id": device_id}
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_devices(connection: Connection) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(f"SELECT {_COLUMNS} FROM edge_devices ORDER BY created_at DESC")
        ).mappings()
    ]


def communication_status(device: dict[str, Any], *, now: datetime) -> str:
    """online si une relève a eu lieu récemment, offline si elle date trop,
    unknown si l'appareil n'a jamais donné signe de vie."""
    if device["last_seen_at"] is None:
        return "unknown"
    return "online" if now - device["last_seen_at"] <= ONLINE_AFTER else "offline"
