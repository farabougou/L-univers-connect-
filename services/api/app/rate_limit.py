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

import ipaddress

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.auth import decode_device_token, decode_token_with_cached_keys
from app.config import settings
from app.errors import ApiError, problem_response


def client_ip(request: Request) -> str:
    """Adresse du client. Par défaut, celle de la connexion (que uvicorn
    remplace par `X-Forwarded-For` pour les proxys de `FORWARDED_ALLOW_IPS`).

    Si `CLIENT_IP_HEADER` est renseigné (Railway : `X-Real-IP`, posé et écrasé
    par son proxy), on lit cet en-tête. Chez l'hébergeur, la connexion vue par
    l'application est celle du proxy : sans cette lecture, tous les clients
    anonymes de la plateforme partageraient UN quota, et n'importe qui pourrait
    l'épuiser pour tous (par exemple celui de `/devices/auth`).

    Ne retenir que ce que l'on peut vérifier : une seule adresse IP valide, sinon
    repli sur la connexion. À n'activer que derrière un proxy qui écrase cet
    en-tête et si le service n'est pas joignable autrement (voir
    infra/RAILWAY_STAGING.md, qui décrit l'essai à faire avant l'activation)."""
    header = settings.client_ip_header.strip()
    if header:
        try:
            return str(ipaddress.ip_address(request.headers.get(header, "").strip()))
        except ValueError:
            pass
    return get_remote_address(request)


def ip_rate_limit_key(request: Request) -> str:
    """Clé par adresse IP, pour les routes ouvertes à tous (avant toute
    authentification) où une identité ne peut pas exister."""
    return client_ip(request)


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


limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["120/minute"],
    storage_uri=settings.rate_limit_storage_uri,
)


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return problem_response(request, status=429, code="RATE_LIMITED")


def install_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
