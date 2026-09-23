import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)


@pytest.fixture
def tenant_id():
    tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {
                "id": tenant_id,
                "name": "Client Télémétrie",
                "slug": f"client-telemetrie-{tenant_id}",
            },
        )

    yield tenant_id

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("DELETE FROM measurements WHERE tenant_id = :id"), {"id": tenant_id}
        )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _auth_headers(tenant_id: uuid.UUID, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant_id), roles=roles)
    return {"Authorization": f"Bearer {token}"}


def test_anonymous_cannot_ingest_a_measurement(tenant_id) -> None:
    response = client.post(
        "/measurements",
        json={"metric": "temperature_depart", "value": 45.5, "unit": "°C"},
    )
    assert response.status_code == 401


def test_user_without_field_role_cannot_ingest_a_measurement(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["some_other_role"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/measurements",
            json={"metric": "temperature_depart", "value": 45.5, "unit": "°C"},
            headers=headers,
        )

    assert response.status_code == 403


def test_squelette_de_bout_en_bout_point_simule_puis_lecture(tenant_id) -> None:
    """Scénario du squelette de bout en bout (M2, cahier des charges 36.2) :
    un point simulé est ingéré, puis relu — sans jamais écrire vers un
    équipement (règle non négociable 1, ici il n'y en a même pas)."""
    headers = _auth_headers(tenant_id, ["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        create_response = client.post(
            "/measurements",
            json={
                "metric": "temperature_depart",
                "value": 45.5,
                "unit": "°C",
                "source": "simulator",
            },
            headers=headers,
        )
        assert create_response.status_code == 201
        body = create_response.json()
        assert body["metric"] == "temperature_depart"
        assert body["value"] == 45.5
        assert body["unit"] == "°C"
        assert body["source"] == "simulator"

        list_response = client.get("/measurements", headers=headers)
        assert list_response.status_code == 200
        measurement_ids = {row["id"] for row in list_response.json()}
        assert body["id"] in measurement_ids


def test_measurement_target_must_exist_when_given(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/measurements",
            json={
                "metric": "temperature_depart",
                "value": 45.5,
                "unit": "°C",
                "functional_location_id": str(uuid.uuid4()),
            },
            headers=headers,
        )

    assert response.status_code == 404
