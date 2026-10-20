"""Limitation de débit (slowapi) — défense en profondeur, pas la seule
protection : l'authentification d'appareil (app/devices.py) compare déjà les
secrets en temps constant avec une entropie de 256 bits. Sans limitation de
débit, rien n'empêche un nombre illimité de tentatives par minute contre
`/devices/auth` ou un usage abusif d'endpoints coûteux (recherche, export
PDF) — trouvé par l'audit sécurité du 02/10/2026, absent jusqu'ici.

Clé de limitation : l'identité vérifiée de l'appelant (appareil Edge ou
personne), à défaut son adresse IP. Audit V5 du 20/10/2026 : la clé par
adresse IP seule était fausse pour le trafic web — le serveur Next.js appelle
l'API au nom de toutes les personnes connectées (voir apps/web/src/lib/api.ts)
et sans transmettre leur adresse, donc tous les utilisateurs de tous les
clients partageaient un unique quota de 120 requêtes par minute.

Une identité n'est retenue que si le jeton est réellement vérifié (signature,
émetteur, audience, expiration) : un jeton falsifié retombe sur le quota de
l'adresse IP et n'ouvre jamais un quota neuf. Pour les requêtes sans jeton, la
clé reste l'adresse IP du client ; derrière un proxy inverse, uvicorn ne la
lit dans `X-Forwarded-For` que pour les proxys déclarés par
`FORWARDED_ALLOW_IPS` (voir infra/RAILWAY_STAGING.md) — sans cette
déclaration, toutes les requêtes anonymes partagent l'adresse du proxy.
"""

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.auth import decode_device_token, decode_token_with_cached_keys
from app.errors import ApiError, problem_response


def ip_rate_limit_key(request: Request) -> str:
    """Clé par adresse IP, pour les routes ouvertes à tous (avant toute
    authentification) où une identité ne peut pas exister."""
    return get_remote_address(request)


def _bearer_token(request: Request) -> str | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    token = token.strip()
    return token if scheme.lower() == "bearer" and token else None


def rate_limit_key(request: Request) -> str:
    token = _bearer_token(request)
    if token:
        try:
            device_id = decode_device_token(token).get("device_id")
        except ApiError:
            device_id = None
        if device_id:
            return f"device:{device_id}"

        claims = decode_token_with_cached_keys(token)
        if claims and claims.get("sub"):
            return f"user:{claims['sub']}"

    return f"ip:{ip_rate_limit_key(request)}"


limiter = Limiter(key_func=rate_limit_key, default_limits=["120/minute"])


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return problem_response(request, status=429, code="RATE_LIMITED")


def install_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
