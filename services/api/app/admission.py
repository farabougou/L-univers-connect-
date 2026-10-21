"""Contrôle d'admission : borne le nombre de requêtes HTTP traitées en même
temps (audit V5 du 20/10/2026).

Pourquoi : la dépendance `get_connection` (app/deps.py) est un générateur
synchrone. Son entrée prend une connexion du pool dans un fil d'exécution, puis
la route attend un autre fil pour s'exécuter, tenant la connexion entre-temps.
Avec plus de requêtes simultanées que de connexions, tous les fils (40 par
défaut) finissent bloqués à attendre une connexion détenue par une requête qui
attend elle-même un fil : plus rien n'avance jusqu'à l'expiration du pool.
Mesuré : 78 requêtes/s à 50 clients simultanés, 5 requêtes/s et des erreurs 500
à 150 clients.

Limiter les requêtes en cours à la capacité du pool garantit qu'aucune requête
n'attend une connexion : l'interblocage devient impossible. Les requêtes en
trop patientent un court instant puis reçoivent un 503 explicite avec
`Retry-After` (les clients Edge réessayent déjà) plutôt qu'une erreur 500 ou
une attente sans fin.

Chaque processus a sa propre limite et son propre pool : avec plusieurs
processus (`WEB_CONCURRENCY`), le total de connexions est celui d'un processus
multiplié par leur nombre (voir infra/RAILWAY_STAGING.md).
"""

import asyncio

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.errors import problem_response

RETRY_AFTER_SECONDS = 2


class AdmissionControlMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        max_in_flight: int,
        queue_timeout_seconds: float,
        exempt_paths: frozenset[str] = frozenset(),
    ) -> None:
        self.app = app
        self._slots = asyncio.Semaphore(max_in_flight)
        self._queue_timeout = queue_timeout_seconds
        self._exempt_paths = exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self._exempt_paths:
            await self.app(scope, receive, send)
            return

        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=self._queue_timeout)
        except TimeoutError:
            response = problem_response(
                Request(scope, receive), status=503, code="SERVICE_BUSY"
            )
            response.headers["Retry-After"] = str(RETRY_AFTER_SECONDS)
            await response(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        finally:
            self._slots.release()
