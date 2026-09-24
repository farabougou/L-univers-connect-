"""API d'identité d'appareil Edge : provisionner, authentifier, révoquer,
ingérer de la télémétrie par jeton d'appareil (M4, app/routers/devices.py).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import text

from app.config_versions import activate_version, create_version
from app.connectors.device_mapping import MODBUS_DEVICE_MAPPING
from app.db import engine
from app.devices import ASSERTION_ALGORITHM
from app.main import app
from app.points import create_point, decide_point
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_config_versions_for_tenant
from tests.jwt_helpers import JWKS, make_token


def _keypair() -> tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private_pem, public_pem


def _assertion(
    private_pem: str, *, device_id: str, tenant_id, at: datetime, jti: str = "n1"
) -> str:
    claims = {
        "device_id": device_id,
        "tenant_id": str(tenant_id),
        "jti": jti,
        "iat": int(at.timestamp()),
        "exp": int((at + timedelta(seconds=30)).timestamp()),
    }
    return jwt.encode(claims, private_pem, algorithm=ASSERTION_ALGORITHM)


client = TestClient(app)
T0 = datetime(2026, 9, 24, 8, 0, tzinfo=UTC)


@pytest.fixture
def tenant():
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    location_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": "ClientDevicesApi", "slug": f"devices-api-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site')"),
            {"id": site_id, "tenant_id": tenant_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'cpt-01', 'Compteur test')"
            ),
            {"id": location_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        point_id = create_point(
            connection,
            tenant_id=tenant_id,
            code="CPT01-E",
            name="Énergie",
            value_type="number",
            point_class="energy_meter_reading",
            unit="kW.h",
            functional_location_id=location_id,
            min_value=0,
            max_value=1_000_000,
            created_by="test",
        )
        decide_point(connection, point_id=point_id, decision="validated")

    yield {
        "tenant_id": tenant_id,
        "site_id": site_id,
        "location_id": location_id,
        "point_id": point_id,
    }

    purge_config_versions_for_tenant(tenant_id)
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("DELETE FROM device_assertion_nonces WHERE tenant_id = :id"), {"id": tenant_id}
        )
        for table in ("edge_devices", "measurements", "points", "functional_locations", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _human_headers(tenant_id, roles=("responsable_exploitation",)):
    token = make_token(roles=list(roles), tenant_id=str(tenant_id))
    return {"Authorization": f"Bearer {token}"}


def test_provisionner_puis_authentifier_un_appareil(tenant):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        created = client.post(
            "/devices",
            json={"device_id": "sdm120-cpt01"},
            headers=_human_headers(tenant["tenant_id"]),
        )
        assert created.status_code == 201
        secret = created.json()["secret"]

        auth = client.post(
            "/devices/auth",
            json={
                "tenant_id": str(tenant["tenant_id"]),
                "device_id": "sdm120-cpt01",
                "secret": secret,
            },
        )
    assert auth.status_code == 200
    body = auth.json()
    assert body["token_type"] == "bearer"
    assert set(body["scopes"]) == {"telemetry:write", "config:read", "command:execute"}
    assert body["expires_in"] > 0


def test_technicien_ne_peut_pas_provisionner(tenant):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/devices",
            json={"device_id": "cpt01"},
            headers=_human_headers(tenant["tenant_id"], ["technicien"]),
        )
    assert response.status_code == 403


def test_authentification_ne_requiert_aucun_jeton_humain(tenant):
    """L'appareil n'a jamais de compte Keycloak : ce point d'entrée est
    volontairement hors du flux OIDC humain."""
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        client.post(
            "/devices", json={"device_id": "cpt01"}, headers=_human_headers(tenant["tenant_id"])
        )
    response = client.post(
        "/devices/auth",
        json={"tenant_id": str(tenant["tenant_id"]), "device_id": "cpt01", "secret": "peu-importe"},
    )
    # Pas de 401 "TOKEN_MISSING" : la route ne dépend d'aucune authentification
    # humaine, seulement du secret d'appareil (ici erroné, donc refusé).
    assert response.status_code == 401
    assert response.json()["code"] == "DEVICE_AUTH_INVALID"


def test_secret_errone_est_refuse(tenant):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        client.post(
            "/devices", json={"device_id": "cpt01"}, headers=_human_headers(tenant["tenant_id"])
        )
    response = client.post(
        "/devices/auth",
        json={"tenant_id": str(tenant["tenant_id"]), "device_id": "cpt01", "secret": "faux"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "DEVICE_AUTH_INVALID"


def test_appareil_d_un_autre_tenant_est_invisible(tenant):
    autre_tenant = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": autre_tenant, "name": "AutreClient", "slug": f"autre-{autre_tenant}"},
        )
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        created = client.post(
            "/devices", json={"device_id": "cpt01"}, headers=_human_headers(tenant["tenant_id"])
        )
    secret = created.json()["secret"]

    response = client.post(
        "/devices/auth",
        json={"tenant_id": str(autre_tenant), "device_id": "cpt01", "secret": secret},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "DEVICE_AUTH_INVALID"

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": autre_tenant})


def _device_token(tenant):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        created = client.post(
            "/devices", json={"device_id": "cpt01"}, headers=_human_headers(tenant["tenant_id"])
        )
    secret = created.json()["secret"]
    auth = client.post(
        "/devices/auth",
        json={"tenant_id": str(tenant["tenant_id"]), "device_id": "cpt01", "secret": secret},
    )
    return auth.json()["access_token"], created.json()["id"]


def test_ingestion_edge_authentifiee_enregistre_la_mesure(tenant):
    token, device_id = _device_token(tenant)
    response = client.post(
        "/edge/measurements",
        json={
            "items": [
                {
                    "point_id": str(tenant["point_id"]),
                    "value": 1234.5,
                    "measured_at": "2026-09-24T10:00:00Z",
                    "origin": "measured",
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["inserted"] == 1

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        row = (
            connection.execute(
                text("SELECT value, source FROM measurements WHERE point_id = :id"),
                {"id": tenant["point_id"]},
            )
            .mappings()
            .first()
        )
    assert row["value"] == pytest.approx(1234.5)
    assert row["source"] == f"edge:{device_id}"


def test_ingestion_edge_refuse_un_jeton_humain(tenant):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/edge/measurements", json={"items": []}, headers=_human_headers(tenant["tenant_id"])
        )
    assert response.status_code == 401


def test_ingestion_met_a_jour_la_derniere_relève(tenant):
    token, device_id = _device_token(tenant)
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        before = client.get("/devices", headers=_human_headers(tenant["tenant_id"])).json()
        assert before[0]["last_seen_at"] is not None  # déjà mis à jour par /devices/auth

        client.post(
            "/edge/measurements",
            json={
                "items": [
                    {
                        "point_id": str(tenant["point_id"]),
                        "value": 1.0,
                        "measured_at": "2026-09-24T10:00:00Z",
                        "origin": "measured",
                    }
                ]
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        after = client.get("/devices", headers=_human_headers(tenant["tenant_id"])).json()
    assert after[0]["last_seen_at"] >= before[0]["last_seen_at"]


def test_revoquer_puis_authentifier_echoue(tenant):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        created = client.post(
            "/devices", json={"device_id": "cpt01"}, headers=_human_headers(tenant["tenant_id"])
        )
        secret = created.json()["secret"]
        device_id = created.json()["id"]

        revoked = client.post(
            f"/devices/{device_id}/revoke",
            json={"reason": "Appareil perdu"},
            headers=_human_headers(tenant["tenant_id"]),
        )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    auth = client.post(
        "/devices/auth",
        json={"tenant_id": str(tenant["tenant_id"]), "device_id": "cpt01", "secret": secret},
    )
    assert auth.status_code == 401


def test_edge_config_renvoie_la_configuration_active(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        version_id = create_version(
            connection,
            tenant_id=tenant["tenant_id"],
            config_type=MODBUS_DEVICE_MAPPING,
            subject_key=str(tenant["location_id"]),
            content={
                "device_type": "sdm120",
                "host": "192.168.1.50",
                "port": 502,
                "points": [
                    {"point_id": str(tenant["point_id"]), "register_name": "total_active_energy"}
                ],
            },
            author="test",
            reason="test",
        )
        activate_version(connection, version_id=version_id, activated_by="test", activated_at=T0)

    token, _ = _device_token(tenant)
    response = client.get(
        f"/edge/config?equipment_id={tenant['location_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["host"] == "192.168.1.50"


def test_edge_config_sans_configuration_active_renvoie_404(tenant):
    token, _ = _device_token(tenant)
    response = client.get(
        f"/edge/config?equipment_id={uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "MODBUS_MAPPING_NOT_FOUND"


def test_appareil_inconnu_dans_l_ingestion_est_signale_sans_planter(tenant):
    token, _ = _device_token(tenant)
    response = client.post(
        "/edge/measurements",
        json={
            "items": [
                {
                    "point_id": str(uuid.uuid4()),
                    "value": 1.0,
                    "measured_at": "2026-09-24T10:00:00Z",
                    "origin": "measured",
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["rejected"] == 1
    assert response.json()["errors"][0]["code"] == "POINT_NOT_FOUND"


# --- Identité par clé publique (modèle cible, Mohamed 24/09/2026) ---------


def test_provisionner_par_cle_publique_puis_authentifier_par_assertion(tenant):
    private_pem, public_pem = _keypair()
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        created = client.post(
            "/devices",
            json={"device_id": "edge-01", "public_key_pem": public_pem},
            headers=_human_headers(tenant["tenant_id"]),
        )
    assert created.status_code == 201
    body = created.json()
    assert body["secret"] is None  # rien à transmettre, aucune clé privée côté serveur
    assert "PRIVATE KEY" not in created.text

    assertion = _assertion(
        private_pem, device_id="edge-01", tenant_id=tenant["tenant_id"], at=datetime.now(UTC)
    )
    auth = client.post(
        "/devices/auth",
        json={
            "tenant_id": str(tenant["tenant_id"]),
            "device_id": "edge-01",
            "assertion": assertion,
        },
    )
    assert auth.status_code == 200
    assert set(auth.json()["scopes"]) == {"telemetry:write", "config:read", "command:execute"}


def test_creer_un_appareil_avec_une_cle_publique_invalide_est_refuse(tenant):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/devices",
            json={"device_id": "edge-01", "public_key_pem": "pas une clé"},
            headers=_human_headers(tenant["tenant_id"]),
        )
    assert response.status_code == 422
    assert response.json()["code"] == "DEVICE_PUBLIC_KEY_INVALID"


def test_auth_avec_secret_et_assertion_a_la_fois_est_refuse(tenant):
    response = client.post(
        "/devices/auth",
        json={
            "tenant_id": str(tenant["tenant_id"]),
            "device_id": "edge-01",
            "secret": "x",
            "assertion": "y",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_auth_sans_secret_ni_assertion_est_refuse(tenant):
    response = client.post(
        "/devices/auth", json={"tenant_id": str(tenant["tenant_id"]), "device_id": "edge-01"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_assertion_rejouee_est_refusee_via_l_api(tenant):
    private_pem, public_pem = _keypair()
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        client.post(
            "/devices",
            json={"device_id": "edge-01", "public_key_pem": public_pem},
            headers=_human_headers(tenant["tenant_id"]),
        )
    assertion = _assertion(
        private_pem, device_id="edge-01", tenant_id=tenant["tenant_id"], at=datetime.now(UTC)
    )
    body = {"tenant_id": str(tenant["tenant_id"]), "device_id": "edge-01", "assertion": assertion}
    first = client.post("/devices/auth", json=body)
    second = client.post("/devices/auth", json=body)
    assert first.status_code == 200
    assert second.status_code == 401
    assert second.json()["code"] == "DEVICE_AUTH_INVALID"


def test_appareil_revoque_refuse_une_assertion_via_l_api(tenant):
    private_pem, public_pem = _keypair()
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        created = client.post(
            "/devices",
            json={"device_id": "edge-01", "public_key_pem": public_pem},
            headers=_human_headers(tenant["tenant_id"]),
        )
        client.post(
            f"/devices/{created.json()['id']}/revoke",
            json={"reason": "Perdu"},
            headers=_human_headers(tenant["tenant_id"]),
        )
    assertion = _assertion(
        private_pem, device_id="edge-01", tenant_id=tenant["tenant_id"], at=datetime.now(UTC)
    )
    response = client.post(
        "/devices/auth",
        json={
            "tenant_id": str(tenant["tenant_id"]),
            "device_id": "edge-01",
            "assertion": assertion,
        },
    )
    assert response.status_code == 401


def test_migrer_un_appareil_shared_secret_vers_cle_publique_via_l_api(tenant):
    private_pem, public_pem = _keypair()
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        created = client.post(
            "/devices", json={"device_id": "edge-01"}, headers=_human_headers(tenant["tenant_id"])
        )
        secret = created.json()["secret"]
        device_id = created.json()["id"]

        migrated = client.post(
            f"/devices/{device_id}/public-key",
            json={"public_key_pem": public_pem, "reason": "Migration vers clé publique"},
            headers=_human_headers(tenant["tenant_id"]),
        )
    assert migrated.status_code == 200
    assert migrated.json()["credential_type"] == "public_key_assertion"
    assert migrated.json()["key_fingerprint"]

    old_auth = client.post(
        "/devices/auth",
        json={"tenant_id": str(tenant["tenant_id"]), "device_id": "edge-01", "secret": secret},
    )
    assert old_auth.status_code == 401

    assertion = _assertion(
        private_pem, device_id="edge-01", tenant_id=tenant["tenant_id"], at=datetime.now(UTC)
    )
    new_auth = client.post(
        "/devices/auth",
        json={
            "tenant_id": str(tenant["tenant_id"]),
            "device_id": "edge-01",
            "assertion": assertion,
        },
    )
    assert new_auth.status_code == 200


def test_technicien_ne_peut_pas_installer_une_cle_publique(tenant):
    _, public_pem = _keypair()
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        created = client.post(
            "/devices", json={"device_id": "edge-01"}, headers=_human_headers(tenant["tenant_id"])
        )
        response = client.post(
            f"/devices/{created.json()['id']}/public-key",
            json={"public_key_pem": public_pem, "reason": "test"},
            headers=_human_headers(tenant["tenant_id"], ["technicien"]),
        )
    assert response.status_code == 403


def test_installer_une_cle_publique_sur_un_appareil_inconnu_est_refuse(tenant):
    _, public_pem = _keypair()
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            f"/devices/{uuid.uuid4()}/public-key",
            json={"public_key_pem": public_pem, "reason": "test"},
            headers=_human_headers(tenant["tenant_id"]),
        )
    assert response.status_code == 404
    assert response.json()["code"] == "DEVICE_NOT_FOUND"
