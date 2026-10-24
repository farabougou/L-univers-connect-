import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import (
    InvalidAudienceError,
    InvalidIssuedAtError,
    InvalidSignatureError,
    InvalidTokenError,
    PyJWTError,
)

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
        return _verify_oidc_token(token, jwks)
    except PyJWTError as exc:
        raise ApiError(401, "TOKEN_INVALID") from exc


# Algorithme du fournisseur d'identité : fixé ici, jamais lu dans le jeton (voir
# tests/test_token_algorithm_confusion.py).
OIDC_ALGORITHMS = ["RS256"]


def _signing_keys(token: str, jwks: dict[str, Any]) -> list[Any]:
    """Clés publiques du JWKS qui peuvent avoir signé ce jeton : celle de son `kid`, ou
    toutes les clés de signature si le jeton n'en annonce pas. Les clés de chiffrement
    (`use: enc`) ne servent jamais à vérifier une signature."""
    if not isinstance(jwks, dict):
        raise InvalidTokenError("JWKS illisible")
    try:
        key_set = jwt.PyJWKSet.from_dict(jwks)
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        # PyJWT laisse parfois passer l'erreur brute d'une clé mal formée (ex. « oct » sans « k »)
        raise InvalidTokenError("JWKS illisible") from exc
    kid = jwt.get_unverified_header(token).get("kid")
    keys = [
        key.key
        for key in key_set.keys
        if key.public_key_use in (None, "sig") and (kid is None or key.key_id == kid)
    ]
    if not keys:
        raise InvalidTokenError("aucune clé de signature correspondante")
    return keys


def _check_issued_at_format(claims: dict[str, Any]) -> None:
    """`iat`, s'il existe, doit être un nombre. Seul le format est contrôlé, comme avec
    python-jose : l'heure d'émission n'est jamais comparée à l'horloge du serveur, car
    deux machines (Keycloak, API) ont presque toujours quelques secondes d'écart."""
    if "iat" in claims:
        try:
            int(claims["iat"])
        except (TypeError, ValueError):
            raise InvalidIssuedAtError("Issued At claim (iat) must be an integer.") from None


def _check_audience(claims: dict[str, Any]) -> None:
    """Contrôle l'audience **quand le jeton en porte une**.

    Comportement hérité de python-jose, conservé volontairement : les jetons réels de
    Keycloak (realm-export.json) n'ont aucune revendication `aud` (constaté le
    21/10/2026 sur le staging : `aud` absent, `azp` = paios-api). Exiger `aud` comme le
    fait PyJWT par défaut mettrait toute l'authentification en échec. Le contrôle ne
    devient effectif qu'avec un mapper d'audience dans le royaume (voir
    docs/security/registre-vulnerabilites.md, « Audience »)."""
    if "aud" not in claims:
        return
    audience = claims["aud"]
    if isinstance(audience, str):
        accepted = audience == settings.oidc_audience
    elif isinstance(audience, list) and all(isinstance(item, str) for item in audience):
        accepted = settings.oidc_audience in audience
    else:
        raise InvalidAudienceError("Invalid claim format in token")
    if not accepted:
        raise InvalidAudienceError("Invalid audience")


def _verify_oidc_token(token: str, jwks: dict[str, Any]) -> dict[str, Any]:
    """Signature (RS256 uniquement), émetteur, expiration — `exp` et `iss` obligatoires —,
    audience si présente. Un jeton dont la signature ne correspond à aucune clé candidate
    est refusé ; toute autre erreur (expiré, mauvais émetteur) l'est dès la première clé
    dont la signature est valide."""
    last_error: PyJWTError = InvalidSignatureError("Signature verification failed")
    for key in _signing_keys(token, jwks):
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=OIDC_ALGORITHMS,
                issuer=settings.oidc_issuer,
                options={"require": ["exp", "iss"], "verify_aud": False, "verify_iat": False},
            )
        except InvalidSignatureError as exc:
            last_error = exc
            continue
        _check_issued_at_format(claims)
        _check_audience(claims)
        return claims
    raise last_error


def decode_token_with_cached_keys(token: str) -> dict[str, Any] | None:
    """Même vérification que `decode_token`, mais uniquement avec les clés
    déjà en cache : aucun appel réseau, aucune exception.

    Réservé à la limitation de débit (app/rate_limit.py), qui s'exécute dans
    le middleware, sur la boucle d'événements : un appel bloquant vers le
    fournisseur OIDC (indisponible, délai dépassé) y gèlerait toutes les
    requêtes. Renvoie None si le jeton n'est pas vérifiable (cache encore
    vide, signature invalide, expiré) : l'appelant se rabat alors sur
    l'adresse IP. Ne sert jamais à autoriser quoi que ce soit."""
    keys = _jwks_cache["keys"]
    if keys is None:
        return None
    try:
        return _verify_oidc_token(token, keys)
    except (PyJWTError, ValueError, KeyError, TypeError):
        # « aucune exception » : un JWKS ou un jeton malformé ne doit jamais devenir une 500
        # dans le middleware de limitation de débit.
        return None


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
        claims = jwt.decode(
            token,
            settings.device_token_secret,
            algorithms=["HS256"],
            options={"require": ["exp"], "verify_iat": False},
        )
        _check_issued_at_format(claims)
        return claims
    except PyJWTError as exc:
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
