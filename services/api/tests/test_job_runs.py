"""État des tâches planifiées (app/job_runs.py, V4, priorité « Déploiement » :
observabilité). Donnée de plateforme, jamais une donnée métier d'un
tenant — pas de contexte RLS à poser, même raisonnement que pour
`tenants` elle-même."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db import engine
from app.job_runs import latest_job_runs, record_job_run, run_and_record

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def job_name() -> str:
    # Un nom unique par test : les lignes ne sont jamais nettoyées par
    # ailleurs (insertion seulement, voir la migration), donc chaque test
    # doit pouvoir distinguer les siennes de celles d'un autre test ou
    # d'un vrai balayage exécuté en parallèle.
    return f"test_job_{uuid.uuid4().hex}"


def test_record_puis_lire_le_dernier_tour(job_name: str) -> None:
    with engine.begin() as connection:
        record_job_run(
            connection,
            job_name=job_name,
            started_at=T0,
            finished_at=T0 + timedelta(seconds=2),
            succeeded=True,
            summary={"tenants_ok": 3},
        )
    with engine.connect() as connection:
        runs = {run["job_name"]: run for run in latest_job_runs(connection)}
    assert runs[job_name]["succeeded"] is True
    assert runs[job_name]["summary"] == {"tenants_ok": 3}
    assert runs[job_name]["error"] is None


def test_latest_job_runs_ne_renvoie_que_le_plus_recent_par_tache(job_name: str) -> None:
    with engine.begin() as connection:
        record_job_run(
            connection,
            job_name=job_name,
            started_at=T0,
            finished_at=T0 + timedelta(seconds=1),
            succeeded=False,
            summary={},
            error="ancien échec",
        )
        record_job_run(
            connection,
            job_name=job_name,
            started_at=T0 + timedelta(minutes=1),
            finished_at=T0 + timedelta(minutes=1, seconds=1),
            succeeded=True,
            summary={"tenants_ok": 1},
        )
    with engine.connect() as connection:
        runs = [run for run in latest_job_runs(connection) if run["job_name"] == job_name]
    assert len(runs) == 1
    assert runs[0]["succeeded"] is True
    assert runs[0]["error"] is None


def test_run_and_record_enregistre_le_succes(job_name: str) -> None:
    summary = run_and_record(engine, job_name=job_name, run_once=lambda: {"ok": 1})
    assert summary == {"ok": 1}

    with engine.connect() as connection:
        runs = {run["job_name"]: run for run in latest_job_runs(connection)}
    assert runs[job_name]["succeeded"] is True
    assert runs[job_name]["summary"] == {"ok": 1}


def test_run_and_record_enregistre_l_echec_puis_relaie_l_exception(job_name: str) -> None:
    def _echoue() -> dict:
        raise RuntimeError("panne simulée")

    with pytest.raises(RuntimeError, match="panne simulée"):
        run_and_record(engine, job_name=job_name, run_once=_echoue)

    with engine.connect() as connection:
        runs = {run["job_name"]: run for run in latest_job_runs(connection)}
    assert runs[job_name]["succeeded"] is False
    assert runs[job_name]["error"] == "panne simulée"


@pytest.fixture(autouse=True)
def _cleanup(job_name: str):
    yield
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM scheduled_job_runs WHERE job_name = :job_name"),
            {"job_name": job_name},
        )
