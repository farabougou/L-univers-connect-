"""Confusion d'algorithme sur les jetons (avis CVE-2026-85394 / PYSEC-2026-4298,
python-jose 3.5.0, sans correctif publié au 21/10/2026).

L'avis : python-jose accepte, comme clé HMAC, une clé publique asymétrique en
DER ; qui détient la clé publique du service peut alors forger un jeton HS256
accepté « quand les algorithmes ne sont pas explicitement restreints ».

Notre code restreint toujours les algorithmes (RS256 pour le fournisseur
d'identité, HS256 pour les jetons d'appareil, avec un secret et non une clé
publique). Ces tests le prouvent par l'attaque elle-même, pour que la
protection ne disparaisse pas lors d'une évolution : la clé publique sert ici
de secret HMAC sous toutes ses formes (PEM, DER, composantes JWK).
"""

import base64
import hashlib
import hmac
import json
import time
import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from jwt.exceptions import PyJWTError

from app import auth
from app.config import settings
from app.errors import ApiError
from tests.jwt_helpers import JWKS, KEY_ID, PRIVATE_KEY_PEM, make_token


def _b64(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _claims() -> dict:
    now = int(time.time())
    return {
        "sub": "attaquant",
        "iss": settings.oidc_issuer,
        "aud": settings.oidc_audience,
        "iat": now,
        "exp": now + 300,
        "realm_access": {"roles": ["admin_tenant"]},
        "tenant_id": "11111111-1111-1111-1111-111111111111",
    }


def _forge_hs256(secret: bytes, claims: dict | None = None) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KEY_ID}).encode())
    payload = _b64(json.dumps(claims or _claims()).encode())
    signing_input = header + b"." + payload
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return (signing_input + b"." + _b64(signature)).decode()


def _public_key_forms() -> dict[str, bytes]:
    private_key = serialization.load_pem_private_key(PRIVATE_KEY_PEM, password=None)
    public_key = private_key.public_key()
    spki_der = public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pkcs1_der = public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.PKCS1
    )
    return {
        "PEM": public_key.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ),
        "DER SPKI": spki_der,
        "DER PKCS1": pkcs1_der,
        "modulus JWK": JWKS["keys"][0]["n"].encode(),
    }


@pytest.mark.parametrize("form", list(_public_key_forms()))
def test_un_jeton_hs256_forge_avec_la_cle_publique_est_refuse_par_le_chemin_oidc(
    form: str,
) -> None:
    forged = _forge_hs256(_public_key_forms()[form])

    with pytest.raises(PyJWTError):
        auth._verify_oidc_token(forged, JWKS)


def test_le_jeton_legitime_passe_toujours_le_chemin_oidc() -> None:
    """Témoin : sans lui, les refus ci-dessus pourraient venir d'un jeton mal formé."""
    claims = auth._verify_oidc_token(make_token(sub="technicien-test"), JWKS)

    assert claims["sub"] == "technicien-test"


def test_un_jeton_sans_signature_est_refuse_par_le_chemin_oidc() -> None:
    header = _b64(json.dumps({"alg": "none", "typ": "JWT", "kid": KEY_ID}).encode())
    payload = _b64(json.dumps(_claims()).encode())
    unsigned = (header + b"." + payload + b".").decode()

    with pytest.raises(PyJWTError):
        auth._verify_oidc_token(unsigned, JWKS)


def test_decode_token_renvoie_401_pour_un_jeton_forge(monkeypatch) -> None:
    monkeypatch.setattr(auth, "fetch_jwks", lambda: JWKS)
    forged = _forge_hs256(_public_key_forms()["DER SPKI"])

    with pytest.raises(ApiError) as excinfo:
        auth.decode_token(forged)

    assert excinfo.value.status == 401


def test_un_jeton_oidc_rs256_n_ouvre_pas_le_chemin_des_appareils() -> None:
    with pytest.raises(ApiError) as excinfo:
        auth.decode_device_token(make_token())

    assert excinfo.value.status == 401


def test_un_jeton_d_appareil_n_ouvre_pas_le_chemin_oidc() -> None:
    device_token = auth.issue_device_token(
        device_id=uuid.uuid4(),
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        site_id=None,
        scopes=["telemetry:write"],
    )

    with pytest.raises(PyJWTError):
        auth._verify_oidc_token(device_token, JWKS)


def test_un_jeton_d_appareil_signe_avec_un_autre_secret_est_refuse() -> None:
    forged = _forge_hs256(
        b"un-autre-secret", claims={"device_id": "x", "exp": int(time.time()) + 60}
    )

    with pytest.raises(ApiError) as excinfo:
        auth.decode_device_token(forged)

    assert excinfo.value.status == 401
