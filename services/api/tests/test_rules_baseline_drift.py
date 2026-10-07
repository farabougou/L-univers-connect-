"""Règle FDD « dérive de baseline » (07/10/2026, V3 — priorité « Drift » de
la feuille de route : Compare → Drift → Diagnose → Explain → Optimize,
app/rules.py::_evaluate_baseline_drift). Compare deux fenêtres temporelles
du même point (une fenêtre récente contre la fenêtre de référence qui la
précède immédiatement) — distinct de `statistical_anomaly` (une valeur
contre une baseline instantanée) et de `trend_projection` (une projection
vers un seuil fixé par une personne) : ici, aucun seuil absolu, seulement un
changement de comportement du point par rapport à lui-même dans le temps.

Décalage temporel choisi pour que seul le tout dernier relevé dispose
d'assez d'échantillons dans les deux fenêtres (`min_samples=3`) : les
relevés intermédiaires de la fenêtre récente ne doivent jamais suffire à
eux seuls, sans quoi le test vérifierait un déclenchement prématuré plutôt
que celui, attendu, du dernier relevé. Même motif que
tests/test_rules_statistical_anomaly.py."""

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

# Décalages (minutes depuis T0) des fenêtres par défaut
# (recent_window_minutes=30, reference_window_minutes=60), pour une
# évaluation finale à T0+95 : référence dans [T0+5, T0+65), récente dans
# [T0+65, T0+95].
_REFERENCE_OFFSETS = [10, 30, 50]
_RECENT_OFFSETS = [70, 80, 95]


@pytest.fixture
def two_tenants():
    tenant_a = create_tenant_with_points("ClientBaselineDriftA")
    tenant_b = create_tenant_with_points("ClientBaselineDriftB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        cleanup_tenant(tenant)


def _activate_baseline_drift_rule(
    connection,
    tenant,
    *,
    recent_window_minutes=30,
    reference_window_minutes=60,
    min_samples=3,
    deviation_threshold=2.0,
    **overrides,
):
    content = {
        "kind": "baseline_drift",
        "point_id": str(tenant["sensor"]),
        "recent_window_minutes": recent_window_minutes,
        "reference_window_minutes": reference_window_minutes,
        "min_samples": min_samples,
        "deviation_threshold": deviation_threshold,
        "severity": "warning",
        "title": "Dérive de comportement sur la température de départ",
        "recommended_action": "Comparer avec le fonctionnement observé juste avant.",
        "create_work_order": False,
    }
    content.update(overrides)
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ALARM_RULE,
        subject_key="cta01-derive-baseline",
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


def _seed_reference_window(connection, tenant, values):
    for offset, value in zip(_REFERENCE_OFFSETS[: len(values)], values, strict=True):
        _measure(connection, tenant, value, T0 + timedelta(minutes=offset))


def _seed_recent_window(connection, tenant, values):
    for offset, value in zip(_RECENT_OFFSETS[: len(values)], values, strict=True):
        _measure(connection, tenant, value, T0 + timedelta(minutes=offset))


def test_a_shift_between_the_two_windows_raises_a_finding(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        version_id = _activate_baseline_drift_rule(connection, tenant_a)
        # Référence stable autour de 20 (moyenne 20, écart-type 1) ; fenêtre
        # récente nettement plus haute (30) : dérive franche.
        _seed_reference_window(connection, tenant_a, [20, 21, 19])
        _seed_recent_window(connection, tenant_a, [30, 30, 30])
        findings = _findings(connection)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["reason_code"] == "RULE_BASELINE_DRIFT"
    assert finding["kind"] == "fault"
    assert finding["method"] == "statistical"
    assert finding["rule_config_version_id"] == version_id
    assert finding["reason_params"]["point_code"] == "CTA01-TDEP"
    assert finding["reason_params"]["reference_mean"] == 20.0
    assert finding["reason_params"]["recent_mean"] == 30.0
    assert finding["reason_params"]["deviation_threshold"] == 2.0
    assert "confidence" not in finding["reason_params"]
    assert finding["confidence"] is not None
    assert 0.0 < finding["confidence"] < 1.0


def test_similar_windows_raise_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_baseline_drift_rule(connection, tenant_a)
        _seed_reference_window(connection, tenant_a, [20, 21, 19])
        # Fenêtre récente dans la continuité de la référence : pas de dérive.
        _seed_recent_window(connection, tenant_a, [20, 21, 20])
        assert _findings(connection) == []


def test_not_enough_samples_in_the_reference_window_raises_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_baseline_drift_rule(connection, tenant_a, min_samples=3)
        _seed_reference_window(connection, tenant_a, [20, 21])  # 2 < min_samples
        _seed_recent_window(connection, tenant_a, [30, 30, 30])
        assert _findings(connection) == []


def test_not_enough_samples_in_the_recent_window_raises_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_baseline_drift_rule(connection, tenant_a, min_samples=3)
        _seed_reference_window(connection, tenant_a, [20, 21, 19])
        # Un seul relevé récent : jamais assez pour estimer la fenêtre
        # récente (min_samples=3).
        _measure(connection, tenant_a, 30.0, T0 + timedelta(minutes=80))
        assert _findings(connection) == []


def test_zero_variance_reference_window_raises_nothing(two_tenants) -> None:
    """Écart-type de référence nul : un z-score serait une division par
    zéro, jamais un calcul — pas de constat, même avec une fenêtre récente
    nettement différente."""
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_baseline_drift_rule(connection, tenant_a)
        _seed_reference_window(connection, tenant_a, [20, 20, 20])
        _seed_recent_window(connection, tenant_a, [99, 99, 99])
        assert _findings(connection) == []


def test_deviation_at_or_below_the_threshold_raises_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_baseline_drift_rule(connection, tenant_a, deviation_threshold=20.0)
        _seed_reference_window(connection, tenant_a, [20, 21, 19])
        _seed_recent_window(connection, tenant_a, [30, 30, 30])
        assert _findings(connection) == []


def test_baseline_drift_rule_requires_a_number(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with raises_code(ConfigInvalid, "RULE_BASELINE_DRIFT_REQUIRES_NUMBER"):
        with in_tenant(tenant_a) as connection:
            create_version(
                connection,
                tenant_id=tenant_a["tenant_id"],
                config_type=ALARM_RULE,
                subject_key="cta01-derive-invalide",
                content={
                    "kind": "baseline_drift",
                    "point_id": str(tenant_a["run_status"]),
                    "recent_window_minutes": 30,
                    "reference_window_minutes": 60,
                    "min_samples": 3,
                    "deviation_threshold": 2.0,
                    "severity": "warning",
                    "title": "Dérive (mauvais point)",
                },
                author="responsable",
                reason="test",
            )


def test_tenant_isolation(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_baseline_drift_rule(connection, tenant_a)
        _seed_reference_window(connection, tenant_a, [20, 21, 19])
        _seed_recent_window(connection, tenant_a, [30, 30, 30])
        seen_by_a = connection.execute(
            text("SELECT 1 FROM findings WHERE tenant_id = :id"), {"id": tenant_a["tenant_id"]}
        ).fetchall()
    with in_tenant(tenant_b) as connection:
        seen_by_b = connection.execute(
            text("SELECT 1 FROM findings WHERE tenant_id = :id"), {"id": tenant_a["tenant_id"]}
        ).fetchall()
    assert seen_by_a
    assert seen_by_b == []
