"""Règle FDD « cycles courts » (01/10/2026, app/rules.py::_evaluate_short_cycling) :
deuxième AFDD standard du secteur (ASHRAE Guideline 36), premier type de
règle qui porte sur un historique de mesures plutôt que sur l'instant
présent seul. Même motif que tests/test_rules_correlation.py."""

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

T0 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def two_tenants():
    tenant_a = create_tenant_with_points("ClientShortCyclingA")
    tenant_b = create_tenant_with_points("ClientShortCyclingB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        cleanup_tenant(tenant)


def _activate_short_cycling_rule(
    connection, tenant, *, max_starts=2, window_minutes=10, **overrides
):
    content = {
        "kind": "short_cycling",
        "point_id": str(tenant["run_status"]),
        "max_starts": max_starts,
        "window_minutes": window_minutes,
        "severity": "major",
        "title": "Cycles courts sur la CTA",
        "recommended_action": "Vérifier la régulation et la protection du compresseur.",
        "create_work_order": False,
    }
    content.update(overrides)
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ALARM_RULE,
        subject_key="cta01-cycles-courts",
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
        point=get_point(connection, tenant["run_status"]),
        value=value,
        measured_at=at,
        origin="simulated",
        source="simulator",
        received_at=at,
    )


def _findings(connection):
    return list_findings(connection, kind="fault")


def test_too_many_starts_in_the_window_raises_a_finding(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        version_id = _activate_short_cycling_rule(
            connection, tenant_a, max_starts=2, window_minutes=10
        )
        # Trois démarrages en 7 minutes : au-delà de la limite de 2.
        _measure(connection, tenant_a, 1, T0)
        _measure(connection, tenant_a, 0, T0 + timedelta(minutes=1))
        _measure(connection, tenant_a, 1, T0 + timedelta(minutes=3))
        _measure(connection, tenant_a, 0, T0 + timedelta(minutes=4))
        _measure(connection, tenant_a, 1, T0 + timedelta(minutes=7))
        findings = _findings(connection)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["reason_code"] == "RULE_SHORT_CYCLING"
    assert finding["kind"] == "fault"
    assert finding["condition_state"] == "active"
    assert finding["rule_config_version_id"] == version_id
    assert finding["reason_params"] == {
        "point_code": "CTA01-MARCHE",
        "start_count": 3,
        "window_minutes": 10,
        "max_starts": 2,
    }


def test_starts_within_the_limit_raise_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_short_cycling_rule(connection, tenant_a, max_starts=2, window_minutes=10)
        _measure(connection, tenant_a, 1, T0)
        _measure(connection, tenant_a, 0, T0 + timedelta(minutes=1))
        _measure(connection, tenant_a, 1, T0 + timedelta(minutes=3))
        assert _findings(connection) == []


def test_repeated_on_readings_without_a_stop_count_as_a_single_start(two_tenants) -> None:
    """Un simple sondage répété pendant une marche normale (plusieurs relevés
    « marche » d'affilée, sans arrêt entre deux) ne doit jamais être compté
    comme autant de nouveaux démarrages."""
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_short_cycling_rule(connection, tenant_a, max_starts=2, window_minutes=10)
        _measure(connection, tenant_a, 1, T0)
        _measure(connection, tenant_a, 1, T0 + timedelta(minutes=1))
        _measure(connection, tenant_a, 1, T0 + timedelta(minutes=2))
        _measure(connection, tenant_a, 1, T0 + timedelta(minutes=3))
        assert _findings(connection) == []


def test_starts_outside_the_window_do_not_count(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_short_cycling_rule(connection, tenant_a, max_starts=1, window_minutes=5)
        # Deux démarrages très espacés (20 minutes) : jamais dans la même
        # fenêtre de 5 minutes.
        _measure(connection, tenant_a, 1, T0)
        _measure(connection, tenant_a, 0, T0 + timedelta(minutes=1))
        _measure(connection, tenant_a, 1, T0 + timedelta(minutes=20))
        assert _findings(connection) == []


def test_finding_clears_once_old_starts_fall_out_of_the_window(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_short_cycling_rule(connection, tenant_a, max_starts=1, window_minutes=10)
        _measure(connection, tenant_a, 1, T0)
        _measure(connection, tenant_a, 0, T0 + timedelta(minutes=1))
        _measure(connection, tenant_a, 1, T0 + timedelta(minutes=3))
        assert len(_findings(connection)) == 1

        # 20 minutes plus tard : les deux démarrages précédents (T0, T0+3)
        # sont hors de la fenêtre glissante de 10 minutes qui se termine ici.
        _measure(connection, tenant_a, 0, T0 + timedelta(minutes=23))
        findings = _findings(connection)

    assert findings[0]["condition_state"] == "cleared"


def test_short_cycling_rule_requires_a_boolean_point(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with raises_code(ConfigInvalid, "RULE_SHORT_CYCLING_REQUIRES_BOOLEAN"):
        with in_tenant(tenant_a) as connection:
            create_version(
                connection,
                tenant_id=tenant_a["tenant_id"],
                config_type=ALARM_RULE,
                subject_key="cta01-cycles-courts-invalide",
                content={
                    "kind": "short_cycling",
                    "point_id": str(tenant_a["sensor"]),
                    "max_starts": 2,
                    "window_minutes": 10,
                    "severity": "major",
                    "title": "Cycles courts (mauvais point)",
                },
                author="responsable",
                reason="test",
            )


def test_tenant_isolation(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with in_tenant(tenant_a) as connection:
        _activate_short_cycling_rule(connection, tenant_a, max_starts=1, window_minutes=10)
        _measure(connection, tenant_a, 1, T0)
        _measure(connection, tenant_a, 0, T0 + timedelta(minutes=1))
        _measure(connection, tenant_a, 1, T0 + timedelta(minutes=3))
        seen_by_a = connection.execute(
            text("SELECT 1 FROM findings WHERE tenant_id = :id"), {"id": tenant_a["tenant_id"]}
        ).fetchall()
    with in_tenant(tenant_b) as connection:
        seen_by_b = connection.execute(
            text("SELECT 1 FROM findings WHERE tenant_id = :id"), {"id": tenant_a["tenant_id"]}
        ).fetchall()
    assert seen_by_a
    assert seen_by_b == []
