import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.engine import Connection

import app.connectors.device_mapping  # noqa: F401  (config « modbus_device_mapping »)
import app.energy.baseline  # noqa: F401  (enregistre le type de configuration « energy_baseline »)
import app.rules  # noqa: F401  (enregistre le type de configuration « alarm_rule »)
from app.audit import append_audit_entry
from app.auth import require_any_role
from app.config_versions import (
    ConfigConflict,
    ConfigInvalid,
    ConfigNotFound,
    activate_version,
    create_version,
    diff_versions,
    get_version,
    list_versions,
    restore_version,
    retire_version,
)
from app.deps import get_tenant_connection, get_tenant_id
from app.errors import ApiError, api_error
from app.schemas import ConfigDiffOut, ConfigReason, ConfigVersionCreate, ConfigVersionOut

router = APIRouter()

_MANAGE_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


def _http_error(exc: Exception) -> ApiError:
    if isinstance(exc, ConfigNotFound):
        return api_error(exc, 404)
    if isinstance(exc, ConfigConflict):
        return api_error(exc, 409)
    return api_error(exc, 400)


_ERRORS = (ConfigNotFound, ConfigConflict, ConfigInvalid)


def _audit(connection, tenant_id, claims, action, version_id, payload) -> None:
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action=action,
        entity_type="config_version",
        entity_id=str(version_id),
        payload=payload,
    )


@router.post("/configs", response_model=ConfigVersionOut, status_code=status.HTTP_201_CREATED)
def create_config_version(
    body: ConfigVersionCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> ConfigVersionOut:
    """Nouvelle version en brouillon (rien ne change tant qu'elle n'est pas activée)."""
    try:
        version_id = create_version(
            connection,
            tenant_id=tenant_id,
            config_type=body.config_type,
            subject_key=body.subject_key,
            content=body.content,
            author=_actor(claims),
            reason=body.reason,
        )
    except _ERRORS as exc:
        raise _http_error(exc) from exc
    version = get_version(connection, version_id)
    _audit(
        connection,
        tenant_id,
        claims,
        "config.version_created",
        version_id,
        {
            "config_type": body.config_type,
            "subject_key": body.subject_key,
            "version": version["version"],
            "reason": body.reason,
        },
    )
    return ConfigVersionOut(**version)


@router.get("/configs", response_model=list[ConfigVersionOut])
def list_config_versions(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    config_type: str | None = None,
    subject_key: str | None = None,
) -> list[ConfigVersionOut]:
    versions = list_versions(connection, config_type=config_type, subject_key=subject_key)
    return [ConfigVersionOut(**version) for version in versions]


@router.get("/configs/{version_id}", response_model=ConfigVersionOut)
def read_config_version(
    version_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> ConfigVersionOut:
    version = get_version(connection, version_id)
    if version is None:
        raise ApiError(404, "CONFIG_VERSION_NOT_FOUND")
    return ConfigVersionOut(**version)


@router.get("/configs/{version_id}/diff", response_model=ConfigDiffOut)
def diff_config_versions(
    version_id: uuid.UUID,
    against: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> ConfigDiffOut:
    """Ce qui change de la version `against` à la version `version_id`."""
    new, old = get_version(connection, version_id), get_version(connection, against)
    if new is None or old is None:
        raise ApiError(404, "CONFIG_VERSION_NOT_FOUND")
    if (new["config_type"], new["subject_key"]) != (old["config_type"], old["subject_key"]):
        raise ApiError(400, "CONFIG_DIFF_SUBJECT_MISMATCH")
    return ConfigDiffOut(
        from_version=old["version"],
        to_version=new["version"],
        **diff_versions(old["content"], new["content"]),
    )


@router.post("/configs/{version_id}/activate", response_model=ConfigVersionOut)
def activate_config_version(
    version_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> ConfigVersionOut:
    try:
        previous = activate_version(
            connection,
            version_id=version_id,
            activated_by=_actor(claims),
            activated_at=datetime.now(UTC),
        )
    except _ERRORS as exc:
        raise _http_error(exc) from exc
    _audit(
        connection,
        tenant_id,
        claims,
        "config.version_activated",
        version_id,
        {"superseded_version_id": str(previous) if previous else None},
    )
    return ConfigVersionOut(**get_version(connection, version_id))


@router.post("/configs/{version_id}/retire", response_model=ConfigVersionOut)
def retire_config_version(
    version_id: uuid.UUID,
    body: ConfigReason,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> ConfigVersionOut:
    try:
        retire_version(connection, version_id=version_id)
    except _ERRORS as exc:
        raise _http_error(exc) from exc
    _audit(
        connection, tenant_id, claims, "config.version_retired", version_id, {"reason": body.reason}
    )
    return ConfigVersionOut(**get_version(connection, version_id))


@router.post(
    "/configs/{version_id}/restore",
    response_model=ConfigVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def restore_config_version(
    version_id: uuid.UUID,
    body: ConfigReason,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> ConfigVersionOut:
    """Retour arrière : une nouvelle version reprend et active l'ancien contenu."""
    try:
        new_id = restore_version(
            connection,
            tenant_id=tenant_id,
            version_id=version_id,
            author=_actor(claims),
            reason=body.reason,
            activated_at=datetime.now(UTC),
        )
    except _ERRORS as exc:
        raise _http_error(exc) from exc
    _audit(
        connection,
        tenant_id,
        claims,
        "config.version_restored",
        new_id,
        {"restored_from": str(version_id), "reason": body.reason},
    )
    return ConfigVersionOut(**get_version(connection, new_id))
