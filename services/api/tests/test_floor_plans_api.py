"""Plans 2D (ADR 011, étape S3) : envoi, versions, lecture, isolation."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_floor_plans_for_tenant
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)

_FAKE_SHA256 = "a" * 64


def _create_tenant(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    space_id = uuid.uuid4()
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
    return {"tenant_id": tenant_id, "site_id": site_id, "space_id": space_id}


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    purge_audit_log_for_tenant(tenant_id)
    purge_floor_plans_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("spaces", "sites"):
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
    tenant = _create_tenant("ClientPlans")
    yield tenant
    _cleanup(tenant)


def _upload_and_create(tenant: dict, headers: dict, filename: str = "etage1.pdf") -> dict:
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        upload_url_response = client.post(
            f"/spaces/{tenant['space_id']}/floor-plans/upload-url",
            json={"filename": filename, "content_type": "application/pdf"},
            headers=headers,
        )
        assert upload_url_response.status_code == 200
        object_key = upload_url_response.json()["object_key"]

        create_response = client.post(
            f"/spaces/{tenant['space_id']}/floor-plans",
            json={
                "object_key": object_key,
                "filename": filename,
                "content_type": "application/pdf",
                "sha256": _FAKE_SHA256,
            },
            headers=headers,
        )
    assert create_response.status_code == 201
    return create_response.json()


def test_envoi_puis_lecture_d_un_plan(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    plan = _upload_and_create(tenant, headers)

    assert plan["version"] == 1
    assert plan["filename"] == "etage1.pdf"
    assert plan["content_type"] == "application/pdf"
    assert plan["download_url"].startswith("http")

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        get_response = client.get(f"/floor-plans/{plan['id']}", headers=headers)
        list_response = client.get(
            f"/spaces/{tenant['space_id']}/floor-plans", headers=headers
        )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == plan["id"]
    assert [p["id"] for p in list_response.json()] == [plan["id"]]


def test_un_second_envoi_cree_une_nouvelle_version_sans_ecraser_la_premiere(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    first = _upload_and_create(tenant, headers, filename="etage1-v1.pdf")
    second = _upload_and_create(tenant, headers, filename="etage1-v2.pdf")

    assert first["version"] == 1
    assert second["version"] == 2
    assert first["id"] != second["id"]

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        list_response = client.get(
            f"/spaces/{tenant['space_id']}/floor-plans", headers=headers
        )
    versions = [(p["id"], p["version"]) for p in list_response.json()]
    # La plus récente version en premier.
    assert versions == [(second["id"], 2), (first["id"], 1)]


def test_technicien_ne_peut_pas_envoyer_un_plan_mais_peut_le_consulter(tenant) -> None:
    admin_headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    plan = _upload_and_create(tenant, admin_headers)

    tech_headers = _auth_headers(tenant["tenant_id"], ["technicien"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        upload_url_response = client.post(
            f"/spaces/{tenant['space_id']}/floor-plans/upload-url",
            json={"filename": "essai.pdf", "content_type": "application/pdf"},
            headers=tech_headers,
        )
        get_response = client.get(f"/floor-plans/{plan['id']}", headers=tech_headers)

    assert upload_url_response.status_code == 403
    assert get_response.status_code == 200


def test_type_de_fichier_non_pris_en_charge_est_refuse(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        upload_url_response = client.post(
            f"/spaces/{tenant['space_id']}/floor-plans/upload-url",
            json={"filename": "plan.dwg", "content_type": "image/svg+xml"},
            headers=headers,
        )
        object_key = upload_url_response.json()["object_key"]
        create_response = client.post(
            f"/spaces/{tenant['space_id']}/floor-plans",
            json={
                "object_key": object_key,
                "filename": "plan.dwg",
                "content_type": "image/svg+xml",
                "sha256": _FAKE_SHA256,
            },
            headers=headers,
        )

    assert create_response.status_code == 422
    assert create_response.json()["code"] == "FLOOR_PLAN_CONTENT_TYPE_UNSUPPORTED"


def test_cle_de_stockage_d_un_autre_espace_est_refusee(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    foreign_key = f"{tenant['tenant_id']}/floor-plans/{uuid.uuid4()}/{uuid.uuid4()}-plan.pdf"

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        create_response = client.post(
            f"/spaces/{tenant['space_id']}/floor-plans",
            json={
                "object_key": foreign_key,
                "filename": "plan.pdf",
                "content_type": "application/pdf",
                "sha256": _FAKE_SHA256,
            },
            headers=headers,
        )

    assert create_response.status_code == 422
    assert create_response.json()["code"] == "FLOOR_PLAN_STORAGE_KEY_FOREIGN"


def test_espace_inconnu_renvoie_404(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            f"/spaces/{uuid.uuid4()}/floor-plans/upload-url",
            json={"filename": "plan.pdf", "content_type": "application/pdf"},
            headers=headers,
        )
    assert response.status_code == 404
    assert response.json()["code"] == "SPACE_NOT_FOUND"


def test_plan_inconnu_renvoie_404(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get(f"/floor-plans/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "FLOOR_PLAN_NOT_FOUND"


def test_bibliotheque_portefeuille_montre_la_derniere_version_avec_site_et_espace(
    tenant,
) -> None:
    """Page Spatial/BIM (section 36, point 12) : GET /floor-plans/portfolio
    ne montre que la dernière version de chaque espace, avec le site et
    l'espace visés — jamais toutes les versions."""
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    _upload_and_create(tenant, headers, filename="etage1-v1.pdf")
    second = _upload_and_create(tenant, headers, filename="etage1-v2.pdf")

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/floor-plans/portfolio", headers=headers)

    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["id"] == second["id"]
    assert entries[0]["version"] == 2
    assert entries[0]["space_id"] == str(tenant["space_id"])
    assert entries[0]["space_code"] == "ET1"
    assert entries[0]["site_id"] == str(tenant["site_id"])
    assert entries[0]["validated_placement_count"] == 0


def test_isolation_un_tenant_ne_voit_jamais_le_plan_d_un_autre() -> None:
    tenant_a = _create_tenant("ClientPlansIsoA")
    tenant_b = _create_tenant("ClientPlansIsoB")
    try:
        headers_a = _auth_headers(tenant_a["tenant_id"], ["admin_tenant"])
        plan = _upload_and_create(tenant_a, headers_a)

        headers_b = _auth_headers(tenant_b["tenant_id"], ["admin_tenant"])
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            response = client.get(f"/floor-plans/{plan['id']}", headers=headers_b)
        assert response.status_code == 404
    finally:
        _cleanup(tenant_a)
        _cleanup(tenant_b)
