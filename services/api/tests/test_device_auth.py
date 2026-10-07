"""Jetons d'appareil Edge (app/auth.py) : signature séparée du flux OIDC
humain, expiration, portées (scopes)."""

import time
import uuid
from unittest.mock import patch

import pytest
from jose import jwt

from app.auth import (
    DEVICE_TOKEN_TTL,
    decode_device_token,
    get_current_device_claims,
    issue_device_token,
    require_device_scope,
)
from app.errors import ApiError


def test_jeton_emis_puis_decode_porte_les_bonnes_revendications():
    device_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()

    token = issue_device_token(
        device_id=device_id, tenant_id=tenant_id, site_id=site_id, scopes=["telemetry:write"]
    )
    claims = decode_device_token(token)

    assert claims["device_id"] == str(device_id)
    assert claims["tenant_id"] == str(tenant_id)
    assert claims["site_id"] == str(site_id)
    assert claims["scopes"] == ["telemetry:write"]


def test_jeton_sans_site_porte_site_id_nul():
    token = issue_device_token(
        device_id=uuid.uuid4(), tenant_id=uuid.uuid4(), site_id=None, scopes=["telemetry:write"]
    )
    assert decode_device_token(token)["site_id"] is None


def test_jeton_signe_avec_un_autre_secret_est_refuse():
    token = jwt.encode({"device_id": "x"}, "un-autre-secret", algorithm="HS256")
    with pytest.raises(ApiError) as info:
        decode_device_token(token)
    assert info.value.status == 401
    assert info.value.code == "DEVICE_TOKEN_INVALID"


def test_jeton_expire_est_refuse():
    with patch("app.auth.DEVICE_TOKEN_TTL", -DEVICE_TOKEN_TTL):
        token = issue_device_token(
            device_id=uuid.uuid4(), tenant_id=uuid.uuid4(), site_id=None, scopes=["telemetry:write"]
        )
    time.sleep(0.01)
    with pytest.raises(ApiError) as info:
        decode_device_token(token)
    assert info.value.code == "DEVICE_TOKEN_INVALID"


def test_require_device_scope_accepte_la_bonne_portee():
    dependency = require_device_scope("telemetry:write")
    claims = {"scopes": ["telemetry:write"]}
    assert dependency(claims) == claims


def test_require_device_scope_refuse_une_autre_portee():
    dependency = require_device_scope("telemetry:write")
    with pytest.raises(ApiError) as info:
        dependency({"scopes": ["autre:chose"]})
    assert info.value.status == 403
    assert info.value.code == "DEVICE_SCOPE_FORBIDDEN"


def test_get_current_device_claims_sans_jeton_est_refuse():
    with pytest.raises(ApiError) as info:
        get_current_device_claims(None)
    assert info.value.status == 401
    assert info.value.code == "TOKEN_MISSING"
