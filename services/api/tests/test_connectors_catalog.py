"""Catalogue des connecteurs (V4, ADR 012 §2.12 — app/connectors/catalog.py,
app/routers/connectors.py). Jamais une donnée statique seule : le nombre
d'équipements avec une connexion active de chaque protocole doit refléter
ce qui est réellement configuré dans le tenant, isolé des autres."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config_versions import activate_version, create_version
from app.connectors.device_mapping import MODBUS_DEVICE_MAPPING
from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.analytics_fixtures import cleanup_tenant, create_tenant_with_points
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)


@pytest.fixture
def two_tenants():
    tenant_a = create_tenant_with_points("ClientConnectorsCatalogA")
    tenant_b = create_tenant_with_points("ClientConnectorsCatalogB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        cleanup_tenant(tenant)


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(tenant_id=str(tenant['tenant_id']), roles=roles)}"
    }


def _call(method, path, headers, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def _manager(tenant):
    return _headers(tenant, ["responsable_exploitation"])


def _tech(tenant):
    return _headers(tenant, ["technicien"])


def _activate_modbus_mapping(connection, tenant):
    content = {
        "device_type": "sdm120",
        "host": "127.0.0.1",
        "port": 502,
        "points": [{"point_id": str(tenant["sensor"]), "register_name": "voltage"}],
    }
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=MODBUS_DEVICE_MAPPING,
        subject_key=str(tenant["ahu"]),
        content=content,
        author="responsable",
        reason="test",
    )
    activate_version(
        connection,
        version_id=version_id,
        activated_by="responsable",
        activated_at=datetime.now(UTC),
    )
    return version_id


def test_catalog_lists_the_four_connectors_never_write_enabled(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call("GET", "/connectors", _manager(tenant_a))
    assert response.status_code == 200, response.text
    body = response.json()

    protocols = {entry["protocol"] for entry in body}
    assert protocols == {"modbus", "bacnet", "opcua", "mqtt"}
    for entry in body:
        assert entry["write_enabled"] is False
        assert entry["certification_level"] in ("experimental", "verified", "certified")
        assert entry["active_equipment_count"] == 0


def test_catalog_reflects_an_active_mapping_in_this_tenant_only(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        _activate_modbus_mapping(connection, tenant_a)

    response_a = _call("GET", "/connectors", _manager(tenant_a))
    response_b = _call("GET", "/connectors", _manager(tenant_b))

    modbus_a = next(entry for entry in response_a.json() if entry["protocol"] == "modbus")
    modbus_b = next(entry for entry in response_b.json() if entry["protocol"] == "modbus")
    assert modbus_a["active_equipment_count"] == 1
    assert modbus_b["active_equipment_count"] == 0


def test_catalog_requires_a_management_role(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call("GET", "/connectors", _tech(tenant_a))
    assert response.status_code == 403
