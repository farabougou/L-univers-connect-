"""API de la déclaration annuelle OPERAT (app.regulatory.operat exposé via
app/routers/regulatory.py) : workflow brouillon → prêt → transmis, réservé
aux rôles de gestion (tâche de bureau, pas un geste terrain)."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)


def _create_tenant(name: str) -> dict:
    ids = {k: uuid.uuid4() for k in ("tenant_id", "site")}
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": ids["tenant_id"], "name": name, "slug": f"{name.lower()}-{ids['tenant_id']}"},
        )
        set_tenant_context(connection, ids["tenant_id"])
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:site, :tenant_id, 'Site')"),
            ids,
        )
    return ids


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientOperatApiA")
    tenant_b = _create_tenant("ClientOperatApiB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        purge_tenant(tenant["tenant_id"])


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


def _ready_declaration(tenant) -> dict:
    created = _call(
        "POST",
        f"/sites/{tenant['site']}/operat-declarations",
        _manager(tenant),
        json={"reference_year": 2026},
    )
    assert created.status_code == 201, created.text
    declaration_id = created.json()["id"]
    updated = _call(
        "PUT",
        f"/operat-declarations/{declaration_id}",
        _manager(tenant),
        json={
            "floor_area_m2": 500.0,
            "activity_category": "bureaux",
            "electricity_kwh": 12000.0,
        },
    )
    assert updated.status_code == 200, updated.text
    ready = _call(
        "POST", f"/operat-declarations/{declaration_id}/mark-ready", _manager(tenant)
    )
    assert ready.status_code == 200, ready.text
    return ready.json()


def test_creates_a_draft_declaration(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call(
        "POST",
        f"/sites/{tenant_a['site']}/operat-declarations",
        _manager(tenant_a),
        json={"reference_year": 2026},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "draft"


def test_a_technician_cannot_create_a_declaration(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call(
        "POST",
        f"/sites/{tenant_a['site']}/operat-declarations",
        _tech(tenant_a),
        json={"reference_year": 2026},
    )
    assert response.status_code == 403


def test_a_second_declaration_for_the_same_year_is_refused(two_tenants) -> None:
    tenant_a, _ = two_tenants
    url = f"/sites/{tenant_a['site']}/operat-declarations"
    _call("POST", url, _manager(tenant_a), json={"reference_year": 2026})
    conflict = _call("POST", url, _manager(tenant_a), json={"reference_year": 2026})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "OPERAT_DECLARATION_ALREADY_EXISTS"


def test_full_workflow_from_draft_to_submission(two_tenants) -> None:
    tenant_a, _ = two_tenants
    ready = _ready_declaration(tenant_a)
    assert ready["status"] == "ready"

    summary = _call(
        "GET", f"/operat-declarations/{ready['id']}/summary", _manager(tenant_a)
    )
    assert summary.status_code == 200
    assert summary.json()["surface_m2"] == 500.0

    submitted = _call(
        "POST",
        f"/operat-declarations/{ready['id']}/submissions",
        _manager(tenant_a),
        json={"submission_reference": "OPERAT-2026-000123"},
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["status"] == "submitted"
    assert body["submission_reference"] == "OPERAT-2026-000123"

    with pytest.raises(DBAPIError, match="ne se modifie plus"):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            connection.execute(
                text("UPDATE operat_declarations SET notes = 'x' WHERE id = :id"),
                {"id": uuid.UUID(body["id"])},
            )


def test_mark_ready_before_complete_is_refused(two_tenants) -> None:
    tenant_a, _ = two_tenants
    created = _call(
        "POST",
        f"/sites/{tenant_a['site']}/operat-declarations",
        _manager(tenant_a),
        json={"reference_year": 2026},
    )
    response = _call(
        "POST",
        f"/operat-declarations/{created.json()['id']}/mark-ready",
        _manager(tenant_a),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "OPERAT_DECLARATION_INCOMPLETE"


def test_portfolio_lists_declarations_across_all_sites(two_tenants) -> None:
    tenant_a, _ = two_tenants
    _call(
        "POST",
        f"/sites/{tenant_a['site']}/operat-declarations",
        _manager(tenant_a),
        json={"reference_year": 2026},
    )
    portfolio = _call("GET", "/operat-declarations/portfolio", _manager(tenant_a))
    assert portfolio.status_code == 200
    assert [d["reference_year"] for d in portfolio.json()] == [2026]


def test_tenant_isolation_on_operat_declarations(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    created = _call(
        "POST",
        f"/sites/{tenant_a['site']}/operat-declarations",
        _manager(tenant_a),
        json={"reference_year": 2026},
    )
    declaration_id = created.json()["id"]

    cross = _call("GET", f"/operat-declarations/{declaration_id}", _manager(tenant_b))
    assert cross.status_code == 404
