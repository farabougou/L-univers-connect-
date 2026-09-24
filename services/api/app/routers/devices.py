"""Identité d'appareil Edge : provisionnement, authentification, ingestion
de télémétrie authentifiée par appareil (M4, ADR 012 §2.10 — première
brique). Voir app/devices.py et app/auth.py pour le détail du modèle.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import DEVICE_TOKEN_TTL, issue_device_token, require_any_role, require_device_scope
from app.connectors.device_mapping import ModbusDeviceMappingContent, get_active_mapping
from app.db import engine
from app.deps import get_connection, get_tenant_connection, get_tenant_id
from app.devices import (
    DeviceAuthInvalid,
    DeviceConflict,
    DeviceNotFound,
    DevicePublicKeyInvalid,
    authenticate_device,
    authenticate_device_by_assertion,
    communication_status,
    get_device,
    list_devices,
    provision_device,
    revoke_device,
    set_public_key,
    touch_last_seen,
)
from app.errors import ApiError, api_error
from app.i18n import negotiate_locale, render
from app.schemas import EdgeMeasurementBatch, MeasurementBatchResult
from app.telemetry import ingest_measurements
from app.tenancy import set_tenant_context

router = APIRouter()

_MANAGE_ROLES = ("responsable_exploitation", "admin_tenant")
# Un seul jeu de portées pour l'instant : suffisant pour la V1, conçu pour
# devenir configurable par appareil (Mohamed, point 3 : évolution vers un
# modèle de portées plus fin).
_DEVICE_SCOPES = ["telemetry:write", "config:read", "command:execute"]


class DeviceCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=200)
    site_id: uuid.UUID | None = None
    # Modèle cible (Mohamed, 24/09/2026) : une clé publique EC P-256,
    # jamais la clé privée correspondante (qui reste sur l'appareil).
    # Omise : compatibilité shared_secret, à ne plus utiliser pour du
    # nouveau matériel (voir app/devices.py).
    public_key_pem: str | None = None


class DeviceCredentials(BaseModel):
    id: uuid.UUID
    device_id: str
    # Absent quand l'appareil est provisionné par clé publique : il n'y a
    # alors rien à transmettre, la clé privée n'ayant jamais existé côté
    # serveur.
    secret: str | None = None


class DeviceRevoke(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class DevicePublicKeyUpdate(BaseModel):
    public_key_pem: str
    reason: str = Field(min_length=1, max_length=500)


class DeviceAuthRequest(BaseModel):
    tenant_id: uuid.UUID
    device_id: str = Field(min_length=1, max_length=200)
    # Exactement l'un des deux (voir _exactly_one_credential) : `secret`
    # pour un appareil `shared_secret` (compatibilité), `assertion` pour un
    # appareil `public_key_assertion` (modèle cible) — un jeton court signé
    # par la clé privée de l'appareil, jamais la clé elle-même.
    secret: str | None = Field(default=None, min_length=1)
    assertion: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _exactly_one_credential(self) -> Self:
        if (self.secret is None) == (self.assertion is None):
            raise PydanticCustomError(
                "device_auth_needs_exactly_one_credential",
                "Provide exactly one of secret or assertion",
            )
        return self


class DeviceToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scopes: list[str]


class DeviceOut(BaseModel):
    id: uuid.UUID
    device_id: str
    site_id: uuid.UUID | None
    credential_type: str
    key_fingerprint: str | None
    status: str
    communication_status: str
    created_at: datetime
    last_seen_at: datetime | None


def _actor(claims: dict) -> str:
    return claims.get("sub") or "inconnu"


def _out(device: dict, *, now: datetime) -> DeviceOut:
    return DeviceOut(**device, communication_status=communication_status(device, now=now))


@router.post("/devices", response_model=DeviceCredentials, status_code=status.HTTP_201_CREATED)
def create_device(
    body: DeviceCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> DeviceCredentials:
    """Avec `public_key_pem` (modèle cible) : rien de secret à renvoyer, la
    clé privée n'a jamais transité par le serveur. Sans (compatibilité
    `shared_secret`) : le secret n'est renvoyé qu'ici, une seule fois, il
    n'est jamais recalculable ensuite (voir app/devices.py)."""
    try:
        device_id, secret = provision_device(
            connection,
            tenant_id=tenant_id,
            device_id=body.device_id,
            site_id=body.site_id,
            created_by=_actor(claims),
            public_key_pem=body.public_key_pem,
        )
    except DeviceConflict as exc:
        raise api_error(exc, exc.status) from exc
    except DevicePublicKeyInvalid as exc:
        raise api_error(exc, exc.status) from exc
    device = get_device(connection, device_id)
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="device.provisioned",
        entity_type="edge_device",
        entity_id=str(device_id),
        payload={
            "device_id": body.device_id,
            "site_id": str(body.site_id) if body.site_id else None,
            "credential_type": device["credential_type"],
            "key_fingerprint": device["key_fingerprint"],
        },
    )
    return DeviceCredentials(id=device_id, device_id=body.device_id, secret=secret)


