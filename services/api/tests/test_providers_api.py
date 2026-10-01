"""Prestataires (ADR 012, section 2.2) : répertoire simple, et seul type de
nœud pouvant être l'objet du prédicat « maintainedBy », jusqu'ici sans
aucune cible possible."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_relations_for_tenant
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)


def _create_tenant(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    location_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site')"),
            {"id": site_id, "tenant_id": tenant_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'cta-01', 'CTA 01')"
            ),
            {"id": location_id, "tenant_id": tenant_id, "site_id": site_id},
        )
    return {"tenant_id": tenant_id, "site_id": site_id, "location_id": location_id}


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    purge_relations_for_tenant(tenant_id)
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("providers", "functional_locations", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientProvidersA")
    tenant_b = _create_tenant("ClientProvidersB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        _cleanup(tenant)


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant["tenant_id"]), roles=roles)
    return {"Authorization": f"Bearer {token}"}


def _call(method: str, path: str, headers: dict, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def _manager(tenant):
    return _headers(tenant, ["responsable_exploitation"])


def _tech(tenant):
    return _headers(tenant, ["technicien"])


def test_create_list_and_read_a_provider(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)

    created = _call(
        "POST",
        "/providers",
        manager,
        json={
            "name": "Frigo Services",
            "contact_name": "M. Traoré",
            "contact_email": "contact@frigo-services.example",
            "contact_phone": "+223 00 00 00 00",
        },
    )
    assert created.status_code == 201, created.text
    provider_id = created.json()["id"]

    listed = _call("GET", "/providers", _tech(tenant_a))
    read = _call("GET", f"/providers/{provider_id}", _tech(tenant_a))

    assert [p["name"] for p in listed.json()] == ["Frigo Services"]
    assert read.status_code == 200
    assert read.json()["contact_name"] == "M. Traoré"


def test_technician_can_read_but_not_create_or_update(two_tenants) -> None:
    tenant_a, _ = two_tenants
    tech = _tech(tenant_a)

    created = _call("POST", "/providers", tech, json={"name": "x"})
    listed = _call("GET", "/providers", tech)

    assert created.status_code == 403
    assert listed.status_code == 200


def test_updating_a_provider(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    provider_id = _call("POST", "/providers", manager, json={"name": "Frigo Services"}).json()["id"]

    updated = _call(
        "PUT",
        f"/providers/{provider_id}",
        manager,
        json={"name": "Frigo Services SARL", "contact_phone": "+223 11 11 11 11"},
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Frigo Services SARL"
    assert updated.json()["contact_phone"] == "+223 11 11 11 11"


def test_provider_not_found(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call("GET", f"/providers/{uuid.uuid4()}", _tech(tenant_a))
    assert response.status_code == 404
    assert response.json()["code"] == "PROVIDER_NOT_FOUND"


def test_providers_are_isolated_by_tenant(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    provider_id = _call(
        "POST", "/providers", _manager(tenant_a), json={"name": "Frigo Services"}
    ).json()["id"]

    seen_by_b = _call("GET", "/providers", _tech(tenant_b))
    read_by_b = _call("GET", f"/providers/{provider_id}", _tech(tenant_b))

    assert seen_by_b.json() == []
    assert read_by_b.status_code == 404


def test_a_functional_location_can_declare_who_maintains_it(two_tenants) -> None:
    """maintainedBy existait déjà dans le vocabulaire mais n'avait aucune
    cible possible (app/graph_vocabulary.py) avant l'ajout des prestataires."""
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    provider_id = _call("POST", "/providers", manager, json={"name": "Frigo Services"}).json()["id"]

    relation = _call(
        "POST",
        "/relations",
        manager,
        json={
            "subject_id": str(tenant_a["location_id"]),
            "predicate": "maintainedBy",
            "object_id": provider_id,
        },
    )
    read = _call("GET", f"/graph/nodes/{tenant_a['location_id']}/relations", manager)

    assert relation.status_code == 201, relation.text
    maintenance = [r for r in read.json() if r["predicate"] == "maintainedBy"]
    assert [r["object_id"] for r in maintenance] == [provider_id]
    assert maintenance[0]["object_type"] == "provider"
