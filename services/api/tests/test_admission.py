"""Contrôle d'admission (app/admission.py, audit V5 du 20/10/2026).

Constat mesuré sur l'API réelle (un processus uvicorn, base de 800 000 lignes) :
jusqu'à 50 clients simultanés, 78 requêtes/s ; à 150 clients simultanés, 5
requêtes/s et des erreurs 500 `TimeoutError`.

Cause : un interblocage entre le pool de fils d'exécution (40 par défaut) et le
pool de connexions (30). La dépendance `get_connection` est un générateur
synchrone : son entrée prend une connexion dans un fil, puis la route attend un
AUTRE fil pour s'exécuter. Quand tous les fils sont bloqués à attendre une
connexion, les requêtes qui en tiennent une n'obtiennent jamais de fil pour
finir et la libérer : tout attend jusqu'à l'expiration du pool.

Ces tests reproduisent le mécanisme sans base (un petit pool de verrous et peu
de fils) et prouvent que limiter les requêtes en cours à la taille du pool
l'empêche — avec un témoin négatif : sans la limite, la même charge se bloque.
"""

import asyncio
import threading
import time
from collections.abc import Iterator
from typing import Annotated

import anyio
import httpx
import pytest
from fastapi import Depends, FastAPI

from app.admission import AdmissionControlMiddleware

POOL_SIZE = 2
THREADS = 4
ACQUIRE_TIMEOUT = 1.0
CLIENTS = 12


def _build_app(*, admission: bool, queue_timeout: float = 5.0, work_seconds: float = 0.05):
    pool = threading.BoundedSemaphore(POOL_SIZE)
    app = FastAPI()

    def get_connection() -> Iterator[None]:
        # Même forme que app.deps.get_connection : un générateur synchrone qui
        # tient une ressource du pool pendant toute la durée de la route.
        if not pool.acquire(timeout=ACQUIRE_TIMEOUT):
            raise TimeoutError("pool de connexions épuisé")
        try:
            yield None
        finally:
            pool.release()

    @app.get("/work")
    def work(_connection: Annotated[None, Depends(get_connection)]) -> dict:
        time.sleep(work_seconds)
        return {"ok": True}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    if admission:
        app.add_middleware(
            AdmissionControlMiddleware,
            max_in_flight=POOL_SIZE,
            queue_timeout_seconds=queue_timeout,
            exempt_paths=frozenset({"/health"}),
        )
    return app


async def _fire(app: FastAPI, path: str = "/work", clients: int = CLIENTS):
    anyio.to_thread.current_default_thread_limiter().total_tokens = THREADS
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=30) as client:
        started = time.perf_counter()
        responses = await asyncio.gather(*(client.get(path) for _ in range(clients)))
        return [r.status_code for r in responses], time.perf_counter() - started


def test_temoin_negatif_sans_controle_la_meme_charge_se_bloque() -> None:
    """Plus de fils que de connexions, plus de clients que de fils : les fils se
    bloquent tous à attendre une connexion détenue par une requête sans fil."""
    statuses, elapsed = asyncio.run(_fire(_build_app(admission=False)))

    assert 500 in statuses, f"interblocage non reproduit : {statuses}"
    assert elapsed >= ACQUIRE_TIMEOUT * 0.9


def test_avec_le_controle_toutes_les_requetes_aboutissent_sans_attendre_le_pool() -> None:
    statuses, elapsed = asyncio.run(_fire(_build_app(admission=True)))

    assert statuses == [200] * CLIENTS
    assert elapsed < ACQUIRE_TIMEOUT


def test_une_file_d_attente_trop_longue_est_refusee_proprement_en_503() -> None:
    """Au-delà du délai d'attente : un refus explicite et réessayable, jamais une
    erreur 500 ni une attente sans fin."""
    app = _build_app(admission=True, queue_timeout=0.05, work_seconds=0.4)

    async def scenario():
        anyio.to_thread.current_default_thread_limiter().total_tokens = THREADS
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await asyncio.gather(*(client.get("/work") for _ in range(6)))

    responses = asyncio.run(scenario())
    refused = [r for r in responses if r.status_code == 503]

    assert len(refused) == 4
    assert {r.status_code for r in responses} == {200, 503}
    body = refused[0].json()
    assert body["code"] == "SERVICE_BUSY"
    assert refused[0].headers["retry-after"] == "2"


def test_la_sonde_de_sante_n_attend_jamais_derriere_les_autres_requetes() -> None:
    app = _build_app(admission=True, queue_timeout=0.05, work_seconds=0.4)

    async def scenario():
        anyio.to_thread.current_default_thread_limiter().total_tokens = THREADS
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            busy = [asyncio.create_task(client.get("/work")) for _ in range(6)]
            await asyncio.sleep(0.05)
            health = await client.get("/health")
            await asyncio.gather(*busy)
            return health

    assert asyncio.run(scenario()).status_code == 200


@pytest.mark.parametrize("scope_type", ["websocket", "lifespan"])
def test_les_connexions_non_http_ne_sont_pas_comptees(scope_type) -> None:
    """Seules les requêtes HTTP consomment une place."""
    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["type"])

    middleware = AdmissionControlMiddleware(
        inner, max_in_flight=1, queue_timeout_seconds=0.01, exempt_paths=frozenset()
    )
    asyncio.run(middleware({"type": scope_type, "path": "/x"}, None, None))

    assert seen == [scope_type]


def test_un_pool_de_connexions_epuise_donne_un_503_reessayable_pas_une_erreur_500() -> None:
    """Filet de sécurité : si une attente de connexion expire malgré le contrôle
    (plusieurs processus sur une même base, scripts), la personne reçoit un refus
    explicite et réessayable plutôt qu'une « erreur non gérée »."""
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import TimeoutError as PoolTimeoutError

    from app.errors import install_error_handlers

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise PoolTimeoutError("QueuePool limit of size 10 overflow 20 reached")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_BUSY"
    assert response.headers["retry-after"] == "2"
