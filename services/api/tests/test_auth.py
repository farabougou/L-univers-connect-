import time
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwk, jwt

from app.config import settings
from app.main import app

client = TestClient(app)

_KEY_ID = "test-key"
_DEMO_TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _generate_keypair() -> tuple[bytes, dict]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_jwk = jwk.construct(public_pem, algorithm="RS256").to_dict()
    public_jwk["kid"] = _KEY_ID
    return private_pem, {"keys": [public_jwk]}


_PRIVATE_KEY_PEM, _JWKS = _generate_keypair()


def _make_token(
    *,
    roles: list[str] | None = None,
    tenant_id: str | None = _DEMO_TENANT_ID,
    audience: str | None = None,
    expired: bool = False,
    private_key: bytes | None = None,
) -> str:
    now = int(time.time())
    claims = {
        "sub": "technicien-test",
        "iss": settings.oidc_issuer,
        "aud": audience or settings.oidc_audience,
        "iat": now,
        "exp": now - 10 if expired else now + 300,
        "realm_access": {"roles": roles or ["technicien"]},
        "tenant_id": tenant_id,
    }
    return jwt.encode(
        claims, private_key or _PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": _KEY_ID}
    )


def test_me_without_token_returns_401() -> None:
    response = client.get("/me")

    assert response.status_code == 401


def test_me_with_valid_token_returns_claims() -> None:
    token = _make_token(roles=["technicien"])

    with patch("app.auth.fetch_jwks", return_value=_JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == "technicien-test"
    assert body["roles"] == ["technicien"]
    assert body["tenant_id"] == _DEMO_TENANT_ID


def test_me_with_expired_token_returns_401() -> None:
    token = _make_token(expired=True)

    with patch("app.auth.fetch_jwks", return_value=_JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_me_with_wrong_audience_returns_401() -> None:
    token = _make_token(audience="autre-application")

    with patch("app.auth.fetch_jwks", return_value=_JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_me_with_token_signed_by_unknown_key_returns_401() -> None:
    other_private_key, _ = _generate_keypair()
    token = _make_token(private_key=other_private_key)

    with patch("app.auth.fetch_jwks", return_value=_JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_admin_route_rejects_technicien_role() -> None:
    token = _make_token(roles=["technicien"])

    with patch("app.auth.fetch_jwks", return_value=_JWKS):
        response = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_admin_route_accepts_admin_tenant_role() -> None:
    token = _make_token(roles=["admin_tenant"])

    with patch("app.auth.fetch_jwks", return_value=_JWKS):
        response = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
