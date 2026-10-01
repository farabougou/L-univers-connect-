"""Règle FDD à deux points : chauffage et refroidissement actifs en même
temps (ADR 012, étape F4 — voir le docstring de app/rules.py). Jamais du
machine learning : une comparaison physique immédiate entre deux points,
pas un historique — donc jamais concernée par le blocage de la maintenance
prédictive (feature-benchmark-matrix.md)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.config_versions import ConfigInvalid, activate_version, create_version
from app.db import engine
from app.findings import list_findings
from app.points import create_point, decide_point, get_point
from app.rules import ALARM_RULE
from app.telemetry import record_measurement
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_config_versions_for_tenant
from tests.error_helpers import raises_code

T0 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def _tenant(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    ahu_id = uuid.uuid4()
    other_ahu_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site')"),
            {"id": site_id, "tenant_id": tenant_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'cta-01', 'CTA 01')"
            ),
            {"id": ahu_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'cta-02', 'CTA 02')"
            ),
            {"id": other_ahu_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        heating = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA01-VANNE-CHAUD",
            name="Position vanne chaude",
            value_type="number",
            point_class="heating_valve_position",
            unit="%",
            functional_location_id=ahu_id,
            expected_interval_seconds=300,
            min_value=0,
            max_value=100,
            created_by="test",
        )
        cooling = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA01-VANNE-FROID",
            name="Position vanne froide",
            value_type="number",
            point_class="cooling_valve_position",
            unit="%",
            functional_location_id=ahu_id,
            expected_interval_seconds=300,
            min_value=0,
            max_value=100,
            created_by="test",
        )
        other_equipment_point = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA02-VANNE-FROID",
            name="Position vanne froide",
            value_type="number",
            point_class="cooling_valve_position",
            unit="%",
            functional_location_id=other_ahu_id,
            expected_interval_seconds=300,
            min_value=0,
            max_value=100,
            created_by="test",
        )
        run_status = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA01-MARCHE",
            name="État de marche",
            value_type="boolean",
            point_class="run_status",
            functional_location_id=ahu_id,
            created_by="test",
        )
        for point_id in (heating, cooling, other_equipment_point, run_status):
            decide_point(connection, point_id=point_id, decision="validated")
    return {
        "tenant_id": tenant_id,
        "site": site_id,
        "ahu": ahu_id,
        "heating": heating,
        "cooling": cooling,
        "other_equipment_point": other_equipment_point,
        "run_status": run_status,
    }


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "events",
            "finding_status_history",
            "findings",
            "alarm_status_history",
            "alarms",
            "work_order_status_history",
            "work_orders",
            "desired_states",
            "measurements",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    purge_config_versions_for_tenant(tenant_id)
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("points", "functional_locations", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


@pytest.fixture
def tenant():
    tenant = _tenant("ClientFDD")
    yield tenant
    _cleanup(tenant)


def _activate_correlation_rule(connection, tenant, subject_key="cta01-chaud-froid", **overrides):
    content = {
        "kind": "simultaneous_heating_cooling",
        "heating_point_id": str(tenant["heating"]),
        "cooling_point_id": str(tenant["cooling"]),
        "heating_threshold": 20,
        "cooling_threshold": 20,
        "severity": "major",
        "title": "Chauffage et refroidissement actifs en même temps sur CTA 01",
    }
    content.update(overrides)
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ALARM_RULE,
        subject_key=subject_key,
        content=content,
        author="responsable",
        reason="test",
    )
    activate_version(connection, version_id=version_id, activated_by="approbateur", activated_at=T0)
    return version_id


def _measure(connection, tenant, point_key, value, at):
    return record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=get_point(connection, tenant[point_key]),
        value=value,
        measured_at=at,
        origin="simulated",
        source="simulator",
        received_at=at,
    )


def test_both_valves_open_at_once_raises_a_fault_finding(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_correlation_rule(connection, tenant)
        # La vanne chaude seule, sans contrepartie encore mesurée : aucune
        # preuve de simultanéité, donc aucun constat.
        _measure(connection, tenant, "heating", 50, T0)
        findings_after_first = list_findings(connection)
        assert findings_after_first == []

        # La vanne froide s'ouvre aussi, peu après, pendant que la lecture
        # de la vanne chaude reste récente : simultanéité confirmée.
        _measure(connection, tenant, "cooling", 60, T0 + timedelta(seconds=30))
        findings = list_findings(connection)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["kind"] == "fault"
    assert finding["condition_state"] == "active"
    assert finding["reason_code"] == "RULE_SIMULTANEOUS_HEATING_COOLING"
    assert finding["reason_params"]["heating_value"] == 50
    assert finding["reason_params"]["cooling_value"] == 60


def test_only_one_valve_open_raises_nothing(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_correlation_rule(connection, tenant)
        _measure(connection, tenant, "heating", 50, T0)
        _measure(connection, tenant, "cooling", 5, T0 + timedelta(seconds=30))
        findings = list_findings(connection)
    assert findings == []


def test_a_stale_counterpart_never_confirms_simultaneity(tenant) -> None:
    """La vanne chaude était ouverte il y a longtemps : au moment où la
    vanne froide s'ouvre, on ne sait plus si la chaude l'est toujours. Pas de
    donnée inventée : aucun constat tant que la simultanéité n'est pas
    prouvée par deux relevés récents."""
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_correlation_rule(connection, tenant)
        _measure(connection, tenant, "heating", 50, T0)
        # expected_interval_seconds=300 ; péremption à 3x, soit 900s.
        _measure(connection, tenant, "cooling", 60, T0 + timedelta(seconds=1000))
        findings = list_findings(connection)
    assert findings == []


def test_return_to_normal_clears_the_finding(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_correlation_rule(connection, tenant)
        _measure(connection, tenant, "heating", 50, T0)
        _measure(connection, tenant, "cooling", 60, T0 + timedelta(seconds=30))
        assert list_findings(connection)[0]["condition_state"] == "active"

        # La vanne froide se referme : retour à la normale.
        _measure(connection, tenant, "cooling", 0, T0 + timedelta(seconds=60))
        finding = list_findings(connection)[0]
    assert finding["condition_state"] == "cleared"


def test_rule_requires_two_different_points(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "RULE_CORRELATION_SAME_POINT"):
            _activate_correlation_rule(
                connection, tenant, cooling_point_id=str(tenant["heating"])
            )


def test_rule_requires_points_on_the_same_equipment(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "RULE_CORRELATION_DIFFERENT_EQUIPMENT"):
            _activate_correlation_rule(
                connection,
                tenant,
                cooling_point_id=str(tenant["other_equipment_point"]),
            )


def test_rule_requires_numeric_points(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "RULE_CORRELATION_REQUIRES_NUMBER"):
            _activate_correlation_rule(
                connection, tenant, cooling_point_id=str(tenant["run_status"])
            )
