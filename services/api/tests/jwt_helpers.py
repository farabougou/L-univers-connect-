"""Fabrique de jetons JWT signés localement, pour tester la vérification
d'authentification (app.auth) sans dépendre d'un vrai serveur Keycloak."""

import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import settings

KEY_ID = "test-key"
DEMO_TENANT_ID = "11111111-1111-1111-1111-111111111111"


def generate_keypair() -> tuple[bytes, dict]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk.update({"kid": KEY_ID, "use": "sig", "alg": "RS256"})
    return private_pem, {"keys": [public_jwk]}


PRIVATE_KEY_PEM, JWKS = generate_keypair()


def make_token(
    *,
    roles: list[str] | None = None,
    tenant_id: str | None = DEMO_TENANT_ID,
    audience: str | None = None,
    expired: bool = False,
    private_key: bytes | None = None,
    sub: str = "technicien-test",
    username: object = None,
) -> str:
    now = int(time.time())
    claims = {
        "sub": sub,
        "iss": settings.oidc_issuer,
        "aud": audience or settings.oidc_audience,
        "iat": now,
        "exp": now - 10 if expired else now + 300,
        "realm_access": {"roles": roles or ["technicien"]},
        "tenant_id": tenant_id,
    }
    if username is not None:
        claims["preferred_username"] = username
    return jwt.encode(
        claims, private_key or PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": KEY_ID}
    )
