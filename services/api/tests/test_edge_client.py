"""Client Edge (app/connectors/edge_client.py) : les deux façons de prouver
son identité à /devices/auth (voir app/devices.py pour la vérification
côté serveur), et sa résilience à la rotation du secret de signature des
jetons d'appareil (V4, priorité « Sécurité » : secrets, rotation)."""

import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jose import jwt
from starlette.testclient import TestClient

from app.config import settings
from app.connectors.edge_client import (
    EdgeApiClient,
    PrivateKeyCredential,
    SharedSecretCredential,
)
from app.devices import ASSERTION_ALGORITHM
from app.main import app
from tests.modbus_fixtures import (
    cleanup_tenant,
    create_tenant_with_energy_point,
    provision_device_for_tenant,
)


def _private_key_pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def test_shared_secret_credential_envoie_le_secret():
    assert SharedSecretCredential("s3cret").auth_payload() == {"secret": "s3cret"}


def test_private_key_credential_signe_une_preuve_verifiable():
    private_pem = _private_key_pem()
    public_pem = (
        serialization.load_pem_private_key(private_pem.encode(), password=None)
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    tenant_id = uuid.uuid4()
    credential = PrivateKeyCredential(
        private_key_pem=private_pem, device_id="edge-01", tenant_id=tenant_id
    )

    payload = credential.auth_payload()

    assert set(payload) == {"assertion"}
    claims = jwt.decode(payload["assertion"], public_pem, algorithms=[ASSERTION_ALGORITHM])
    assert claims["device_id"] == "edge-01"
    assert claims["tenant_id"] == str(tenant_id)
    assert "jti" in claims and "iat" in claims and "exp" in claims


def test_private_key_credential_ne_reutilise_jamais_le_meme_jti():
    credential = PrivateKeyCredential(
        private_key_pem=_private_key_pem(), device_id="edge-01", tenant_id=uuid.uuid4()
    )
    first = jwt.get_unverified_claims(credential.auth_payload()["assertion"])
    second = jwt.get_unverified_claims(credential.auth_payload()["assertion"])
    assert first["jti"] != second["jti"]


def test_edge_api_client_exige_exactement_une_creance():
    with pytest.raises(ValueError):
        EdgeApiClient(client=None, tenant_id=uuid.uuid4(), device_id="edge-01")
    with pytest.raises(ValueError):
        EdgeApiClient(
            client=None,
            tenant_id=uuid.uuid4(),
            device_id="edge-01",
            secret="s",
            credential=SharedSecretCredential("s"),
        )


def test_le_client_se_reauthentifie_seul_apres_rotation_du_secret_de_jeton():
    """Faire tourner `device_token_secret` (la clé qui signe les jetons
    d'appareil, app/config.py) invalide d'un coup tous les jetons déjà
    émis — mais jamais l'identité de l'appareil lui-même (son secret ou sa
    clé privée, vérifiés par /devices/auth, jamais par ce secret-là). Le
    client doit donc absorber la rotation tout seul, sans intervention
    sur site : un 401 inattendu déclenche déjà une seule nouvelle
    authentification (voir EdgeApiClient._authorized_request)."""
    tenant = create_tenant_with_energy_point("ClientEdgeRotation")
    secret = provision_device_for_tenant(tenant_id=tenant["tenant_id"], device_id="edge-rotation")
    original_secret = settings.device_token_secret
    try:
        with EdgeApiClient(
            client=TestClient(app),
            tenant_id=tenant["tenant_id"],
            device_id="edge-rotation",
            secret=secret,
        ) as api:
            assert api.get_config(uuid.uuid4()) is None  # authentifie, met le jeton en cache
            token_before_rotation = api._token

            settings.device_token_secret = "rotated-secret-for-test"

            assert api.get_config(uuid.uuid4()) is None  # 401 sur l'ancien jeton, puis succès
            assert api._token != token_before_rotation
    finally:
        settings.device_token_secret = original_secret
        cleanup_tenant(tenant)
