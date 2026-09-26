from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from tests.jwt_helpers import DEMO_TENANT_ID, JWKS, generate_keypair, make_token

client = TestClient(app)


def test_me_without_token_returns_401() -> None:
    response = client.get("/me")

    assert response.status_code == 401


def test_me_with_valid_token_returns_claims() -> None:
    token = make_token(roles=["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == "technicien-test"
    assert body["roles"] == ["technicien"]
    assert body["tenant_id"] == DEMO_TENANT_ID


def test_me_with_expired_token_returns_401() -> None:
    token = make_token(expired=True)

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_me_with_wrong_audience_returns_401() -> None:
    token = make_token(audience="autre-application")

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_me_with_token_signed_by_unknown_key_returns_401() -> None:
    other_private_key, _ = generate_keypair()
    token = make_token(private_key=other_private_key)

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_admin_route_rejects_technicien_role() -> None:
    token = make_token(roles=["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_admin_route_accepts_admin_tenant_role() -> None:
    token = make_token(roles=["admin_tenant"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
