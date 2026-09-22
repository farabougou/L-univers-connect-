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
        assert alarm_response.json()["status"] == "open"

        ack_response = client.patch(
            f"/alarms/{alarm_id}/status", json={"status": "acknowledged"}, headers=headers
        )
        assert ack_response.status_code == 200

        resolve_response = client.patch(
            f"/alarms/{alarm_id}/status",
            json={"status": "resolved", "note": "Vanne resserrée"},
            headers=headers,
        )
        assert resolve_response.status_code == 200
        assert resolve_response.json()["status"] == "resolved"

        history_response = client.get(f"/alarms/{alarm_id}/history", headers=headers)
        assert [entry["status"] for entry in history_response.json()] == [
            "open",
            "acknowledged",
            "resolved",
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
