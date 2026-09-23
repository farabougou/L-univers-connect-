"""Étiquettes QR / NFC collées sur les équipements (ADR 012, étape F5).

Le QR ne contient qu'un code aléatoire opaque (`paios:tag:<code>`), jamais un
identifiant interne ni une donnée : une étiquette est physiquement visible par
tous, son contenu ne doit rien révéler. Scanner ne donne accès à rien sans
être connecté ; ce qui s'affiche dépend ensuite des droits de la personne.

Une étiquette abîmée ou arrachée est révoquée (jamais réattribuée) et une
nouvelle est créée ; un code révoqué scanné est signalé comme tel.
"""

import secrets
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

QR_PREFIX = "paios:tag:"
TAG_TYPES = ("qr", "nfc", "barcode")

_COLUMNS = (
    "id, node_id, code, tag_type, status, created_by, created_at, revoked_at, revoked_by, "
    "revoke_reason"
)


class TagNotFound(LookupError):
    pass


class TagRevoked(ValueError):
    pass


def new_code() -> str:
    """128 bits aléatoires, lisibles dans une URL et un QR compact."""
    return secrets.token_urlsafe(16)


def with_payload(tag: dict[str, Any]) -> dict[str, Any]:
    return {**tag, "payload": f"{QR_PREFIX}{tag['code']}"}


def create_tag(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    node_id: uuid.UUID,
    tag_type: str,
    created_by: str,
) -> dict[str, Any]:
    if tag_type not in TAG_TYPES:
        raise ValueError(f"type d'étiquette inconnu : {tag_type}")
    node_exists = connection.execute(
        text("SELECT 1 FROM graph_nodes WHERE id = :id"), {"id": node_id}
    ).scalar()
    if not node_exists:
        raise TagNotFound("nœud introuvable")
    tag_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO asset_tags (id, tenant_id, node_id, code, tag_type, created_by) "
            "VALUES (:id, :tenant_id, :node_id, :code, :tag_type, :created_by)"
        ),
        {
            "id": tag_id,
            "tenant_id": tenant_id,
            "node_id": node_id,
            "code": new_code(),
            "tag_type": tag_type,
            "created_by": created_by,
        },
    )
    return get_tag_by_id(connection, tag_id)


def get_tag_by_id(connection: Connection, tag_id: uuid.UUID) -> dict[str, Any]:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM asset_tags WHERE id = :id"), {"id": tag_id}
        )
        .mappings()
        .one()
    )
    return with_payload(dict(row))


def find_tag(connection: Connection, code: str) -> dict[str, Any]:
    """Lecture sous RLS : un code d'un autre tenant est « introuvable »."""
    if code.startswith(QR_PREFIX):
        code = code[len(QR_PREFIX) :]
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM asset_tags WHERE code = :code"), {"code": code}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise TagNotFound("étiquette inconnue")
    return with_payload(dict(row))


def resolve_tag(connection: Connection, code: str) -> dict[str, Any]:
    tag = find_tag(connection, code)
    if tag["status"] == "revoked":
        raise TagRevoked(
            f"étiquette révoquée ({tag['revoke_reason']}) : scanner la nouvelle étiquette"
        )
    return tag


def revoke_tag(
    connection: Connection, *, code: str, revoked_by: str, reason: str, revoked_at: datetime
) -> dict[str, Any]:
    tag = find_tag(connection, code)
    if tag["status"] == "revoked":
        raise TagRevoked("cette étiquette est déjà révoquée")
    connection.execute(
        text(
            "UPDATE asset_tags SET status = 'revoked', revoked_at = :at, revoked_by = :by, "
            "revoke_reason = :reason WHERE id = :id"
        ),
        {"at": revoked_at, "by": revoked_by, "reason": reason, "id": tag["id"]},
    )
    return get_tag_by_id(connection, tag["id"])


def list_tags(connection: Connection, node_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        with_payload(dict(row))
        for row in connection.execute(
            text(f"SELECT {_COLUMNS} FROM asset_tags WHERE node_id = :id ORDER BY created_at"),
            {"id": node_id},
        ).mappings()
    ]
