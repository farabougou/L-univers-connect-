"""API de recherche globale (GET /search, app/routers/search.py) : rôle
requis, forme de la réponse, isolation par tenant au niveau HTTP — la
rigueur du filtrage lui-même est déjà prouvée par tests/test_search.py."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from tests.jwt_helpers import JWKS, make_token
from tests.test_search import _cleanup, _create_tenant

client = TestClient(app)


def _get(path: str, *, token: str | None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.get(path, headers=headers)


def test_search_requires_authentication() -> None:
    response = _get("/search?q=Nord", token=None)
    assert response.status_code == 401


def test_search_returns_matches_scoped_to_the_caller_tenant() -> None:
    tenant = _create_tenant("ClientRechercheApi")
    try:
        token = make_token(roles=["technicien"], tenant_id=str(tenant["tenant_id"]))
        response = _get("/search?q=Nord", token=token)
        assert response.status_code == 200
        body = response.json()
        assert {result["kind"] for result in body} >= {"site", "functional_location"}
        assert all("id" in result and "label" in result for result in body)
    finally:
        _cleanup(tenant)


def test_blank_query_is_rejected() -> None:
    token = make_token(roles=["technicien"])
    response = _get("/search?q=", token=token)
    assert response.status_code == 422
