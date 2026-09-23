import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)


@pytest.fixture
def tenant_id():
    tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": "Client API", "slug": f"client-api-{tenant_id}"},
        )

    yield tenant_id

    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "functional_location_assignments",
            "physical_unit_lifecycle_events",
            "physical_units",
            "functional_locations",
            "product_models",
            "sites",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _auth_headers(tenant_id: uuid.UUID, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant_id), roles=roles)
    return {"Authorization": f"Bearer {token}"}


def test_create_site_rejects_technicien_role(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/sites", json={"name": "Site A", "timezone": "Europe/Paris"}, headers=headers
        )

    assert response.status_code == 403


def test_full_asset_registry_flow_as_admin(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_response = client.post(
            "/sites",
            json={"name": "Site principal", "timezone": "Europe/Paris"},
            headers=headers,
        )
        assert site_response.status_code == 201
        site_id = site_response.json()["id"]

        model_response = client.post(
            "/product-models",
            json={"manufacturer": "Fabricant Demo", "reference": "PAC-100", "category": "pac"},
            headers=headers,
        )
        assert model_response.status_code == 201
        product_model_id = model_response.json()["id"]

        unit_1_response = client.post(
            "/physical-units",
            json={"product_model_id": product_model_id, "serial_number": "SN-001"},
            headers=headers,
        )
        assert unit_1_response.status_code == 201
        unit_1_id = unit_1_response.json()["id"]

        unit_2_response = client.post(
            "/physical-units",
            json={"product_model_id": product_model_id, "serial_number": "SN-002"},
            headers=headers,
        )
        assert unit_2_response.status_code == 201
        unit_2_id = unit_2_response.json()["id"]

        location_response = client.post(
            "/functional-locations",
            json={"site_id": site_id, "code": "sous-station-1", "name": "Sous-station 1"},
            headers=headers,
        )
        assert location_response.status_code == 201
        location_id = location_response.json()["id"]

        assign_1_response = client.post(
            f"/functional-locations/{location_id}/assignment",
            json={"physical_unit_id": unit_1_id},
            headers=headers,
        )
        assert assign_1_response.status_code == 201

        occupant_response = client.get(
            f"/functional-locations/{location_id}/current-occupant", headers=headers
        )
        assert occupant_response.status_code == 200
        assert occupant_response.json()["physical_unit_id"] == unit_1_id

        # Remplacement de l'exemplaire : l'occupant courant doit changer,
        # sans casser les affectations passées (voir test_asset_registry.py
        # pour la preuve de non-régression de l'historique côté base).
        assign_2_response = client.post(
            f"/functional-locations/{location_id}/assignment",
            json={"physical_unit_id": unit_2_id},
            headers=headers,
        )
        assert assign_2_response.status_code == 201

        occupant_after_replacement = client.get(
            f"/functional-locations/{location_id}/current-occupant", headers=headers
        )
        assert occupant_after_replacement.json()["physical_unit_id"] == unit_2_id

        sites = client.get("/sites", headers=headers)
        assert [s["id"] for s in sites.json()] == [site_id]


def test_assignment_on_unknown_functional_location_returns_404(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    random_location_id = uuid.uuid4()
    random_unit_id = uuid.uuid4()

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            f"/functional-locations/{random_location_id}/assignment",
            json={"physical_unit_id": str(random_unit_id)},
            headers=headers,
        )

    assert response.status_code == 404


def test_list_sites_only_shows_own_tenant(tenant_id) -> None:
    other_tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": other_tenant_id, "name": "Autre client", "slug": f"autre-{other_tenant_id}"},
        )
        set_tenant_context(connection, other_tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
            {"id": uuid.uuid4(), "tenant_id": other_tenant_id, "name": "Site de l'autre client"},
        )

    headers = _auth_headers(tenant_id, ["admin_tenant"])
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            client.post(
                "/sites", json={"name": "Mon site", "timezone": "Europe/Paris"}, headers=headers
            )
            response = client.get("/sites", headers=headers)

        assert response.status_code == 200
        assert [site["name"] for site in response.json()] == ["Mon site"]
    finally:
        with engine.begin() as connection:
            set_tenant_context(connection, other_tenant_id)
            connection.execute(
                text("DELETE FROM sites WHERE tenant_id = :id"), {"id": other_tenant_id}
            )
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": other_tenant_id})


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"name": "Site sans fuseau"}, "VALIDATION_ERROR"),
        ({"name": "Site", "timezone": "Mars/Olympus"}, "TIMEZONE_UNKNOWN"),
        ({"name": "Site", "timezone": "UTC+2"}, "TIMEZONE_UNKNOWN"),
    ],
)
def test_a_site_requires_a_valid_iana_time_zone(tenant_id, body, code) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post("/sites", json=body, headers=headers)
    assert (response.status_code, response.json()["code"]) == (422, code)


def test_time_zone_of_an_existing_site_can_be_set_and_is_audited(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = client.post(
            "/sites", json={"name": "Site Lyon", "timezone": "Europe/Paris"}, headers=headers
        ).json()["id"]
        updated = client.put(
            f"/sites/{site_id}/timezone", json={"timezone": "Europe/Madrid"}, headers=headers
        )
        unknown = client.put(
            f"/sites/{uuid.uuid4()}/timezone", json={"timezone": "Europe/Paris"}, headers=headers
        )
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        payload = connection.execute(
            text("SELECT payload FROM audit_log WHERE action = 'site.timezone_set'")
        ).scalar()

    assert updated.json()["timezone"] == "Europe/Madrid"
    assert unknown.status_code == 404
    assert payload == {"previous": "Europe/Paris", "timezone": "Europe/Madrid"}
