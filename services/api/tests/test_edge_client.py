"""Client Edge (app/connectors/edge_client.py) : les deux façons de prouver
son identité à /devices/auth (voir app/devices.py pour la vérification
côté serveur)."""

import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jose import jwt

from app.connectors.edge_client import (
    EdgeApiClient,
    PrivateKeyCredential,
    SharedSecretCredential,
)
from app.devices import ASSERTION_ALGORITHM


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
