"""Règle prédictive « projection de tendance » (02/10/2026, décision de
Mohamed : le pipeline logiciel de maintenance prédictive avance en
simulation, seule l'annonce d'une performance réelle reste
DEFERRED_PHYSICAL_VALIDATION — app/rules.py::_evaluate_trend_projection).
Premier type de règle qui porte sur l'avenir (constat de nature
« prediction »), une sécante à deux points, jamais un modèle entraîné.
Même motif que tests/test_rules_short_cycling.py."""

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

T0 = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)


@pytest.fixture
def two_tenants():
    tenant_a = create_tenant_with_points("ClientTrendProjectionA")
    tenant_b = create_tenant_with_points("ClientTrendProjectionB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        cleanup_tenant(tenant)


def _activate_trend_projection_rule(
    connection,
    tenant,
    *,
    operator=">",
    threshold=30.0,
    window_minutes=60,
    horizon_minutes=120,
    **overrides,
):
    content = {
        "kind": "trend_projection",
        "point_id": str(tenant["sensor"]),
        "operator": operator,
        "threshold": threshold,
        "window_minutes": window_minutes,
        "horizon_minutes": horizon_minutes,
        "severity": "warning",
        "title": "Dérive du capteur de température",
        "recommended_action": "Planifier le remplacement du capteur avant la panne.",
        "create_work_order": False,
    }
    content.update(overrides)
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ALARM_RULE,
        subject_key="cta01-projection-derive",
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
    return list_findings(connection, kind="prediction")


def test_rising_trend_toward_threshold_raises_a_prediction(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        version_id = _activate_trend_projection_rule(
            connection,
            tenant_a,
            operator=">",
            threshold=30.0,
            window_minutes=60,
            horizon_minutes=120,
        )
        # Dérive de 10°C en 60 minutes (20 -> 30 dans 60 min) : au rythme
        # observé, le seuil de 30 serait atteint dans 60 min, sous l'horizon.
        _measure(connection, tenant_a, 20.0, T0)
        _measure(connection, tenant_a, 25.0, T0 + timedelta(minutes=60))
        findings = _findings(connection)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["reason_code"] == "RULE_TREND_PROJECTION"
    assert finding["kind"] == "prediction"
    assert finding["certainty"] == "prediction"
    assert finding["confidence"] is None
    assert finding["rule_config_version_id"] == version_id
    assert finding["reason_params"]["point_code"] == "CTA01-TDEP"
    assert finding["reason_params"]["threshold"] == 30.0
    assert finding["reason_params"]["projected_minutes"] == 60


def test_falling_trend_toward_a_lower_threshold_raises_a_prediction(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_trend_projection_rule(
            connection,
            tenant_a,
            operator="<",
            threshold=10.0,
            window_minutes=60,
            horizon_minutes=120,
        )
        _measure(connection, tenant_a, 20.0, T0)
        _measure(connection, tenant_a, 15.0, T0 + timedelta(minutes=60))
        assert len(_findings(connection)) == 1


def test_stable_value_raises_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_trend_projection_rule(connection, tenant_a, operator=">", threshold=30.0)
        _measure(connection, tenant_a, 20.0, T0)
        _measure(connection, tenant_a, 20.0, T0 + timedelta(minutes=60))
        assert _findings(connection) == []


def test_trend_moving_away_from_threshold_raises_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_trend_projection_rule(connection, tenant_a, operator=">", threshold=30.0)
        # Dérive à la baisse : s'éloigne du seuil haut, jamais une prédiction.
        _measure(connection, tenant_a, 25.0, T0)
        _measure(connection, tenant_a, 20.0, T0 + timedelta(minutes=60))
        assert _findings(connection) == []


def test_projection_beyond_the_horizon_raises_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_trend_projection_rule(
            connection,
            tenant_a,
            operator=">",
            threshold=100.0,
            window_minutes=60,
            horizon_minutes=30,
        )
        # Dérive lente : seuil atteint bien au-delà de l'horizon de 30 min.
        _measure(connection, tenant_a, 20.0, T0)
        _measure(connection, tenant_a, 21.0, T0 + timedelta(minutes=60))
        assert _findings(connection) == []


def test_threshold_already_breached_is_not_a_prediction(two_tenants) -> None:
    """Un seuil déjà franchi relève de ThresholdRule, qui constate — jamais
    de cette règle, qui prédit un franchissement futur."""
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_trend_projection_rule(connection, tenant_a, operator=">", threshold=30.0)
        _measure(connection, tenant_a, 20.0, T0)
        _measure(connection, tenant_a, 35.0, T0 + timedelta(minutes=60))
        assert _findings(connection) == []


def test_single_measurement_in_window_raises_nothing(two_tenants) -> None:
    """Pas assez d'historique dans la fenêtre pour estimer une pente :
    jamais une tendance inventée à partir d'un seul point."""
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_trend_projection_rule(connection, tenant_a, operator=">", threshold=30.0)
        _measure(connection, tenant_a, 20.0, T0)
        assert _findings(connection) == []


def test_trend_projection_rule_requires_a_number(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with raises_code(ConfigInvalid, "RULE_TREND_PROJECTION_REQUIRES_NUMBER"):
        with in_tenant(tenant_a) as connection:
            create_version(
                connection,
                tenant_id=tenant_a["tenant_id"],
                config_type=ALARM_RULE,
                subject_key="cta01-projection-invalide",
                content={
                    "kind": "trend_projection",
                    "point_id": str(tenant_a["run_status"]),
                    "operator": ">",
                    "threshold": 30.0,
                    "window_minutes": 60,
                    "horizon_minutes": 120,
                    "severity": "warning",
                    "title": "Projection (mauvais point)",
                },
                author="responsable",
                reason="test",
            )


def test_tenant_isolation(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_trend_projection_rule(connection, tenant_a, operator=">", threshold=30.0)
        _measure(connection, tenant_a, 20.0, T0)
        _measure(connection, tenant_a, 25.0, T0 + timedelta(minutes=60))
        seen_by_a = connection.execute(
            text("SELECT 1 FROM findings WHERE tenant_id = :id"), {"id": tenant_a["tenant_id"]}
        ).fetchall()
    with in_tenant(tenant_b) as connection:
        seen_by_b = connection.execute(
            text("SELECT 1 FROM findings WHERE tenant_id = :id"), {"id": tenant_a["tenant_id"]}
        ).fetchall()
    assert seen_by_a
    assert seen_by_b == []
