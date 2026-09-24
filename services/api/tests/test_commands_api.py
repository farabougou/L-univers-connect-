"""API de commande (app/routers/commands.py) : humain (POST/GET /commands) et
appareil (GET/POST /edge/commands). Exception scopée à la règle non
négociable 1 — voir CLAUDE.md et app/commands.py.
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.devices import provision_device
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
        for table in ("commands", "edge_devices", "points", "functional_locations", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _commandable_tenant(
    *, device_type: str = "simulated_relay", register_name: str = "relay_state"
):
    created = create_tenant_with_energy_point("ClientCommandesApi")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=5921,
        device_type=device_type,
        points=[{"point_id": str(created["point_id"]), "register_name": register_name}],
    )
    return created


def _device_token(tenant, *, scopes_needed="command:execute"):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        device_id, secret = provision_device(
            connection, tenant_id=tenant["tenant_id"], device_id="relais-01", created_by="test"
        )
    auth = client.post(
        "/devices/auth",
        json={"tenant_id": str(tenant["tenant_id"]), "device_id": "relais-01", "secret": secret},
    )
    assert auth.status_code == 200
    assert scopes_needed in auth.json()["scopes"]
    return auth.json()["access_token"], device_id


def test_creer_une_commande_sur_un_point_pilotable(monkeypatch):
    tenant = _commandable_tenant()
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            response = client.post(
                "/commands",
                json={"point_id": str(tenant["point_id"]), "requested_value": 1.0},
                headers=_human_headers(tenant["tenant_id"]),
            )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "pending"
        assert body["requested_value"] == 1.0
    finally:
        _cleanup(tenant["tenant_id"])


def test_refuse_une_commande_sur_un_point_non_pilotable():
    tenant = create_tenant_with_energy_point("ClientNonPilotableApi")
    activate_device_mapping(
        tenant_id=tenant["tenant_id"],
        equipment_id=tenant["location_id"],
        host="127.0.0.1",
        port=5020,
        points=[{"point_id": str(tenant["point_id"]), "register_name": "total_active_energy"}],
    )
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            response = client.post(
                "/commands",
                json={"point_id": str(tenant["point_id"]), "requested_value": 1.0},
                headers=_human_headers(tenant["tenant_id"]),
            )
        assert response.status_code == 422
        assert response.json()["code"] == "COMMAND_POINT_NOT_CONTROLLABLE"
    finally:
        _cleanup(tenant["tenant_id"])


def test_lister_l_historique_d_un_point():
    tenant = _commandable_tenant()
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            client.post(
                "/commands",
                json={"point_id": str(tenant["point_id"]), "requested_value": 1.0},
                headers=_human_headers(tenant["tenant_id"]),
            )
            client.post(
                "/commands",
                json={"point_id": str(tenant["point_id"]), "requested_value": 0.0},
                headers=_human_headers(tenant["tenant_id"]),
            )
            response = client.get(
                f"/commands?point_id={tenant['point_id']}",
                headers=_human_headers(tenant["tenant_id"]),
            )
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["requested_value"] == 0.0  # le plus récent d'abord
    finally:
        _cleanup(tenant["tenant_id"])


def test_appareil_sans_jeton_humain_ne_peut_pas_creer_de_commande():
    tenant = _commandable_tenant()
    try:
        token, _ = _device_token(tenant)
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            response = client.post(
                "/commands",
                json={"point_id": str(tenant["point_id"]), "requested_value": 1.0},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401
    finally:
        _cleanup(tenant["tenant_id"])


def test_edge_recupere_puis_ne_recupere_pas_deux_fois_la_meme_commande():
    tenant = _commandable_tenant()
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            client.post(
                "/commands",
                json={"point_id": str(tenant["point_id"]), "requested_value": 1.0},
                headers=_human_headers(tenant["tenant_id"]),
            )
        token, _ = _device_token(tenant)
        headers = {"Authorization": f"Bearer {token}"}

        first = client.get(f"/edge/commands?equipment_id={tenant['location_id']}", headers=headers)
        second = client.get(f"/edge/commands?equipment_id={tenant['location_id']}", headers=headers)

        assert first.status_code == 200
        assert len(first.json()) == 1
        assert second.json() == []
    finally:
        _cleanup(tenant["tenant_id"])


def test_boucle_complete_commande_verifiee():
    tenant = _commandable_tenant()
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            created = client.post(
                "/commands",
                json={"point_id": str(tenant["point_id"]), "requested_value": 1.0},
                headers=_human_headers(tenant["tenant_id"]),
            )
        command_id = created.json()["id"]

        token, _ = _device_token(tenant)
        headers = {"Authorization": f"Bearer {token}"}
        pending = client.get(
            f"/edge/commands?equipment_id={tenant['location_id']}", headers=headers
        ).json()
        assert [c["id"] for c in pending] == [command_id]

        ack = client.post(
            f"/edge/commands/{command_id}/ack",
            json={"success": True, "actual_value": 1.0},
            headers=headers,
        )
        assert ack.status_code == 200
        assert ack.json()["status"] == "verified"

        with patch("app.auth.fetch_jwks", return_value=JWKS):
            final = client.get(
                f"/commands/{command_id}", headers=_human_headers(tenant["tenant_id"])
            )
        assert final.json()["status"] == "verified"
        assert final.json()["actual_value"] == 1.0
    finally:
        _cleanup(tenant["tenant_id"])


def test_valeur_reelle_differente_de_la_demandee_echoue():
    tenant = _commandable_tenant()
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            created = client.post(
                "/commands",
                json={"point_id": str(tenant["point_id"]), "requested_value": 1.0},
                headers=_human_headers(tenant["tenant_id"]),
            )
        command_id = created.json()["id"]
        token, _ = _device_token(tenant)
        headers = {"Authorization": f"Bearer {token}"}
        client.get(f"/edge/commands?equipment_id={tenant['location_id']}", headers=headers)

        ack = client.post(
            f"/edge/commands/{command_id}/ack",
            json={"success": True, "actual_value": 0.0},
            headers=headers,
        )
        assert ack.json()["status"] == "failed"
        assert ack.json()["failure_reason"] == "ACTUAL_STATE_MISMATCH"
    finally:
        _cleanup(tenant["tenant_id"])


def test_acquitter_deux_fois_est_refuse():
    tenant = _commandable_tenant()
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            created = client.post(
                "/commands",
                json={"point_id": str(tenant["point_id"]), "requested_value": 1.0},
                headers=_human_headers(tenant["tenant_id"]),
            )
        command_id = created.json()["id"]
        token, _ = _device_token(tenant)
        headers = {"Authorization": f"Bearer {token}"}
        client.get(f"/edge/commands?equipment_id={tenant['location_id']}", headers=headers)
        client.post(
            f"/edge/commands/{command_id}/ack",
            json={"success": True, "actual_value": 1.0},
            headers=headers,
        )
        second = client.post(
            f"/edge/commands/{command_id}/ack",
            json={"success": True, "actual_value": 1.0},
            headers=headers,
        )
        assert second.status_code == 409
        assert second.json()["code"] == "COMMAND_ALREADY_ACKNOWLEDGED"
    finally:
        _cleanup(tenant["tenant_id"])


def test_commande_inconnue_est_signalee():
    tenant = _commandable_tenant()
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            response = client.get(
                f"/commands/{uuid.uuid4()}", headers=_human_headers(tenant["tenant_id"])
            )
        assert response.status_code == 404
        assert response.json()["code"] == "COMMAND_NOT_FOUND"
    finally:
        _cleanup(tenant["tenant_id"])
