import time
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JOSEError

from app.config import settings

security = HTTPBearer(auto_error=False)

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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="fournisseur d'authentification indisponible",
        ) from exc

    try:
        return jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
        )
    except JOSEError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="jeton invalide"
        ) from exc


def get_current_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="jeton manquant")
    return decode_token(credentials.credentials)


def require_role(role: str):
    """Dépendance FastAPI : n'autorise que les jetons portant ce rôle."""

    def dependency(
        claims: Annotated[dict[str, Any], Depends(get_current_claims)],
    ) -> dict[str, Any]:
        roles = claims.get("realm_access", {}).get("roles", [])
        if role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="rôle insuffisant")
        return claims

    return dependency


def require_any_role(*allowed_roles: str):
    """Dépendance FastAPI : n'autorise que les jetons portant au moins un de ces rôles."""

    def dependency(
        claims: Annotated[dict[str, Any], Depends(get_current_claims)],
    ) -> dict[str, Any]:
        roles = set(claims.get("realm_access", {}).get("roles", []))
        if roles.isdisjoint(allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="rôle insuffisant")
        return claims

    return dependency
