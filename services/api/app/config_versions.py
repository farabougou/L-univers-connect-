"""Configuration versionnée (ADR 012, section 2.11).

Un seul mécanisme pour tout ce qui influence le fonctionnement : chaque
modification crée une nouvelle version (auteur, raison obligatoire, empreinte
du contenu), une seule version est active à la fois, et revenir en arrière
crée encore une nouvelle version avec l'ancien contenu. Rien n'est réécrit
ni supprimé (déclencheurs en base).

Chaque type de configuration déclare son validateur : une configuration
invalide n'est jamais enregistrée, même en brouillon.
"""

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError

VERSION_COLUMNS = (
    "id, config_type, subject_key, version, content, content_hash, schema_version, status, "
    "author, reason, parent_version_id, created_at, activated_at, activated_by"
)


class ConfigNotFound(DomainError, LookupError):
    status = 404


class ConfigConflict(DomainError, ValueError):
    status = 409


class ConfigInvalid(DomainError, ValueError):
    pass


# config_type → (version du schéma, validateur). Le validateur reçoit la
# connexion (pour vérifier ce que la configuration référence) et le contenu,
# et renvoie le contenu normalisé ou lève ConfigInvalid.
Validator = Callable[[Connection, dict[str, Any]], dict[str, Any]]
_REGISTRY: dict[str, tuple[str, Validator]] = {}


def register_config_type(config_type: str, schema_version: str, validator: Validator) -> None:
    _REGISTRY[config_type] = (schema_version, validator)


def _validate(connection: Connection, config_type: str, content: dict) -> tuple[str, dict]:
    if config_type not in _REGISTRY:
        raise ConfigInvalid("CONFIG_TYPE_UNKNOWN", config_type=config_type)
    schema_version, validator = _REGISTRY[config_type]
    return schema_version, validator(connection, content)


def content_hash(content: dict[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_version(connection: Connection, version_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {VERSION_COLUMNS} FROM config_versions WHERE id = :id"),
            {"id": version_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _require_version(connection: Connection, version_id: uuid.UUID) -> dict[str, Any]:
    version = get_version(connection, version_id)
    if version is None:
        raise ConfigNotFound("CONFIG_VERSION_NOT_FOUND")
    return version


def create_version(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    config_type: str,
    subject_key: str,
    content: dict[str, Any],
    author: str,
    reason: str,
) -> uuid.UUID:
    """Enregistre une nouvelle version (brouillon) après validation du contenu."""
    schema_version, normalized = _validate(connection, config_type, content)
    latest = (
        connection.execute(
            text(
                "SELECT id, version FROM config_versions WHERE config_type = :type "
                "AND subject_key = :key ORDER BY version DESC LIMIT 1"
            ),
            {"type": config_type, "key": subject_key},
        )
        .mappings()
        .first()
    )
    version_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO config_versions (id, tenant_id, config_type, subject_key, version, "
            "content, content_hash, schema_version, author, reason, parent_version_id) "
            "VALUES (:id, :tenant_id, :config_type, :subject_key, :version, "
            "CAST(:content AS JSONB), :content_hash, :schema_version, :author, :reason, :parent)"
        ),
        {
            "id": version_id,
            "tenant_id": tenant_id,
            "config_type": config_type,
            "subject_key": subject_key,
            "version": (latest["version"] + 1) if latest else 1,
            "content": json.dumps(normalized, sort_keys=True),
            "content_hash": content_hash(normalized),
            "schema_version": schema_version,
            "author": author,
            "reason": reason,
            "parent": latest["id"] if latest else None,
        },
    )
    return version_id


def activate_version(
    connection: Connection, *, version_id: uuid.UUID, activated_by: str, activated_at: datetime
) -> uuid.UUID | None:
    """Active une version brouillon ; l'ancienne version active passe
    « superseded ». Le contenu est revalidé : ce qu'il référence a pu changer
    depuis le brouillon. Renvoie l'identifiant de la version remplacée."""
    version = _require_version(connection, version_id)
    if version["status"] != "draft":
        raise ConfigConflict("CONFIG_ACTIVATION_REQUIRES_DRAFT", status=version["status"])
    _validate(connection, version["config_type"], version["content"])

    previous = connection.execute(
        text(
            "SELECT id FROM config_versions WHERE config_type = :type AND subject_key = :key "
            "AND status = 'active'"
        ),
        {"type": version["config_type"], "key": version["subject_key"]},
    ).scalar()
    if previous is not None:
        connection.execute(
            text("UPDATE config_versions SET status = 'superseded' WHERE id = :id"),
            {"id": previous},
        )
    connection.execute(
        text(
            "UPDATE config_versions SET status = 'active', activated_at = :at, "
            "activated_by = :by WHERE id = :id"
        ),
        {"at": activated_at, "by": activated_by, "id": version_id},
    )
    return previous


def retire_version(connection: Connection, *, version_id: uuid.UUID) -> None:
    """Retire une version (brouillon abandonné, ou règle arrêtée)."""
    version = _require_version(connection, version_id)
    if version["status"] not in ("draft", "active"):
        raise ConfigConflict("CONFIG_VERSION_ALREADY_IN_STATUS", status=version["status"])
    connection.execute(
        text("UPDATE config_versions SET status = 'retired' WHERE id = :id"), {"id": version_id}
    )


def restore_version(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    version_id: uuid.UUID,
    author: str,
    reason: str,
    activated_at: datetime,
) -> uuid.UUID:
    """Retour arrière : crée et active une NOUVELLE version reprenant le contenu
    d'une version antérieure. L'historique reste complet et lisible."""
    old = _require_version(connection, version_id)
    new_id = create_version(
        connection,
        tenant_id=tenant_id,
        config_type=old["config_type"],
        subject_key=old["subject_key"],
        content=old["content"],
        author=author,
        reason=reason,
    )
    activate_version(connection, version_id=new_id, activated_by=author, activated_at=activated_at)
    return new_id


def list_versions(
    connection: Connection, *, config_type: str | None = None, subject_key: str | None = None
) -> list[dict[str, Any]]:
    query = f"SELECT {VERSION_COLUMNS} FROM config_versions WHERE true"
    params: dict[str, Any] = {}
    if config_type is not None:
        query += " AND config_type = :config_type"
        params["config_type"] = config_type
    if subject_key is not None:
        query += " AND subject_key = :subject_key"
        params["subject_key"] = subject_key
    query += " ORDER BY config_type, subject_key, version"
    return [dict(row) for row in connection.execute(text(query), params).mappings()]


def diff_versions(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Différences clé par clé entre deux contenus."""
    return {
        "added": {key: new[key] for key in new.keys() - old.keys()},
        "removed": {key: old[key] for key in old.keys() - new.keys()},
        "changed": {
            key: {"from": old[key], "to": new[key]}
            for key in old.keys() & new.keys()
            if old[key] != new[key]
        },
    }


def active_versions(
    connection: Connection, *, config_type: str, content_filter: dict[str, str]
) -> list[dict[str, Any]]:
    """Versions actives d'un type dont le contenu contient ces valeurs
    (ex. toutes les règles actives qui portent sur un point donné)."""
    return [
        dict(row)
        for row in connection.execute(
            text(
                f"SELECT {VERSION_COLUMNS} FROM config_versions WHERE config_type = :type "
                "AND status = 'active' AND content @> CAST(:filter AS JSONB) "
                "ORDER BY subject_key"
            ),
            {"type": config_type, "filter": json.dumps(content_filter)},
        ).mappings()
    ]