@router.get("/devices", response_model=list[DeviceOut])
def list_devices_route(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> list[DeviceOut]:
    now = datetime.now(UTC)
    return [_out(device, now=now) for device in list_devices(connection)]


@router.post("/devices/{device_id}/revoke", response_model=DeviceOut)
def revoke_device_route(
    device_id: uuid.UUID,
    body: DeviceRevoke,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> DeviceOut:
    try:
        revoke_device(
            connection,
            device_id=device_id,
            revoked_by=_actor(claims),
            reason=body.reason,
            at=datetime.now(UTC),
        )
    except DeviceConflict as exc:
        raise api_error(exc, 409) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="device.revoked",
        entity_type="edge_device",
        entity_id=str(device_id),
        payload={"reason": body.reason},
    )
    return _out(get_device(connection, device_id), now=datetime.now(UTC))


@router.post("/devices/{device_id}/public-key", response_model=DeviceOut)
def set_device_public_key_route(
    device_id: uuid.UUID,
    body: DevicePublicKeyUpdate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> DeviceOut:
    """Installe une nouvelle clé publique : migration d'un appareil
    `shared_secret` vers le modèle cible, ou rotation d'un appareil déjà à
    clé publique — toujours une action humaine autorisée et auditée (voir
    app/devices.py, `set_public_key`), jamais initiée par l'appareil
    lui-même. Seule l'empreinte figure dans le journal d'audit, jamais la
    clé publique complète ni bien sûr la clé privée (qui ne transite
    jamais par ce serveur)."""
    try:
        fingerprints = set_public_key(
            connection,
            device_id=device_id,
            public_key_pem=body.public_key_pem,
            at=datetime.now(UTC),
        )
    except DeviceNotFound as exc:
        raise api_error(exc, exc.status) from exc
    except DevicePublicKeyInvalid as exc:
        raise api_error(exc, exc.status) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="device.public_key_set",
        entity_type="edge_device",
        entity_id=str(device_id),
        payload={"reason": body.reason, **fingerprints},
    )
    return _out(get_device(connection, device_id), now=datetime.now(UTC))


@router.post("/devices/auth", response_model=DeviceToken)
def authenticate_device_route(
    body: DeviceAuthRequest, connection: Annotated[Connection, Depends(get_connection)]
) -> DeviceToken:
    """Hors du flux OIDC humain : l'appareil annonce son tenant, la
    connexion est positionnée dessus puis la recherche se fait sous RLS
    comme toute autre requête (voir app/devices.py) — jamais de
    contournement de l'isolation, un tenant_id mensonger échoue simplement.

    `secret` (compatibilité) ou `assertion` (modèle cible, preuve signée
    par la clé privée de l'appareil) — exactement l'un des deux."""
    set_tenant_context(connection, body.tenant_id)
    try:
        if body.assertion is not None:
            device = authenticate_device_by_assertion(
                connection, device_id=body.device_id, assertion=body.assertion, at=datetime.now(UTC)
            )
        else:
            device = authenticate_device(connection, device_id=body.device_id, secret=body.secret)
    except DeviceAuthInvalid as exc:
        raise api_error(exc, exc.status) from exc
    touch_last_seen(connection, device_id=device["id"], at=datetime.now(UTC))

    token = issue_device_token(
        device_id=device["id"],
        tenant_id=body.tenant_id,
        site_id=device["site_id"],
        scopes=_DEVICE_SCOPES,
    )
    return DeviceToken(
        access_token=token,
        expires_in=int(DEVICE_TOKEN_TTL.total_seconds()),
        scopes=_DEVICE_SCOPES,
    )


@router.get("/edge/config", response_model=ModbusDeviceMappingContent)
def get_edge_config(
    equipment_id: uuid.UUID,
    claims: Annotated[dict, Depends(require_device_scope("config:read"))],
) -> ModbusDeviceMappingContent:
    """La configuration active pour cet équipement, sous le tenant de
    l'appareil authentifié — jamais un autre tenant, quel que soit
    l'equipment_id demandé (RLS)."""
    tenant_id = uuid.UUID(claims["tenant_id"])
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        content = get_active_mapping(connection, equipment_id=equipment_id)
    if content is None:
        raise ApiError(404, "MODBUS_MAPPING_NOT_FOUND")
    return ModbusDeviceMappingContent(**content)


@router.post("/edge/measurements", response_model=MeasurementBatchResult)
def create_edge_measurements(
    body: EdgeMeasurementBatch,
    request: Request,
    claims: Annotated[dict, Depends(require_device_scope("telemetry:write"))],
) -> MeasurementBatchResult:
    """Même chemin que /measurements/batch (app/routers/telemetry.py), pour
    un appareil authentifié plutôt qu'une personne. La source est
    l'identité vérifiée de l'appareil, jamais une valeur qu'il annoncerait."""
    tenant_id = uuid.UUID(claims["tenant_id"])
    device_id = uuid.UUID(claims["device_id"])
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        received_at = datetime.now(UTC)
        summary = ingest_measurements(
            connection,
            tenant_id=tenant_id,
            items=[item.model_dump() for item in body.items],
            source=f"edge:{claims['device_id']}",
            received_at=received_at,
        )
        touch_last_seen(connection, device_id=device_id, at=received_at)

    locale = negotiate_locale(request.headers.get("accept-language"))
    for error in summary["errors"]:
        error["reason"] = render(error["code"], error["params"], locale)
    return MeasurementBatchResult(**summary)
