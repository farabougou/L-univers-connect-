"""Palier FAILURE_TESTED (ADR 017 §1 et §2.2) : les valeurs produites par un
scénario de panne du Virtual Protocol Adapter, injectées par le même chemin
qu'une vraie mesure (`app.telemetry.record_measurement`), déclenchent
réellement la règle FDD déjà écrite et testée pour un capteur réel
(`app.rules.CorrelationRule`, `simultaneous_heating_cooling` — voir
tests/test_rules_correlation.py, dont ce test reprend le motif). Preuve que
le scénario n'est pas qu'une valeur plausible : c'est la même chaîne
Virtual Asset → télémétrie → FDD → constat que pour un équipement réel."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.config_versions import activate_version, create_version
from app.connectors.virtual_telemetry import failure_scenario, generate_profile_values
from app.db import engine
from app.desired_states import declare_desired_state
from app.findings import list_findings
from app.points import create_point, decide_point, get_point
from app.rules import ALARM_RULE
from app.telemetry import record_measurement
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_config_versions_for_tenant

T0 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def _virtual_cta_tenant() -> dict:
    """Équivalent minimal d'un équipement créé par
    scripts/seed_virtual_site.py : juste assez pour exercer la règle FDD,
    sans dépendre du script (qui a sa propre vérification, incrément 1)."""
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    equipment_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'VirtualFDD', :slug)"),
            {"id": tenant_id, "slug": f"virtual-fdd-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text(
                "INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site virtuel')"
            ),
            {"id": site_id, "tenant_id": tenant_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'CTA-01', 'CTA virtuel 01')"
            ),
            {"id": equipment_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        heating = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA-01.vanne_chaude",
            name="Position vanne chaude",
            value_type="number",
            point_class="heating_valve_position",
            unit="%",
            functional_location_id=equipment_id,
            expected_interval_seconds=300,
            min_value=0,
            max_value=100,
            created_by="test",
        )
        cooling = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA-01.vanne_froide",
            name="Position vanne froide",
            value_type="number",
            point_class="cooling_valve_position",
            unit="%",
            functional_location_id=equipment_id,
            expected_interval_seconds=300,
            min_value=0,
            max_value=100,
            created_by="test",
        )
        damper = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA-01.volet_air_neuf",
            name="Position volet d'air neuf",
            value_type="number",
            point_class="economizer_damper_position",
            unit="%",
            functional_location_id=equipment_id,
            expected_interval_seconds=300,
            min_value=0,
            max_value=100,
            created_by="test",
        )
        supply_temp = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA-01.t_depart",
            name="Température départ CTA",
            value_type="number",
            point_class="supply_air_temperature_sensor",
            unit="Cel",
            functional_location_id=equipment_id,
            expected_interval_seconds=300,
            # Même plage que le profil virtuel (VirtualPointSpec "t_depart",
            # app/connectors/virtual_telemetry.py) : une dérive qui sortirait
            # de cette plage serait d'abord un problème de qualité de donnée
            # (app.quality_flags), pas encore une prédiction à évaluer.
            min_value=10,
            max_value=30,
            created_by="test",
        )
        for point_id in (heating, cooling, damper, supply_temp):
            decide_point(connection, point_id=point_id, decision="validated")
    return {
        "tenant_id": tenant_id,
        "equipment_id": equipment_id,
        "heating": heating,
        "cooling": cooling,
        "damper": damper,
        "supply_temp": supply_temp,
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
            "measurements",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    purge_config_versions_for_tenant(tenant_id)
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("desired_states", "points", "functional_locations", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


@pytest.fixture
def tenant():
    tenant = _virtual_cta_tenant()
    yield tenant
    _cleanup(tenant)


def _activate_correlation_rule(connection, tenant) -> None:
    content = {
        "kind": "simultaneous_heating_cooling",
        "heating_point_id": str(tenant["heating"]),
        "cooling_point_id": str(tenant["cooling"]),
        "heating_threshold": 20,
        "cooling_threshold": 20,
        "severity": "major",
        "title": "Chauffage et refroidissement actifs en même temps (actif virtuel)",
    }
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ALARM_RULE,
        subject_key="cta-01-virtuel-chaud-froid",
        content=content,
        author="responsable",
        reason="test",
    )
    activate_version(connection, version_id=version_id, activated_by="approbateur", activated_at=T0)


def _activate_divergence_rule(connection, tenant) -> None:
    content = {
        "kind": "desired_state_divergence",
        "point_id": str(tenant["damper"]),
        "tolerance": 15,
        "severity": "warning",
        "title": "Volet d'air neuf : écart à l'état souhaité (actif virtuel)",
    }
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ALARM_RULE,
        subject_key="cta-01-virtuel-volet-air-neuf",
        content=content,
        author="responsable",
        reason="test",
    )
    activate_version(connection, version_id=version_id, activated_by="approbateur", activated_at=T0)


def test_stuck_economizer_damper_scenario_raises_a_real_commissioning_finding(tenant) -> None:
    """Preuve que le scénario `economiseur_bloque` déclenche la règle FDD
    `desired_state_divergence` déjà écrite (app/rules.py), sans aucun nouveau
    code de règle — seulement un point et un scénario de panne nouveaux
    (voir app/connectors/virtual_telemetry.py)."""
    scenario = failure_scenario("cta", "economiseur_bloque")
    values = generate_profile_values("cta", now=T0, scenario=scenario)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        declare_desired_state(
            connection,
            tenant_id=tenant["tenant_id"],
            point_id=tenant["damper"],
            value=80.0,
            valid_from=T0 - timedelta(days=1),
            reason="Modulation libre-refroidissement attendue (test)",
            created_by="responsable",
        )
        _activate_divergence_rule(connection, tenant)

        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["damper"]),
            value=values["volet_air_neuf"],
            measured_at=T0,
            origin="simulated",
            source="virtual_commissioning_lab",
            received_at=T0,
        )
        findings = list_findings(connection)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["kind"] == "commissioning"
    assert finding["condition_state"] == "active"
    assert finding["reason_code"] == "RULE_DESIRED_STATE_DIVERGENCE"
    assert finding["reason_params"]["actual"] == values["volet_air_neuf"]
    assert finding["reason_params"]["desired"] == 80.0


def test_healthy_economizer_modulation_never_raises_the_finding(tenant) -> None:
    """Contrôle négatif : sans scénario, la modulation saine du volet (autour
    de 50 % +/- cycle jour/nuit) reste dans la tolérance de la règle — un
    scénario de panne doit être explicitement choisi pour produire un
    défaut."""
    values = generate_profile_values("cta", now=T0)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        declare_desired_state(
            connection,
            tenant_id=tenant["tenant_id"],
            point_id=tenant["damper"],
            value=80.0,
            valid_from=T0 - timedelta(days=1),
            reason="Modulation libre-refroidissement attendue (test)",
            created_by="responsable",
        )
        _activate_divergence_rule(connection, tenant)

        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["damper"]),
            value=values["volet_air_neuf"],
            measured_at=T0,
            origin="simulated",
            source="virtual_commissioning_lab",
            received_at=T0,
        )
        findings = list_findings(connection)

    assert findings == []


def test_simultaneous_heating_cooling_scenario_raises_a_real_finding(tenant) -> None:
    scenario = failure_scenario("cta", "chauffage_froid_simultane")
    values = generate_profile_values("cta", now=T0, scenario=scenario)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_correlation_rule(connection, tenant)

        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["heating"]),
            value=values["vanne_chaude"],
            measured_at=T0,
            origin="simulated",
            source="virtual_commissioning_lab",
            received_at=T0,
        )
        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["cooling"]),
            value=values["vanne_froide"],
            measured_at=T0 + timedelta(seconds=30),
            origin="simulated",
            source="virtual_commissioning_lab",
            received_at=T0 + timedelta(seconds=30),
        )
        findings = list_findings(connection)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["kind"] == "fault"
    assert finding["condition_state"] == "active"
    assert finding["reason_code"] == "RULE_SIMULTANEOUS_HEATING_COOLING"
    assert finding["reason_params"]["heating_value"] == values["vanne_chaude"]
    assert finding["reason_params"]["cooling_value"] == values["vanne_froide"]


def test_healthy_baseline_never_raises_the_finding(tenant) -> None:
    """Contrôle négatif : sans scénario, la télémétrie saine (vannes fermées
    par défaut) ne doit jamais déclencher la règle — un scénario de panne
    doit être explicitement choisi pour produire un défaut."""
    values = generate_profile_values("cta", now=T0)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_correlation_rule(connection, tenant)
        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["heating"]),
            value=values["vanne_chaude"],
            measured_at=T0,
            origin="simulated",
            source="virtual_commissioning_lab",
            received_at=T0,
        )
        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["cooling"]),
            value=values["vanne_froide"],
            measured_at=T0 + timedelta(seconds=30),
            origin="simulated",
            source="virtual_commissioning_lab",
            received_at=T0 + timedelta(seconds=30),
        )
        findings = list_findings(connection)

    assert findings == []


def _activate_trend_projection_rule(connection, tenant) -> None:
    content = {
        "kind": "trend_projection",
        "point_id": str(tenant["supply_temp"]),
        "operator": ">",
        "threshold": 28.0,
        "window_minutes": 60,
        "horizon_minutes": 180,
        "severity": "warning",
        "title": "Dérive du capteur de température de départ (actif virtuel)",
        "recommended_action": "Planifier le remplacement avant qu'il ne sorte de sa plage.",
    }
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ALARM_RULE,
        subject_key="cta-01-virtuel-projection-derive",
        content=content,
        author="responsable",
        reason="test",
    )
    activate_version(connection, version_id=version_id, activated_by="approbateur", activated_at=T0)


def test_sensor_drift_scenario_raises_a_real_prediction(tenant) -> None:
    """Palier FAILURE_TESTED pour la maintenance prédictive (02/10/2026,
    décision de Mohamed) : le scénario `capteur_derive` déjà existant
    (dérive linéaire de 4°C/heure, `app/connectors/virtual_telemetry.py`)
    déclenche réellement `TrendProjectionRule` (`app/rules.py`) — aucun
    nouveau mécanisme de simulation, seulement une nouvelle règle qui lit la
    même télémétrie que les autres scénarios de ce fichier."""
    scenario = failure_scenario("cta", "capteur_derive")

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_trend_projection_rule(connection, tenant)

        # Deux relevés dérivés, une heure d'écart : la pente observée (environ
        # 4°C/heure) resterait sous le seuil de 28°C maintenant, mais
        # l'atteindrait dans l'horizon de 180 minutes — une vraie prédiction,
        # jamais un constat de seuil déjà franchi.
        first_values = generate_profile_values(
            "cta", now=T0, scenario=scenario, scenario_started_at=T0
        )
        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["supply_temp"]),
            value=first_values["t_depart"],
            measured_at=T0,
            origin="simulated",
            source="virtual_commissioning_lab",
            received_at=T0,
        )
        second_values = generate_profile_values(
            "cta",
            now=T0 + timedelta(hours=1),
            scenario=scenario,
            scenario_started_at=T0,
        )
        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["supply_temp"]),
            value=second_values["t_depart"],
            measured_at=T0 + timedelta(hours=1),
            origin="simulated",
            source="virtual_commissioning_lab",
            received_at=T0 + timedelta(hours=1),
        )
        findings = list_findings(connection, kind="prediction")

    assert len(findings) == 1
    finding = findings[0]
    assert finding["reason_code"] == "RULE_TREND_PROJECTION"
    assert finding["certainty"] == "prediction"
    assert finding["confidence"] is None
    assert finding["reason_params"]["current_value"] == second_values["t_depart"]


def test_healthy_sensor_never_raises_a_prediction(tenant) -> None:
    """Contrôle négatif : sans scénario, la valeur saine (oscillation autour
    de 18°C) ne dérive vers aucun seuil — une prédiction exige un véritable
    scénario de panne, jamais une fluctuation normale."""
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_trend_projection_rule(connection, tenant)

        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["supply_temp"]),
            value=generate_profile_values("cta", now=T0)["t_depart"],
            measured_at=T0,
            origin="simulated",
            source="virtual_commissioning_lab",
            received_at=T0,
        )
        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["supply_temp"]),
            value=generate_profile_values("cta", now=T0 + timedelta(hours=1))["t_depart"],
            measured_at=T0 + timedelta(hours=1),
            origin="simulated",
            source="virtual_commissioning_lab",
            received_at=T0 + timedelta(hours=1),
        )
        findings = list_findings(connection, kind="prediction")

    assert findings == []
