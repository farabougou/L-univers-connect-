"""Placement des actifs sur un plan (ADR 011, étape S4) : espace, position
ou point, jamais deux à la fois, avec un cycle proposé → validé."""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.floor_plans import record_floor_plan
from app.main import app
from app.points import create_point, get_point
from app.telemetry import record_measurement
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_floor_plans_for_tenant
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)


def _create_tenant(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    space_id = uuid.uuid4()
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
                "INSERT INTO spaces (id, tenant_id, site_id, space_type, code, name, valid_from) "
                "VALUES (:id, :tenant_id, :site_id, 'floor', 'ET1', 'Étage 1', now())"
            ),
            {"id": space_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'pac-01', 'PAC 01')"
            ),
            {"id": location_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        point_id = create_point(
            connection,
            tenant_id=tenant_id,
            code=f"PAC01-MARCHE-{tenant_id}",
            name="Marche",
            value_type="boolean",
            functional_location_id=location_id,
            created_by="test",
        )
        floor_plan_id = record_floor_plan(
            connection,
            tenant_id=tenant_id,
            space_id=space_id,
            storage_key=f"{tenant_id}/floor-plans/{space_id}/{uuid.uuid4()}-etage1.pdf",
            content_type="application/pdf",
            filename="etage1.pdf",
            sha256="a" * 64,
            uploaded_by="test",
        )
    return {
        "tenant_id": tenant_id,
        "site_id": site_id,
        "space_id": space_id,
        "location_id": location_id,
        "point_id": point_id,
        "floor_plan_id": floor_plan_id,
    }


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("DELETE FROM plan_placements WHERE tenant_id = :id"), {"id": tenant_id}
        )
    purge_floor_plans_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("measurements", "points", "functional_locations", "spaces", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _auth_headers(tenant_id: uuid.UUID, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant_id), roles=roles)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def tenant():
    tenant = _create_tenant("ClientPlacements")
    yield tenant
    _cleanup(tenant)


def test_propose_puis_valider_un_placement_d_espace(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        create_response = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={"space_id": str(tenant["space_id"]), "x_ratio": 0.5, "y_ratio": 0.25},
            headers=headers,
        )
    assert create_response.status_code == 201
    placement = create_response.json()
    assert placement["status"] == "proposed"
    assert placement["space_id"] == str(tenant["space_id"])
    assert placement["functional_location_id"] is None
    assert placement["point_id"] is None

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        validate_response = client.post(f"/placements/{placement['id']}/validate", headers=headers)
    assert validate_response.status_code == 200
    assert validate_response.json()["status"] == "validated"
    assert validate_response.json()["validated_by"] is not None


def test_placement_de_position_et_de_point(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        location_response = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={
                "functional_location_id": str(tenant["location_id"]),
                "x_ratio": 0.1,
                "y_ratio": 0.9,
            },
            headers=headers,
        )
        point_response = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={"point_id": str(tenant["point_id"]), "x_ratio": 0.4, "y_ratio": 0.4},
            headers=headers,
        )
        list_response = client.get(
            f"/floor-plans/{tenant['floor_plan_id']}/placements", headers=headers
        )

    assert location_response.status_code == 201
    assert point_response.status_code == 201
    ids = {p["id"] for p in list_response.json()}
    assert ids == {location_response.json()["id"], point_response.json()["id"]}


def test_aucun_ou_plusieurs_cibles_est_refuse(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        none_response = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={"x_ratio": 0.5, "y_ratio": 0.5},
            headers=headers,
        )
        both_response = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={
                "space_id": str(tenant["space_id"]),
                "functional_location_id": str(tenant["location_id"]),
                "x_ratio": 0.5,
                "y_ratio": 0.5,
            },
            headers=headers,
        )

    assert none_response.status_code == 422
    assert none_response.json()["code"] == "PLAN_PLACEMENT_EXACTLY_ONE_TARGET"
    assert both_response.status_code == 422
    assert both_response.json()["code"] == "PLAN_PLACEMENT_EXACTLY_ONE_TARGET"


