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
            {"id": tenant_id, "name": "Client GMAO", "slug": f"client-gmao-{tenant_id}"},
        )

    yield tenant_id

    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "intervention_photos",
            "interventions",
            "alarm_status_history",
            "alarms",
            "work_order_status_history",
            "work_orders",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _auth_headers(tenant_id: uuid.UUID, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant_id), roles=roles)
    return {"Authorization": f"Bearer {token}"}


def test_technicien_cannot_create_work_order(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post("/work-orders", json={"title": "Réviser la PAC"}, headers=headers)

    assert response.status_code == 403


def test_technicien_can_update_work_order_status(tenant_id) -> None:
    admin_headers = _auth_headers(tenant_id, ["admin_tenant"])
    technicien_headers = _auth_headers(tenant_id, ["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        create_response = client.post(
            "/work-orders",
            json={"title": "Réviser la PAC", "priority": "high"},
            headers=admin_headers,
        )
        assert create_response.status_code == 201
        work_order_id = create_response.json()["id"]
        assert create_response.json()["status"] == "open"

        update_response = client.patch(
            f"/work-orders/{work_order_id}/status",
            json={"status": "in_progress", "note": "Départ sur site"},
            headers=technicien_headers,
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "in_progress"

        history_response = client.get(
            f"/work-orders/{work_order_id}/history", headers=admin_headers
        )
        assert [entry["status"] for entry in history_response.json()] == ["open", "in_progress"]


def test_full_maintenance_flow(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        alarm_response = client.post(
            "/alarms",
            json={"severity": "critical", "message": "Pression basse"},
            headers=headers,
        )
        assert alarm_response.status_code == 201
        alarm_id = alarm_response.json()["id"]
        created = alarm_response.json()
        assert (created["condition_state"], created["ack_state"], created["handling_status"]) == (
            "active",
            "unacknowledged",
            "open",
        )

        ack_response = client.post(f"/alarms/{alarm_id}/acknowledge", json={}, headers=headers)
        assert ack_response.json()["ack_state"] == "acknowledged"
        assert ack_response.json()["condition_state"] == "active"

        too_early = client.patch(
            f"/alarms/{alarm_id}/handling", json={"handling_status": "closed"}, headers=headers
        )
        assert too_early.status_code == 409

        cleared = client.post(
            f"/alarms/{alarm_id}/clear", json={"note": "Vanne resserrée"}, headers=headers
        )
        closed = client.patch(
            f"/alarms/{alarm_id}/handling", json={"handling_status": "closed"}, headers=headers
        )
        assert cleared.json()["condition_state"] == "cleared"
        assert closed.json()["handling_status"] == "closed"

        history_response = client.get(f"/alarms/{alarm_id}/history", headers=headers)
        assert [(entry["field"], entry["value"]) for entry in history_response.json()] == [
            ("handling_status", "open"),
            ("ack_state", "acknowledged"),
            ("condition_state", "cleared"),
            ("handling_status", "closed"),
        ]

        intervention_response = client.post(
            "/interventions",
            json={"summary": "Resserrage de la vanne"},
            headers=headers,
        )
        assert intervention_response.status_code == 201
        assert intervention_response.json()["technician"] is not None

        alarms = client.get("/alarms", headers=headers)
        assert [a["id"] for a in alarms.json()] == [alarm_id]


def test_create_ronde_with_checklist(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["technicien"])
    checklist = {"pression_ok": True, "bruit_anormal": False}

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/interventions",
            json={
                "intervention_type": "ronde",
                "checklist": checklist,
                "summary": "RAS sinon",
            },
            headers=headers,
        )

    assert response.status_code == 201
    body = response.json()
    assert body["intervention_type"] == "ronde"
    assert body["checklist"] == checklist


def test_photo_upload_url_then_confirm_returns_download_url(tenant_id) -> None:
    """La génération d'URL pré-signée (boto3) est une opération de signature
    locale : elle ne demande aucune connexion réelle au stockage (MinIO n'a
    donc pas besoin de tourner pour ce test, voir ADR 006)."""
    headers = _auth_headers(tenant_id, ["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        intervention_response = client.post(
            "/interventions", json={"summary": "Contrôle filtre"}, headers=headers
        )
        assert intervention_response.status_code == 201
        intervention_id = intervention_response.json()["id"]

        upload_url_response = client.post(
            f"/interventions/{intervention_id}/photos/upload-url",
            json={"filename": "filtre.jpg", "content_type": "image/jpeg"},
            headers=headers,
        )
        assert upload_url_response.status_code == 200
        body = upload_url_response.json()
        assert body["upload_url"].startswith("http")
        assert str(tenant_id) in body["object_key"]
        assert intervention_id in body["object_key"]

        create_photo_response = client.post(
            f"/interventions/{intervention_id}/photos",
            json={"object_key": body["object_key"], "caption": "Avant nettoyage"},
            headers=headers,
        )
        assert create_photo_response.status_code == 201
        photo = create_photo_response.json()
        assert photo["caption"] == "Avant nettoyage"
        assert photo["download_url"].startswith("http")

        list_response = client.get(f"/interventions/{intervention_id}/photos", headers=headers)
        assert [p["id"] for p in list_response.json()] == [photo["id"]]


def test_photo_upload_url_on_unknown_intervention_returns_404(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["technicien"])
    random_intervention_id = uuid.uuid4()

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            f"/interventions/{random_intervention_id}/photos/upload-url",
            json={"filename": "photo.jpg", "content_type": "image/jpeg"},
            headers=headers,
        )

    assert response.status_code == 404


def test_work_order_on_unknown_functional_location_returns_404(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    random_location_id = uuid.uuid4()

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/work-orders",
            json={"title": "Tâche", "functional_location_id": str(random_location_id)},
            headers=headers,
        )

    assert response.status_code == 404
