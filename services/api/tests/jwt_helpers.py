"""Fabrique de jetons JWT signés localement, pour tester la vérification
d'authentification (app.auth) sans dépendre d'un vrai serveur Keycloak."""

import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

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
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_jwk = jwk.construct(public_pem, algorithm="RS256").to_dict()
    public_jwk["kid"] = KEY_ID
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
    return jwt.encode(
        claims, private_key or PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": KEY_ID}
    )
