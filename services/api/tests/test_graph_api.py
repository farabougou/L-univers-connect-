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
    ahu_id = uuid.uuid4()
    panel_id = uuid.uuid4()
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
        for location_id, code in ((ahu_id, "cta-01"), (panel_id, "tableau-elec")):
            connection.execute(
                text(
                    "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                    "VALUES (:id, :tenant_id, :site_id, :code, :code)"
                ),
                {"id": location_id, "tenant_id": tenant_id, "site_id": site_id, "code": code},
            )
    return {"tenant_id": tenant_id, "site": site_id, "ahu": ahu_id, "panel": panel_id}


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    purge_relations_for_tenant(tenant_id)
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("functional_locations", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientGraphApiA")
    tenant_b = _create_tenant("ClientGraphApiB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        _cleanup(tenant)


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant["tenant_id"]), roles=roles)
    return {"Authorization": f"Bearer {token}"}


def _relation_body(tenant: dict, **overrides) -> dict:
    body = {
        "subject_id": str(tenant["ahu"]),
        "predicate": "poweredBy",
        "object_id": str(tenant["panel"]),
    }
    body.update(overrides)
    return body


def test_technicien_can_read_but_not_create_relations(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        create = client.post("/relations", json=_relation_body(tenant_a), headers=headers)
        read = client.get(f"/graph/nodes/{tenant_a['ahu']}/relations", headers=headers)

    assert create.status_code == 403
    assert read.status_code == 200


def test_create_relation_then_read_it_from_both_ends(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["responsable_exploitation"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        created = client.post("/relations", json=_relation_body(tenant_a), headers=headers)
        from_panel = client.get(f"/graph/nodes/{tenant_a['panel']}/relations", headers=headers)

    assert created.status_code == 201
    body = created.json()
    assert body["label"] == "poweredBy"
    assert body["direction"] == "outgoing"
    assert body["origin"] == "manual"
    assert body["status"] == "validated"
    assert body["vocabulary_version"]

    stored = [edge for edge in from_panel.json() if not edge["derived"]]
    assert [(edge["id"], edge["label"]) for edge in stored] == [(body["id"], "powers")]


def test_relation_creation_is_audited(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["admin_tenant"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        created = client.post("/relations", json=_relation_body(tenant_a), headers=headers)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        actions = (
            connection.execute(
                text("SELECT action FROM audit_log WHERE entity_id = :id"),
                {"id": created.json()["id"]},
            )
            .scalars()
            .all()
        )
    assert actions == ["relation.created"]


def test_node_of_another_tenant_is_not_found(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    headers = _headers(tenant_a, ["admin_tenant"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        create = client.post(
            "/relations",
            json=_relation_body(tenant_a, object_id=str(tenant_b["panel"])),
            headers=headers,
        )
        read = client.get(f"/graph/nodes/{tenant_b['panel']}", headers=headers)

    assert create.status_code == 404
    assert read.status_code == 404


@pytest.mark.parametrize(
    ("predicate", "expected_detail"),
    [("aime", "inconnu"), ("hasPart", "hiérarchie")],
)
def test_vocabulary_errors_are_explained(two_tenants, predicate, expected_detail) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["admin_tenant"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/relations", json=_relation_body(tenant_a, predicate=predicate), headers=headers
        )

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]


def test_date_without_timezone_is_rejected(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["admin_tenant"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/relations",
            json=_relation_body(tenant_a, valid_from="2026-09-23T08:00:00"),
            headers=headers,
        )

    assert response.status_code == 422


def test_duplicate_relation_is_a_conflict(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["admin_tenant"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        first = client.post("/relations", json=_relation_body(tenant_a), headers=headers)
        second = client.post("/relations", json=_relation_body(tenant_a), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 409


def test_ending_a_relation_keeps_it_in_history(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["admin_tenant"])
    url = f"/graph/nodes/{tenant_a['ahu']}/relations"

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        relation_id = client.post(
            "/relations",
            json=_relation_body(tenant_a, valid_from="2026-09-01T00:00:00+00:00"),
            headers=headers,
        ).json()["id"]
        ended = client.post(
            f"/relations/{relation_id}/end",
            json={"reason": "Tableau remplacé"},
            headers=headers,
        )
        ended_twice = client.post(
            f"/relations/{relation_id}/end",
            json={"reason": "Deuxième tentative"},
            headers=headers,
        )
        current = client.get(url, headers=headers).json()
        history = client.get(url, params={"include_ended": True}, headers=headers).json()

    assert ended.status_code == 200
    assert ended.json()["valid_to"] is not None
    assert ended_twice.status_code == 409
    assert relation_id not in {edge["id"] for edge in current}
    assert relation_id in {edge["id"] for edge in history}


def test_ending_a_relation_requires_a_reason(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["admin_tenant"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        relation_id = client.post(
            "/relations", json=_relation_body(tenant_a), headers=headers
        ).json()["id"]
        response = client.post(f"/relations/{relation_id}/end", json={}, headers=headers)

    assert response.status_code == 422


def test_read_node_returns_its_type(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get(f"/graph/nodes/{tenant_a['site']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["node_type"] == "site"
