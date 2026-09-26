import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JOSEError

from app.config import settings
from app.errors import ApiError

security = HTTPBearer(auto_error=False)

# Jetons d'appareil Edge (M4, app/devices.py) : un flux séparé, signé par
# l'API elle-même (HS256, secret local), jamais mélangé au flux humain OIDC
# ci-dessus. Courte durée pour limiter la fenêtre d'un secret compromis ; le
# démon en redemande un avant expiration ou sur un premier refus.
DEVICE_TOKEN_TTL = timedelta(minutes=15)

_JWKS_CACHE_SECONDS = 300
_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}


def _jwks_url() -> str:
    return f"{settings.oidc_issuer}/protocol/openid-connect/certs"


def fetch_jwks() -> dict[str, Any]:
    """Récupère (et met en cache) les clés publiques du fournisseur OIDC."""
    now = time.monotonic()
    is_stale = now - _jwks_cache["fetched_at"] > _JWKS_CACHE_SECONDS
    if _jwks_cache["keys"] is None or is_stale:
        response = httpx.get(_jwks_url(), timeout=5.0)
        response.raise_for_status()
        _jwks_cache["keys"] = response.json()
        _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


def decode_token(token: str) -> dict[str, Any]:
    """Vérifie la signature, l'émetteur, l'audience et l'expiration du jeton.

    Ne jamais lire les informations d'un jeton sans passer par cette
    vérification : un jeton non vérifié ne prouve rien.
    """
    try:
        jwks = fetch_jwks()
    except httpx.HTTPError as exc:
        raise ApiError(503, "AUTH_PROVIDER_UNAVAILABLE") from exc

    try:
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
        )
    except JOSEError as exc:
        raise ApiError(401, "TOKEN_INVALID") from exc


def get_current_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, Any]:
    if credentials is None:
        raise ApiError(401, "TOKEN_MISSING")
    return decode_token(credentials.credentials)


def require_role(role: str):
    """Dépendance FastAPI : n'autorise que les jetons portant ce rôle."""

    def dependency(
        claims: Annotated[dict[str, Any], Depends(get_current_claims)],
    ) -> dict[str, Any]:
        roles = claims.get("realm_access", {}).get("roles", [])
        if role not in roles:
            raise ApiError(403, "ROLE_FORBIDDEN")
        return claims

    return dependency


def require_any_role(*allowed_roles: str):
    """Dépendance FastAPI : n'autorise que les jetons portant au moins un de ces rôles."""

    def dependency(
        claims: Annotated[dict[str, Any], Depends(get_current_claims)],
    ) -> dict[str, Any]:
        roles = set(claims.get("realm_access", {}).get("roles", []))
        if roles.isdisjoint(allowed_roles):
            raise ApiError(403, "ROLE_FORBIDDEN")
        return claims

    return dependency


def issue_device_token(
    *, device_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID | None, scopes: list[str]
) -> str:
    now = datetime.now(UTC)
    claims = {
        "device_id": str(device_id),
        "tenant_id": str(tenant_id),
        "site_id": str(site_id) if site_id else None,
        "scopes": scopes,
        "iat": int(now.timestamp()),
        "exp": int((now + DEVICE_TOKEN_TTL).timestamp()),
    }
    return jwt.encode(claims, settings.device_token_secret, algorithm="HS256")


def decode_device_token(token: str) -> dict[str, Any]:
    """Vérifie la signature et l'expiration d'un jeton d'appareil.

    Algorithme fixé explicitement (HS256) : jamais laisser le jeton dicter
    son propre algorithme de vérification (attaque classique "alg=none")."""
    try:
        return jwt.decode(token, settings.device_token_secret, algorithms=["HS256"])
    except JOSEError as exc:
        raise ApiError(401, "DEVICE_TOKEN_INVALID") from exc


def get_current_device_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, Any]:
    if credentials is None:
        raise ApiError(401, "TOKEN_MISSING")
    return decode_device_token(credentials.credentials)


def require_device_scope(scope: str):
    """Dépendance FastAPI : n'autorise qu'un jeton d'appareil portant cette
    portée précise (ex. "telemetry:write") — jamais un jeton humain."""

    def dependency(
        claims: Annotated[dict[str, Any], Depends(get_current_device_claims)],
    ) -> dict[str, Any]:
        if scope not in claims.get("scopes", []):
            raise ApiError(403, "DEVICE_SCOPE_FORBIDDEN")
        return claims

    return dependency
