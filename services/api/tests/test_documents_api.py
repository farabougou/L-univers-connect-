"""Documents d'équipement (section 36, point 10 — directive UI/dashboard) :
envoi, lecture, bibliothèque portefeuille, isolation."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_documents_for_tenant
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)

_FAKE_SHA256 = "b" * 64


def _create_tenant(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    functional_location_id = uuid.uuid4()
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
            {"id": functional_location_id, "tenant_id": tenant_id, "site_id": site_id},
        )
    return {
        "tenant_id": tenant_id,
        "site_id": site_id,
        "functional_location_id": functional_location_id,
    }


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    purge_audit_log_for_tenant(tenant_id)
    purge_documents_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("functional_locations", "sites"):
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
    tenant = _create_tenant("ClientDocuments")
    yield tenant
    _cleanup(tenant)


def _upload_and_create(
    tenant: dict, headers: dict, *, filename: str = "manuel.pdf", category: str = "manual"
) -> dict:
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        upload_url_response = client.post(
            f"/functional-locations/{tenant['functional_location_id']}/documents/upload-url",
            json={"filename": filename, "content_type": "application/pdf"},
            headers=headers,
        )
        assert upload_url_response.status_code == 200
        object_key = upload_url_response.json()["object_key"]

        create_response = client.post(
            f"/functional-locations/{tenant['functional_location_id']}/documents",
            json={
                "category": category,
                "object_key": object_key,
                "filename": filename,
                "content_type": "application/pdf",
                "sha256": _FAKE_SHA256,
            },
            headers=headers,
        )
    assert create_response.status_code == 201
    return create_response.json()


def test_envoi_puis_lecture_d_un_document(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    document = _upload_and_create(tenant, headers)

    assert document["category"] == "manual"
    assert document["filename"] == "manuel.pdf"
    assert document["download_url"].startswith("http")

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        get_response = client.get(f"/documents/{document['id']}", headers=headers)
        list_response = client.get(
            f"/functional-locations/{tenant['functional_location_id']}/documents",
            headers=headers,
        )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == document["id"]
    assert [d["id"] for d in list_response.json()] == [document["id"]]


def test_deux_envois_restent_deux_documents_distincts_sans_ecraser_le_premier(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    first = _upload_and_create(
        tenant, headers, filename="certificat-2025.pdf", category="certificate"
    )
    second = _upload_and_create(
        tenant, headers, filename="certificat-2026.pdf", category="certificate"
    )

    assert first["id"] != second["id"]

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        list_response = client.get(
            f"/functional-locations/{tenant['functional_location_id']}/documents",
            headers=headers,
        )
    ids = {d["id"] for d in list_response.json()}
    assert ids == {first["id"], second["id"]}


def test_bibliotheque_portefeuille_montre_l_equipement_vise(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    document = _upload_and_create(tenant, headers)

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/documents/portfolio", headers=headers)

    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["id"] == document["id"]
    assert entries[0]["functional_location_code"] == "cta-01"
    assert entries[0]["functional_location_name"] == "CTA 01"


def test_technicien_ne_peut_pas_envoyer_mais_peut_consulter(tenant) -> None:
    admin_headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    document = _upload_and_create(tenant, admin_headers)

    tech_headers = _auth_headers(tenant["tenant_id"], ["technicien"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        upload_url_response = client.post(
            f"/functional-locations/{tenant['functional_location_id']}/documents/upload-url",
            json={"filename": "essai.pdf", "content_type": "application/pdf"},
            headers=tech_headers,
        )
        get_response = client.get(f"/documents/{document['id']}", headers=tech_headers)

    assert upload_url_response.status_code == 403
    assert get_response.status_code == 200


def test_categorie_inconnue_est_refusee(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        upload_url_response = client.post(
            f"/functional-locations/{tenant['functional_location_id']}/documents/upload-url",
            json={"filename": "x.pdf", "content_type": "application/pdf"},
            headers=headers,
        )
        object_key = upload_url_response.json()["object_key"]
        create_response = client.post(
            f"/functional-locations/{tenant['functional_location_id']}/documents",
            json={
                "category": "inconnue",
                "object_key": object_key,
                "filename": "x.pdf",
                "content_type": "application/pdf",
                "sha256": _FAKE_SHA256,
            },
            headers=headers,
        )

    assert create_response.status_code == 422
    assert create_response.json()["code"] == "DOCUMENT_CATEGORY_UNKNOWN"


def test_type_de_fichier_non_pris_en_charge_est_refuse(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        upload_url_response = client.post(
            f"/functional-locations/{tenant['functional_location_id']}/documents/upload-url",
            json={"filename": "x.dwg", "content_type": "image/svg+xml"},
            headers=headers,
        )
        object_key = upload_url_response.json()["object_key"]
        create_response = client.post(
            f"/functional-locations/{tenant['functional_location_id']}/documents",
            json={
                "category": "other",
                "object_key": object_key,
                "filename": "x.dwg",
                "content_type": "image/svg+xml",
                "sha256": _FAKE_SHA256,
            },
            headers=headers,
        )

    assert create_response.status_code == 422
    assert create_response.json()["code"] == "DOCUMENT_CONTENT_TYPE_UNSUPPORTED"


def test_cle_de_stockage_d_un_autre_equipement_est_refusee(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    foreign_key = (
        f"{tenant['tenant_id']}/documents/{uuid.uuid4()}/{uuid.uuid4()}-manuel.pdf"
    )

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        create_response = client.post(
            f"/functional-locations/{tenant['functional_location_id']}/documents",
            json={
                "category": "manual",
                "object_key": foreign_key,
                "filename": "manuel.pdf",
                "content_type": "application/pdf",
                "sha256": _FAKE_SHA256,
            },
            headers=headers,
        )

    assert create_response.status_code == 422
    assert create_response.json()["code"] == "DOCUMENT_STORAGE_KEY_FOREIGN"


def test_equipement_inconnu_renvoie_404(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            f"/functional-locations/{uuid.uuid4()}/documents/upload-url",
            json={"filename": "x.pdf", "content_type": "application/pdf"},
            headers=headers,
        )
    assert response.status_code == 404
    assert response.json()["code"] == "FUNCTIONAL_LOCATION_NOT_FOUND"


def test_document_inconnu_renvoie_404(tenant) -> None:
    headers = _auth_headers(tenant["tenant_id"], ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get(f"/documents/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "DOCUMENT_NOT_FOUND"


def test_isolation_un_tenant_ne_voit_jamais_le_document_d_un_autre() -> None:
    tenant_a = _create_tenant("ClientDocsIsoA")
    tenant_b = _create_tenant("ClientDocsIsoB")
    try:
        headers_a = _auth_headers(tenant_a["tenant_id"], ["admin_tenant"])
        document = _upload_and_create(tenant_a, headers_a)

        headers_b = _auth_headers(tenant_b["tenant_id"], ["admin_tenant"])
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            get_response = client.get(f"/documents/{document['id']}", headers=headers_b)
            portfolio_response = client.get("/documents/portfolio", headers=headers_b)
        assert get_response.status_code == 404
        assert portfolio_response.json() == []
    finally:
        _cleanup(tenant_a)
        _cleanup(tenant_b)