def test_cible_introuvable_est_refusee(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={"space_id": str(uuid.uuid4()), "x_ratio": 0.5, "y_ratio": 0.5},
            headers=headers,
        )
    assert response.status_code == 404
    assert response.json()["code"] == "SPACE_NOT_FOUND"


def test_technicien_ne_peut_pas_proposer_mais_peut_lister(tenant) -> None:
    admin_headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        create_response = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={"space_id": str(tenant["space_id"]), "x_ratio": 0.5, "y_ratio": 0.5},
            headers=admin_headers,
        )
    placement_id = create_response.json()["id"]

    tech_headers = _auth_headers(tenant["tenant_id"], ["technicien"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        propose_response = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={"space_id": str(tenant["space_id"]), "x_ratio": 0.2, "y_ratio": 0.2},
            headers=tech_headers,
        )
        validate_response = client.post(
            f"/placements/{placement_id}/validate", headers=tech_headers
        )
        list_response = client.get(
            f"/floor-plans/{tenant['floor_plan_id']}/placements", headers=tech_headers
        )

    assert propose_response.status_code == 403
    assert validate_response.status_code == 403
    assert list_response.status_code == 200


def test_valider_deux_fois_est_un_conflit(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        create_response = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={"space_id": str(tenant["space_id"]), "x_ratio": 0.5, "y_ratio": 0.5},
            headers=headers,
        )
        placement_id = create_response.json()["id"]
        client.post(f"/placements/{placement_id}/validate", headers=headers)
        second_validate = client.post(f"/placements/{placement_id}/validate", headers=headers)

    assert second_validate.status_code == 409
    assert second_validate.json()["code"] == "PLAN_PLACEMENT_ALREADY_VALIDATED"


def test_supprimer_un_placement(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        create_response = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={"space_id": str(tenant["space_id"]), "x_ratio": 0.5, "y_ratio": 0.5},
            headers=headers,
        )
        placement_id = create_response.json()["id"]
        delete_response = client.delete(f"/placements/{placement_id}", headers=headers)
        list_response = client.get(
            f"/floor-plans/{tenant['floor_plan_id']}/placements", headers=headers
        )

    assert delete_response.status_code == 204
    assert list_response.json() == []


def test_placement_introuvable_renvoie_404(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        validate_response = client.post(f"/placements/{uuid.uuid4()}/validate", headers=headers)
        delete_response = client.delete(f"/placements/{uuid.uuid4()}", headers=headers)

    assert validate_response.status_code == 404
    assert validate_response.json()["code"] == "PLAN_PLACEMENT_NOT_FOUND"
    assert delete_response.status_code == 404
    assert delete_response.json()["code"] == "PLAN_PLACEMENT_NOT_FOUND"


def test_affichage_temps_reel_montre_la_derniere_valeur_du_point(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        point = get_point(connection, tenant["point_id"])
        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=point,
            value=1.0,
            measured_at=datetime.now(UTC),
            origin="measured",
            source="test",
            received_at=datetime.now(UTC),
        )

    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        proposed = client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={"point_id": str(tenant["point_id"]), "x_ratio": 0.4, "y_ratio": 0.4},
            headers=headers,
        )
        placement_id = proposed.json()["id"]
        client.post(f"/placements/{placement_id}/validate", headers=headers)
        live_response = client.get(
            f"/floor-plans/{tenant['floor_plan_id']}/placements/live", headers=headers
        )

    assert live_response.status_code == 200
    [live] = live_response.json()
    assert live["id"] == placement_id
    assert live["point_value"] == 1.0
    assert live["point_value_type"] == "boolean"
    assert live["point_measured_at"] is not None
    assert isinstance(live["point_trust_score"], int)


def test_affichage_temps_reel_masque_les_placements_encore_proposes(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        client.post(
            f"/floor-plans/{tenant['floor_plan_id']}/placements",
            json={"space_id": str(tenant["space_id"]), "x_ratio": 0.5, "y_ratio": 0.5},
            headers=headers,
        )
        live_response = client.get(
            f"/floor-plans/{tenant['floor_plan_id']}/placements/live", headers=headers
        )

    assert live_response.status_code == 200
    assert live_response.json() == []
