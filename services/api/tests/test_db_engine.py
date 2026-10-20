"""app/db.py : le pool de connexions Postgres (audit V5 du 20/10/2026).

Sur Railway, une connexion peut être coupée côté Postgres (redémarrage,
bascule, proxy réseau qui ferme les connexions inactives). Sans
`pool_pre_ping`, la première requête qui retombe sur cette connexion devient
une erreur 500. Ces tests prouvent le comportement sur une vraie base :
connexion réellement terminée par `pg_terminate_backend`, puis reprise
transparente — avec un témoin négatif (moteur sans pré-vérification) pour
montrer que le test détecte bien le défaut.
"""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.db import build_engine, engine
from app.tenancy import set_tenant_context


def _backend_pid(candidate) -> int:
    with candidate.connect() as connection:
        return connection.execute(text("SELECT pg_backend_pid()")).scalar_one()


def _terminate(pid: int) -> None:
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})


def test_une_connexion_coupee_cote_postgres_est_remplacee_sans_erreur() -> None:
    candidate = build_engine(settings.database_url)
    try:
        pid = _backend_pid(candidate)
        _terminate(pid)

        with candidate.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
            new_pid = connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
        assert new_pid != pid
    finally:
        candidate.dispose()


def test_temoin_negatif_sans_pre_ping_la_connexion_coupee_provoque_une_erreur() -> None:
    """Sans `pool_pre_ping`, la même coupure fait échouer la requête : le test
    précédent mesure donc bien l'effet de la correction, pas un hasard."""
    candidate = create_engine(settings.database_url, pool_size=1)
    try:
        pid = _backend_pid(candidate)
        _terminate(pid)

        with pytest.raises(OperationalError), candidate.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        candidate.dispose()


def test_le_pool_applique_les_limites_configurees() -> None:
    candidate = build_engine(settings.database_url)
    try:
        assert candidate.pool.size() == settings.db_pool_size
        assert candidate.pool._max_overflow == settings.db_max_overflow
    finally:
        candidate.dispose()


def test_le_contexte_tenant_ne_survit_pas_a_la_transaction_meme_avec_un_pool() -> None:
    """Isolation (règle non négociable 2) : une connexion du pool réutilisée
    par une autre requête ne doit jamais hériter du tenant précédent."""
    candidate = build_engine(settings.database_url)
    try:
        with candidate.begin() as connection:
            set_tenant_context(connection, uuid.uuid4())
            assert connection.execute(
                text("SELECT current_setting('app.current_tenant_id', true)")
            ).scalar_one()
        first_pid = _backend_pid(candidate)

        with candidate.begin() as connection:
            assert connection.execute(text("SELECT pg_backend_pid()")).scalar_one() == first_pid
            leftover = connection.execute(
                text("SELECT current_setting('app.current_tenant_id', true)")
            ).scalar_one()
        assert leftover in (None, "")
    finally:
        candidate.dispose()
