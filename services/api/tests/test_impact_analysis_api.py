"""GET /graph/nodes/{id}/impact : parcourt les relations « dependsOn »
(app/graph_vocabulary.py, jamais utilisé avant ce module) pour regrouper des
constats ouverts qui partagent potentiellement une même cause — voir
app/impact_analysis.py."""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.findings import raise_or_repeat_finding
from app.main import app
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)


def _create_tenant(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    gateway_id = uuid.uuid4()
    equip_a_id = uuid.uuid4()
    equip_b_id = uuid.uuid4()
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
        for location_id, code in (
            (gateway_id, "passerelle-01"),
            (equip_a_id, "cta-01"),
            (equip_b_id, "cta-02"),
        ):
            connection.execute(
                text(
                    "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                    "VALUES (:id, :tenant_id, :site_id, :code, :code)"
                ),
                {"id": location_id, "tenant_id": tenant_id, "site_id": site_id, "code": code},
            )
    return {
        "tenant_id": tenant_id,
        "site": site_id,
        "gateway": gateway_id,
        "equip_a": equip_a_id,
        "equip_b": equip_b_id,
    }


@pytest.fixture
def tenant():
    created = _create_tenant("ClientImpactAnalysis")
    yield created
    purge_tenant(created["tenant_id"])


def _headers(tenant: dict, roles: list[str] | None = None) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant["tenant_id"]), roles=roles or ["technicien"])
    return {"Authorization": f"Bearer {token}"}


def _depends_on(tenant: dict, subject_id, object_id, headers) -> None:
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/relations",
            json={
                "subject_id": str(subject_id),
                "predicate": "dependsOn",
                "object_id": str(object_id),
            },
            headers=headers,
        )
    assert response.status_code == 201, response.text


def _open_finding(tenant: dict, subject_node_id) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        raise_or_repeat_finding(
            connection,
            tenant_id=tenant["tenant_id"],
            dedup_key=f"test:{subject_node_id}",
            subject_node_id=subject_node_id,
            kind="fault",
            method="deterministic_rule",
            severity="warning",
            reason_code="TEST_FINDING",
            reason_params={},
            evidence={},
            seen_at=datetime.now(UTC),
            changed_by="test",
        )


def test_ce_qui_depend_transitivement_est_regroupe(tenant) -> None:
    manager = _headers(tenant, ["responsable_exploitation"])
    # equip_a dépend de la passerelle ; equip_b dépend de equip_a (transitif).
    _depends_on(tenant, tenant["equip_a"], tenant["gateway"], manager)
    _depends_on(tenant, tenant["equip_b"], tenant["equip_a"], manager)
    _open_finding(tenant, tenant["gateway"])
    _open_finding(tenant, tenant["equip_b"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get(
            f"/graph/nodes/{tenant['gateway']}/impact", headers=_headers(tenant)
        )

    assert response.status_code == 200
    body = response.json()
    assert body["node_id"] == str(tenant["gateway"])
    assert body["open_finding_count"] == 1
    impacted_by_id = {item["node_id"]: item for item in body["impacted"]}
    assert set(impacted_by_id) == {str(tenant["equip_a"]), str(tenant["equip_b"])}
    assert impacted_by_id[str(tenant["equip_a"])]["open_finding_count"] == 0
    assert impacted_by_id[str(tenant["equip_b"])]["open_finding_count"] == 1


def test_aucune_dependance_renvoie_une_liste_vide(tenant) -> None:
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get(
            f"/graph/nodes/{tenant['gateway']}/impact", headers=_headers(tenant)
        )

    assert response.status_code == 200
    assert response.json()["impacted"] == []


def test_noeud_introuvable_renvoie_404(tenant) -> None:
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get(
            f"/graph/nodes/{uuid.uuid4()}/impact", headers=_headers(tenant)
        )

    assert response.status_code == 404
    assert response.json()["code"] == "NODE_NOT_FOUND"
