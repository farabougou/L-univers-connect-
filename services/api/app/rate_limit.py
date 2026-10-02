"""Limitation de débit (slowapi) — défense en profondeur, pas la seule
protection : l'authentification d'appareil (app/devices.py) compare déjà les
secrets en temps constant avec une entropie de 256 bits. Sans limitation de
débit, rien n'empêche un nombre illimité de tentatives par minute contre
`/devices/auth` ou un usage abusif d'endpoints coûteux (recherche, export
PDF) — trouvé par l'audit sécurité du 02/10/2026, absent jusqu'ici.

Clé de limitation par adresse IP : ce service est appelé par des appareils
Edge et le proxy serveur du web/mobile (jamais directement par un
navigateur, voir l'absence volontaire de CORS dans app/main.py), donc l'IP
identifie correctement l'appelant réel.
"""

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.errors import problem_response

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return problem_response(request, status=429, code="RATE_LIMITED")


def install_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
