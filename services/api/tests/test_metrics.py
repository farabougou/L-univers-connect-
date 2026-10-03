"""Métriques HTTP minimales (app/metrics.py, feature-benchmark-matrix.md,
ligne « Observabilité ») : agrégats seulement, jamais de donnée métier ni
par tenant."""

from fastapi.testclient import TestClient

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
