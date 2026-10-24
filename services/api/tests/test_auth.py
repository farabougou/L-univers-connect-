from unittest.mock import patch

import pytest
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
    # Nom lisible du client, jamais seulement son identifiant technique —
    # trouvé exposé en brut sur l'accueil mobile par l'audit du 02/10/2026.
    assert "tenant_name" in body


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


def test_me_gives_the_username_when_the_token_carries_one() -> None:
    """L'interface affiche ce nom lisible, jamais l'identifiant technique (`sub`) : même
    principe que le nom du client (`tenant_name`) plutôt que son identifiant."""
    token = make_token(roles=["technicien"], username="demo.technicien")

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["username"] == "demo.technicien"
    assert response.json()["sub"] == "technicien-test"  # inchangé : champ historique


def test_me_username_is_null_without_the_claim_and_never_invented() -> None:
    token = make_token(roles=["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.json()["username"] is None


@pytest.mark.parametrize("claim", [123, ["a"], {"x": 1}, True, ""])
def test_me_ignores_a_username_claim_that_is_not_a_non_empty_string(claim) -> None:
    token = make_token(roles=["technicien"], username=claim)

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.json()["username"] is None
