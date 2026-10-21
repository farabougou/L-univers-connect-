"""Cohérence de la capacité déclarée (app/capacity.py, consolidation V5 du
21/10/2026) : requêtes en cours, pool, connexions PostgreSQL, quotas de débit."""

import logging

import pytest
from sqlalchemy import create_engine

from app.capacity import (
    CONNECTION_RESERVE,
    effective_max_in_flight,
    evaluate_capacity,
    pool_capacity,
    read_max_connections,
    report_capacity,
    worker_count,
)
from app.config import Settings
from app.db import engine


def _settings(**overrides) -> Settings:
    base = {
        "db_pool_size": 10,
        "db_max_overflow": 20,
        "max_in_flight_requests": 0,
        "expected_replicas": 1,
        "rate_limit_storage_uri": "memory://",
    }
    return Settings(**{**base, **overrides})


def _codes(findings) -> set[str]:
    return {finding.code for finding in findings}


# --- Requêtes en cours <-> pool ---------------------------------------


def test_par_defaut_les_requetes_en_cours_valent_la_capacite_du_pool() -> None:
    settings = _settings()

    assert pool_capacity(settings) == 30
    assert effective_max_in_flight(settings) == 30


def test_on_peut_abaisser_les_requetes_en_cours_sous_la_capacite_du_pool() -> None:
    assert effective_max_in_flight(_settings(max_in_flight_requests=12)) == 12


def test_une_valeur_au_dessus_du_pool_est_ramenee_a_la_capacite_du_pool() -> None:
    """Au-dessus du pool, on retrouve l'interblocage mesuré à 150 clients."""
    settings = _settings(max_in_flight_requests=100)

    assert effective_max_in_flight(settings) == 30
    findings = evaluate_capacity(settings, max_connections=100, workers=1)
    assert "ADMISSION_ABOVE_POOL" in _codes(findings)


def test_une_configuration_coherente_ne_signale_rien() -> None:
    assert evaluate_capacity(_settings(), max_connections=100, workers=1) == []


# --- Connexions PostgreSQL ---------------------------------------------


def test_le_total_des_connexions_de_toutes_les_instances_doit_tenir_dans_postgres() -> None:
    # 30 connexions x 4 processus = 120 > 100 - 10.
    findings = evaluate_capacity(_settings(), max_connections=100, workers=4)

    (finding,) = [f for f in findings if f.code == "CONNECTIONS_OVER_BUDGET"]
    assert finding.detail["required"] == 120
    assert finding.detail["available"] == 100 - CONNECTION_RESERVE


def test_les_repliques_comptent_comme_des_processus() -> None:
    findings = evaluate_capacity(_settings(expected_replicas=4), max_connections=100, workers=1)

    assert "CONNECTIONS_OVER_BUDGET" in _codes(findings)


def test_exactement_a_la_limite_du_budget_est_accepte() -> None:
    # 3 instances x 30 = 90 = 100 - 10.
    findings = evaluate_capacity(_settings(expected_replicas=3), max_connections=100, workers=1)

    assert "CONNECTIONS_OVER_BUDGET" not in _codes(findings)


def test_sans_valeur_lue_sur_la_base_le_budget_n_est_pas_evalue() -> None:
    findings = evaluate_capacity(_settings(expected_replicas=50), max_connections=None, workers=1)

    assert "CONNECTIONS_OVER_BUDGET" not in _codes(findings)


# --- Quotas de débit ----------------------------------------------------


def test_des_quotas_en_memoire_ne_sont_exacts_qu_avec_une_seule_instance() -> None:
    assert "RATE_LIMIT_NOT_SHARED" not in _codes(
        evaluate_capacity(_settings(), max_connections=100, workers=1)
    )
    assert "RATE_LIMIT_NOT_SHARED" in _codes(
        evaluate_capacity(_settings(), max_connections=100, workers=2)
    )
    assert "RATE_LIMIT_NOT_SHARED" in _codes(
        evaluate_capacity(_settings(expected_replicas=2), max_connections=100, workers=1)
    )


def test_un_stockage_partage_leve_l_avertissement() -> None:
    settings = _settings(expected_replicas=2, rate_limit_storage_uri="redis://cache:6379")

    assert "RATE_LIMIT_NOT_SHARED" not in _codes(
        evaluate_capacity(settings, max_connections=100, workers=1)
    )


# --- Nombre de processus -------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 1), ("", 1), ("4", 4), ("0", 1), ("-2", 1), ("beaucoup", 1)],
)
def test_le_nombre_de_processus_suit_web_concurrency(value, expected) -> None:
    environ = {} if value is None else {"WEB_CONCURRENCY": value}

    assert worker_count(environ) == expected


# --- Lecture sur la vraie base et journal -----------------------------


def test_lit_les_connexions_autorisees_sur_la_vraie_base() -> None:
    assert read_max_connections(engine) >= 10


def test_une_base_injoignable_ne_fait_pas_echouer_la_lecture() -> None:
    unreachable = create_engine(
        "postgresql+psycopg://x:y@127.0.0.1:1/none", connect_args={"connect_timeout": 1}
    )

    assert read_max_connections(unreachable) is None


def test_le_demarrage_journalise_la_configuration_reelle(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="paios.capacity"):
        report_capacity(engine, _settings())

    checked = [r for r in caplog.records if getattr(r, "event", "") == "capacity.checked"]
    assert len(checked) == 1
    detail = checked[0].detail
    assert detail["pool_capacity"] == 30
    assert detail["max_in_flight"] == 30
    assert detail["max_connections"] >= 10
    assert detail["rate_limit_storage"] == "memory"


def test_un_incoherence_est_journalisee_en_avertissement(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="paios.capacity"):
        report_capacity(engine, _settings(max_in_flight_requests=100))

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert [getattr(r, "event", "") for r in warnings] == ["capacity.admission_above_pool"]


def test_la_verification_ne_leve_jamais(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("panne")

    monkeypatch.setattr("app.capacity.read_max_connections", boom)

    assert report_capacity(engine, _settings()) == []
