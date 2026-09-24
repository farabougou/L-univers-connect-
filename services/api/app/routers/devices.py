"""Identité d'appareil Edge : provisionnement, authentification, ingestion
de télémétrie authentifiée par appareil (M4, ADR 012 §2.10 — première
brique). Voir app/devices.py et app/auth.py pour le détail du modèle.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import DEVICE_TOKEN_TTL, issue_device_token, require_any_role, require_device_scope
from app.db import engine
from app.deps import get_connection, get_tenant_connection, get_tenant_id
from app.devices import (
    DeviceAuthInvalid,
    DeviceConflict,
    authenticate_device,
    communication_status,
    get_device,
    list_devices,
    provision_device,
    revoke_device,
    touch_last_seen,
)
from app.errors import api_error
from app.i18n import negotiate_locale, render
from app.schemas import EdgeMeasurementBatch, MeasurementBatchResult
from app.telemetry import ingest_measurements
from app.tenancy import set_tenant_context

router = APIRouter()

_MANAGE_ROLES = ("responsable_exploitation", "admin_tenant")
_DEVICE_SCOPES = ["telemetry:write"]


class DeviceCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=200)
    site_id: uuid.UUID | None = None


class DeviceCredentials(BaseModel):
    id: uuid.UUID
    device_id: str
    secret: str


class DeviceRevoke(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class DeviceAuthRequest(BaseModel):
    tenant_id: uuid.UUID
    device_id: str = Field(min_length=1, max_length=200)
    secret: str = Field(min_length=1)


class DeviceToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scopes: list[str]


class DeviceOut(BaseModel):
    id: uuid.UUID
    device_id: str
    site_id: uuid.UUID | None
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
    """Le secret n'est renvoyé qu'ici, une seule fois : il n'est jamais
    recalculable ensuite (voir app/devices.py, hachage à sens unique)."""
    try:
        device_id, secret = provision_device(
            connection,
            tenant_id=tenant_id,
            device_id=body.device_id,
            site_id=body.site_id,
            created_by=_actor(claims),
        )
    except DeviceConflict as exc:
        raise api_error(exc, 409) from exc
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


@router.post("/devices/auth", response_model=DeviceToken)
def authenticate_device_route(
    body: DeviceAuthRequest, connection: Annotated[Connection, Depends(get_connection)]
) -> DeviceToken:
    """Hors du flux OIDC humain : l'appareil annonce son tenant, la
    connexion est positionnée dessus puis la recherche se fait sous RLS
    comme toute autre requête (voir app/devices.py) — jamais de
    contournement de l'isolation, un tenant_id mensonger échoue simplement."""
    set_tenant_context(connection, body.tenant_id)
    try:
        device = authenticate_device(connection, device_id=body.device_id, secret=body.secret)
    except DeviceAuthInvalid as exc:
        raise api_error(exc, 401) from exc
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
