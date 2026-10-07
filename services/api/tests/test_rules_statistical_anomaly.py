"""Règle FDD « anomalie statistique » (07/10/2026, V3 — priorité « anomaly
detection » de la feuille de route : Predict → Diagnose → Compare → Optimize,
app/rules.py::_evaluate_statistical_anomaly). Premier type de règle qui ne
compare pas à un seuil fixé par une personne, mais à la baseline récente du
point lui-même (moyenne + écart-type glissants) — et premier type de règle
qui porte une confiance réellement calculée plutôt que la certitude totale
(1.0) des règles instantanées (ADR 013 : jamais plus que ce que le système
sait). Même motif que tests/test_rules_trend_projection.py."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.config_versions import ConfigInvalid, activate_version, create_version
from app.findings import list_findings
from app.points import get_point
from app.rules import ALARM_RULE
from app.telemetry import record_measurement
from tests.analytics_fixtures import cleanup_tenant, create_tenant_with_points, in_tenant
from tests.error_helpers import raises_code

T0 = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)


@pytest.fixture
def two_tenants():
    tenant_a = create_tenant_with_points("ClientStatisticalAnomalyA")
    tenant_b = create_tenant_with_points("ClientStatisticalAnomalyB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        cleanup_tenant(tenant)


def _activate_statistical_anomaly_rule(
    connection,
    tenant,
    *,
    window_minutes=60,
    min_samples=5,
    deviation_threshold=2.0,
    **overrides,
):
    content = {
        "kind": "statistical_anomaly",
        "point_id": str(tenant["sensor"]),
        "window_minutes": window_minutes,
        "min_samples": min_samples,
        "deviation_threshold": deviation_threshold,
        "severity": "warning",
        "title": "Anomalie statistique sur la température de départ",
        "recommended_action": "Comparer avec la consigne et le fonctionnement attendu.",
        "create_work_order": False,
    }
    content.update(overrides)
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ALARM_RULE,
        subject_key="cta01-anomalie-statistique",
        content=content,
        author="responsable",
        reason="test",
    )
    activate_version(connection, version_id=version_id, activated_by="approbateur", activated_at=T0)
    return version_id


def _measure(connection, tenant, value, at):
    return record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=get_point(connection, tenant["sensor"]),
        value=value,
        measured_at=at,
        origin="simulated",
        source="simulator",
        received_at=at,
    )


def _findings(connection):
    return list_findings(connection, kind="fault")


def _seed_stable_baseline(connection, tenant, values, start=T0, step_minutes=10):
    for index, value in enumerate(values):
        _measure(connection, tenant, value, start + timedelta(minutes=index * step_minutes))


def test_value_far_from_the_baseline_raises_a_finding(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        version_id = _activate_statistical_anomaly_rule(
            connection, tenant_a, window_minutes=90, min_samples=5, deviation_threshold=2.0
        )
        # Baseline stable autour de 20, faible variation : moyenne ~20.2,
        # écart-type ~0.84. Une valeur à 30 est à plus de 11 écarts-types.
        _seed_stable_baseline(connection, tenant_a, [20, 21, 19, 20, 21])
        _measure(connection, tenant_a, 30.0, T0 + timedelta(minutes=50))
        findings = _findings(connection)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["reason_code"] == "RULE_STATISTICAL_ANOMALY"
    assert finding["kind"] == "fault"
    assert finding["method"] == "statistical"
    assert finding["rule_config_version_id"] == version_id
    assert finding["reason_params"]["point_code"] == "CTA01-TDEP"
    assert finding["reason_params"]["value"] == 30.0
    assert finding["reason_params"]["deviation_threshold"] == 2.0
    assert "confidence" not in finding["reason_params"]
    # Une inférence statistique reste une inférence : jamais la certitude
    # totale (1.0) d'une comparaison instantanée à un seuil.
    assert finding["confidence"] is not None
    assert 0.0 < finding["confidence"] < 1.0


def test_value_within_the_baseline_raises_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_statistical_anomaly_rule(
            connection, tenant_a, window_minutes=90, min_samples=5, deviation_threshold=2.0
        )
        _seed_stable_baseline(connection, tenant_a, [20, 21, 19, 20, 21])
        # Dans la continuité de la baseline : aucune anomalie.
        _measure(connection, tenant_a, 20.5, T0 + timedelta(minutes=50))
        assert _findings(connection) == []


def test_not_enough_samples_in_the_window_raises_nothing(two_tenants) -> None:
    """Moins de `min_samples` relevés dans la fenêtre : jamais une baseline
    calculée à partir de trop peu de mesures pour être fiable."""
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_statistical_anomaly_rule(
            connection, tenant_a, window_minutes=90, min_samples=5, deviation_threshold=2.0
        )
        _seed_stable_baseline(connection, tenant_a, [20, 21, 19])
        _measure(connection, tenant_a, 30.0, T0 + timedelta(minutes=50))
        assert _findings(connection) == []


def test_zero_variance_baseline_raises_nothing(two_tenants) -> None:
    """Écart-type nul (aucune variation réelle sur la fenêtre) : un z-score
    serait une division par zéro, jamais un calcul — pas de constat, même si
    la valeur courante diffère nettement d'une baseline parfaitement plate."""
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_statistical_anomaly_rule(
            connection, tenant_a, window_minutes=90, min_samples=5, deviation_threshold=2.0
        )
        _seed_stable_baseline(connection, tenant_a, [20, 20, 20, 20, 20])
        _measure(connection, tenant_a, 100.0, T0 + timedelta(minutes=50))
        assert _findings(connection) == []


def test_deviation_at_or_below_the_threshold_raises_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_statistical_anomaly_rule(
            connection, tenant_a, window_minutes=90, min_samples=5, deviation_threshold=20.0
        )
        _seed_stable_baseline(connection, tenant_a, [20, 21, 19, 20, 21])
        # Seuil de déviation très large : même un écart marqué reste accepté.
        _measure(connection, tenant_a, 30.0, T0 + timedelta(minutes=50))
        assert _findings(connection) == []


def test_statistical_anomaly_rule_requires_a_number(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with raises_code(ConfigInvalid, "RULE_STATISTICAL_ANOMALY_REQUIRES_NUMBER"):
        with in_tenant(tenant_a) as connection:
            create_version(
                connection,
                tenant_id=tenant_a["tenant_id"],
                config_type=ALARM_RULE,
                subject_key="cta01-anomalie-invalide",
                content={
                    "kind": "statistical_anomaly",
                    "point_id": str(tenant_a["run_status"]),
                    "window_minutes": 90,
                    "min_samples": 5,
                    "deviation_threshold": 2.0,
                    "severity": "warning",
                    "title": "Anomalie (mauvais point)",
                },
                author="responsable",
                reason="test",
            )


def test_tenant_isolation(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_statistical_anomaly_rule(
            connection, tenant_a, window_minutes=90, min_samples=5, deviation_threshold=2.0
        )
        _seed_stable_baseline(connection, tenant_a, [20, 21, 19, 20, 21])
        _measure(connection, tenant_a, 30.0, T0 + timedelta(minutes=50))
        seen_by_a = connection.execute(
            text("SELECT 1 FROM findings WHERE tenant_id = :id"), {"id": tenant_a["tenant_id"]}
        ).fetchall()
    with in_tenant(tenant_b) as connection:
        seen_by_b = connection.execute(
            text("SELECT 1 FROM findings WHERE tenant_id = :id"), {"id": tenant_a["tenant_id"]}
        ).fetchall()
    assert seen_by_a
    assert seen_by_b == []
