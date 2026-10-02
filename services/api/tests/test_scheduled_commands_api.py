"""API de planification de commande (app/routers/commands.py,
POST/GET /scheduled-commands, POST .../cancel) — priorité « planification »
de la feuille de route V2."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_config_versions_for_tenant
from tests.jwt_helpers import JWKS, make_token
from tests.modbus_fixtures import activate_device_mapping, create_tenant_with_energy_point

client = TestClient(app)


def _human_headers(tenant_id, roles=("technicien",)):
    token = make_token(roles=list(roles), tenant_id=str(tenant_id))
    return {"Authorization": f"Bearer {token}"}


def _cleanup(tenant_id):
    purge_config_versions_for_tenant(tenant_id)
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "events",
            "scheduled_commands",
            "commands",
            "edge_devices",
            "points",
            "functional_locations",
            "sites",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _commandable_tenant():
    created = create_tenant_with_energy_point("ClientPlanificationApi")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=5921,
        device_type="simulated_relay",
        points=[{"point_id": str(created["point_id"]), "register_name": "relay_state"}],
    )
    return created


def test_planifier_une_commande():
    tenant = _commandable_tenant()
    try:
        scheduled_for = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            response = client.post(
                "/scheduled-commands",
                json={
                    "point_id": str(tenant["point_id"]),
                    "requested_value": 1.0,
                    "scheduled_for": scheduled_for,
                },
                headers=_human_headers(tenant["tenant_id"]),
            )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "pending"
        assert body["requested_value"] == 1.0
    finally:
        _cleanup(tenant["tenant_id"])


def test_planifier_dans_le_passe_est_refuse():
    tenant = _commandable_tenant()
    try:
        scheduled_for = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            response = client.post(
                "/scheduled-commands",
                json={
                    "point_id": str(tenant["point_id"]),
                    "requested_value": 1.0,
                    "scheduled_for": scheduled_for,
                },
                headers=_human_headers(tenant["tenant_id"]),
            )
        assert response.status_code == 422
        assert response.json()["code"] == "SCHEDULED_COMMAND_IN_THE_PAST"
    finally:
        _cleanup(tenant["tenant_id"])


def test_lister_puis_annuler_une_commande_planifiee():
    tenant = _commandable_tenant()
    try:
        scheduled_for = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            created = client.post(
                "/scheduled-commands",
                json={
                    "point_id": str(tenant["point_id"]),
                    "requested_value": 1.0,
                    "scheduled_for": scheduled_for,
                },
                headers=_human_headers(tenant["tenant_id"]),
            )
            scheduled_id = created.json()["id"]

            listed = client.get(
                f"/scheduled-commands?point_id={tenant['point_id']}",
                headers=_human_headers(tenant["tenant_id"]),
            )
            assert listed.status_code == 200
            assert len(listed.json()) == 1

            cancelled = client.post(
                f"/scheduled-commands/{scheduled_id}/cancel",
                headers=_human_headers(tenant["tenant_id"], roles=("responsable_exploitation",)),
            )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "cancelled"
    finally:
        _cleanup(tenant["tenant_id"])


def test_annuler_deux_fois_est_refuse():
    tenant = _commandable_tenant()
    try:
        scheduled_for = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            created = client.post(
                "/scheduled-commands",
                json={
                    "point_id": str(tenant["point_id"]),
                    "requested_value": 1.0,
                    "scheduled_for": scheduled_for,
                },
                headers=_human_headers(tenant["tenant_id"]),
            )
            scheduled_id = created.json()["id"]
            client.post(
                f"/scheduled-commands/{scheduled_id}/cancel",
                headers=_human_headers(tenant["tenant_id"]),
            )
            second = client.post(
                f"/scheduled-commands/{scheduled_id}/cancel",
                headers=_human_headers(tenant["tenant_id"]),
            )
        assert second.status_code == 409
        assert second.json()["code"] == "SCHEDULED_COMMAND_NOT_CANCELLABLE"
    finally:
        _cleanup(tenant["tenant_id"])


def test_isolation_tenant_sur_les_commandes_planifiees():
    tenant_a = _commandable_tenant()
    tenant_b = _commandable_tenant()
    try:
        scheduled_for = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            created = client.post(
                "/scheduled-commands",
                json={
                    "point_id": str(tenant_a["point_id"]),
                    "requested_value": 1.0,
                    "scheduled_for": scheduled_for,
                },
                headers=_human_headers(tenant_a["tenant_id"]),
            )
            assert created.status_code == 201

            listed = client.get(
                f"/scheduled-commands?point_id={tenant_a['point_id']}",
                headers=_human_headers(tenant_b["tenant_id"]),
            )
            assert listed.status_code == 200
            assert listed.json() == []

            cancel_attempt = client.post(
                f"/scheduled-commands/{created.json()['id']}/cancel",
                headers=_human_headers(tenant_b["tenant_id"]),
            )
            assert cancel_attempt.status_code == 404
    finally:
        _cleanup(tenant_a["tenant_id"])
        _cleanup(tenant_b["tenant_id"])


def test_scheduled_command_id_inconnu():
    tenant = _commandable_tenant()
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            response = client.post(
                f"/scheduled-commands/{uuid.uuid4()}/cancel",
                headers=_human_headers(tenant["tenant_id"]),
            )
        assert response.status_code == 404
        assert response.json()["code"] == "SCHEDULED_COMMAND_NOT_FOUND"
    finally:
        _cleanup(tenant["tenant_id"])
