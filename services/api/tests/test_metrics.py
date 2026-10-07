"""Métriques HTTP et tâches planifiées (app/metrics.py,
feature-benchmark-matrix.md, ligne « Observabilité ») : agrégats seulement,
jamais de donnée métier ni par tenant."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.job_runs import record_job_run
from app.main import app
from app.metrics import REGISTRY

client = TestClient(app)


def _sample(name: str, labels: dict[str, str]) -> float:
    for family in REGISTRY.collect():
        for sample in family.samples:
            if sample.name == name and all(
                sample.labels.get(key) == value for key, value in labels.items()
            ):
                return sample.value
    return 0.0


def test_metrics_endpoint_exposes_prometheus_format() -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "paios_http_requests_total" in response.text
    assert "paios_http_request_duration_seconds" in response.text


def test_a_request_increments_its_counter_and_histogram() -> None:
    labels = {"method": "GET", "route": "/health", "status": "200"}
    before_count = _sample("paios_http_requests_total", labels)
    before_observations = _sample(
        "paios_http_request_duration_seconds_count", {"method": "GET", "route": "/health"}
    )

    response = client.get("/health")
    assert response.status_code == 200

    after_count = _sample("paios_http_requests_total", labels)
    after_observations = _sample(
        "paios_http_request_duration_seconds_count", {"method": "GET", "route": "/health"}
    )
    assert after_count == before_count + 1
    assert after_observations == before_observations + 1


def test_metrics_never_expose_tenant_or_business_data() -> None:
    response = client.get("/metrics")

    body = response.text
    assert "tenant" not in body.lower()


def test_metrics_reflete_le_dernier_tour_connu_d_une_tache() -> None:
    """V4 (priorité « Déploiement ») : /metrics est la seule trace
    exploitable d'un tour exécuté dans un autre processus (le script
    --once d'une tâche planifiée externe, voir app/job_runs.py)."""
    job_name = f"test_job_{uuid.uuid4().hex}"
    started_at = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
    finished_at = started_at + timedelta(seconds=5)
    with engine.begin() as connection:
        record_job_run(
            connection,
            job_name=job_name,
            started_at=started_at,
            finished_at=finished_at,
            succeeded=True,
            summary={"tenants_ok": 1},
        )
    try:
        response = client.get("/metrics")
        assert response.status_code == 200
        labels = {"job": job_name}
        assert _sample("paios_job_last_run_success", labels) == 1.0
        assert _sample("paios_job_last_run_duration_seconds", labels) == 5.0
        assert _sample("paios_job_last_run_timestamp_seconds", labels) == pytest.approx(
            finished_at.timestamp()
        )
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM scheduled_job_runs WHERE job_name = :job_name"),
                {"job_name": job_name},
            )
