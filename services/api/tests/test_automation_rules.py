"""Moteur d'automatisation (app/automation_rules.py), dernière priorité de
la feuille de route V2 : commande sécurisée → modes/consignes →
autorisation/policies → Dry Run/Shadow → exécution simulée → vérification →
audit → planification → automatisation. Tests directs sur les fonctions
métier — voir app/automation_rules.py pour le détail des garde-fous."""

from datetime import UTC, datetime, timedelta

import pytest

from app.automation_rules import AUTOMATION_RULE, evaluate_automation_rules
from app.command_policies import COMMAND_POINT_POLICY
from app.commands import list_commands_for_point
from app.config_versions import ConfigInvalid, activate_version, create_version
from app.db import engine
from app.point_control_mode import POINT_CONTROL_MODE
from app.points import create_point, decide_point, get_point
from app.telemetry import record_measurement
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code
from tests.modbus_fixtures import (
    activate_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_point,
)

T0 = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


@pytest.fixture
def tenant():
    created = create_tenant_with_energy_point("ClientAutomatisation")
    with engine.begin() as connection:
        set_tenant_context(connection, created["tenant_id"])
        target_point_id = create_point(
            connection,
            tenant_id=created["tenant_id"],
            code=f"RELAIS-{created['tenant_id'].hex[:8]}",
            name="Relais test",
            value_type="number",
            point_class="energy_meter_reading",
            unit="kW.h",
            functional_location_id=created["location_id"],
            min_value=0,
            max_value=1,
            created_by="test",
        )
        decide_point(connection, point_id=target_point_id, decision="validated")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=5921,
        device_type="simulated_relay",
        points=[{"point_id": str(target_point_id), "register_name": "relay_state"}],
    )
    created["trigger_point_id"] = created["point_id"]
    created["target_point_id"] = target_point_id
    yield created
    cleanup_tenant(created)


def _record(connection, tenant, value, at, point_id=None):
    point = get_point(connection, point_id or tenant["trigger_point_id"])
    record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=point,
        value=value,
        measured_at=at,
        origin="simulated",
        source="simulator",
        received_at=at,
    )


def _activate_mode(connection, tenant, point_id, mode):
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=POINT_CONTROL_MODE,
        subject_key=str(point_id),
        content={"mode": mode},
        author="responsable",
        reason="test",
    )
    activate_version(
        connection, version_id=version_id, activated_by="admin_tenant", activated_at=T0
    )


def _create_rule(connection, tenant, **overrides):
    content = {
        "title": "Règle de test",
        "trigger_point_id": str(tenant["trigger_point_id"]),
        "operator": ">",
        "threshold": 50.0,
        "target_point_id": str(tenant["target_point_id"]),
        "requested_value": 1.0,
    }
    content.update(overrides)
    return create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=AUTOMATION_RULE,
        subject_key=f"rule:{tenant['trigger_point_id']}",
        content=content,
        author="responsable",
        reason="test",
    )


def _activate_rule(connection, version_id):
    activate_version(
        connection, version_id=version_id, activated_by="admin_tenant", activated_at=T0
    )


def test_contenu_invalide_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "AUTOMATION_RULE_CONTENT_INVALID"):
            _create_rule(connection, tenant, operator="=")  # hors énumération


def test_mode_manuel_par_defaut_bloque_le_declenchement(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _record(connection, tenant, 60.0, T0)
        _activate_rule(connection, _create_rule(connection, tenant))
        results = evaluate_automation_rules(connection, tenant_id=tenant["tenant_id"], at=T0)
        assert results[0]["status"] == "blocked_manual_mode"
        assert list_commands_for_point(connection, point_id=tenant["target_point_id"]) == []


def test_condition_non_remplie_ne_declenche_rien(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_mode(connection, tenant, tenant["target_point_id"], "automatic")
        _record(connection, tenant, 10.0, T0)
        _activate_rule(connection, _create_rule(connection, tenant))
        results = evaluate_automation_rules(connection, tenant_id=tenant["tenant_id"], at=T0)
        assert results[0]["status"] == "condition_not_met"


def test_regle_declenchee_cree_une_commande_reelle(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_mode(connection, tenant, tenant["target_point_id"], "automatic")
        _record(connection, tenant, 60.0, T0)
        _activate_rule(connection, _create_rule(connection, tenant))
        results = evaluate_automation_rules(connection, tenant_id=tenant["tenant_id"], at=T0)
        assert results[0]["status"] == "fired"
        commands = list_commands_for_point(connection, point_id=tenant["target_point_id"])
        assert len(commands) == 1
        assert commands[0]["requested_value"] == pytest.approx(1.0)
        assert commands[0]["requested_by"].startswith("automation:")


def test_donnee_hors_plage_bloque_le_declenchement(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_mode(connection, tenant, tenant["target_point_id"], "automatic")
        # max_value=1_000_000 sur le point déclencheur (create_tenant_with_energy_point) :
        # une valeur au-delà est hors plage, donc marquée par un drapeau de qualité.
        _record(connection, tenant, 2_000_000.0, T0)
        _activate_rule(connection, _create_rule(connection, tenant))
        results = evaluate_automation_rules(connection, tenant_id=tenant["tenant_id"], at=T0)
        assert results[0]["status"] == "blocked_untrusted_data"
        assert list_commands_for_point(connection, point_id=tenant["target_point_id"]) == []


def test_point_declencheur_non_valide_a_une_confiance_nulle(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        other_trigger_id = create_point(
            connection,
            tenant_id=tenant["tenant_id"],
            code=f"CAPTEUR-{tenant['tenant_id'].hex[:8]}",
            name="Capteur non validé",
            value_type="number",
            point_class="energy_meter_reading",
            unit="kW.h",
            functional_location_id=tenant["location_id"],
            min_value=0,
            max_value=1_000_000,
            created_by="test",
        )
        # Jamais decide_point() : le point reste non validé, confiance = 0.
        _record(connection, tenant, 60.0, T0, point_id=other_trigger_id)
        _activate_mode(connection, tenant, tenant["target_point_id"], "automatic")
        _activate_rule(
            connection, _create_rule(connection, tenant, trigger_point_id=str(other_trigger_id))
        )
        results = evaluate_automation_rules(connection, tenant_id=tenant["tenant_id"], at=T0)
        assert results[0]["status"] == "blocked_untrusted_data"


def test_point_cible_non_commandable_est_bloque(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        # Le point déclencheur lui-même n'est jamais mappé en relais simulé :
        # le viser comme cible doit être refusé par la commandabilité.
        _activate_mode(connection, tenant, tenant["trigger_point_id"], "automatic")
        _record(connection, tenant, 60.0, T0)
        _activate_rule(
            connection,
            _create_rule(connection, tenant, target_point_id=str(tenant["trigger_point_id"])),
        )
        results = evaluate_automation_rules(connection, tenant_id=tenant["tenant_id"], at=T0)
        assert results[0]["status"] == "blocked"
        assert results[0]["detail"] == "COMMAND_POINT_NOT_CONTROLLABLE"


def test_une_policy_qui_exclut_le_role_automation_bloque_le_declenchement(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_mode(connection, tenant, tenant["target_point_id"], "automatic")
        policy_version = create_version(
            connection,
            tenant_id=tenant["tenant_id"],
            config_type=COMMAND_POINT_POLICY,
            subject_key=str(tenant["target_point_id"]),
            content={"allowed_roles": ["technicien"]},
            author="responsable",
            reason="test",
        )
        activate_version(
            connection, version_id=policy_version, activated_by="admin_tenant", activated_at=T0
        )
        _record(connection, tenant, 60.0, T0)
        _activate_rule(connection, _create_rule(connection, tenant))
        results = evaluate_automation_rules(connection, tenant_id=tenant["tenant_id"], at=T0)
        assert results[0]["status"] == "blocked"
        assert results[0]["detail"] == "COMMAND_POLICY_ROLE_NOT_ALLOWED"
        assert list_commands_for_point(connection, point_id=tenant["target_point_id"]) == []


def test_anti_emballement_bloque_un_second_declenchement_trop_rapproche(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_mode(connection, tenant, tenant["target_point_id"], "automatic")
        _record(connection, tenant, 60.0, T0)
        _activate_rule(connection, _create_rule(connection, tenant))
        first = evaluate_automation_rules(connection, tenant_id=tenant["tenant_id"], at=T0)
        assert first[0]["status"] == "fired"

        second = evaluate_automation_rules(
            connection, tenant_id=tenant["tenant_id"], at=T0 + timedelta(minutes=1)
        )
        assert second[0]["status"] == "cooldown"
        assert len(list_commands_for_point(connection, point_id=tenant["target_point_id"])) == 1


def test_le_cooldown_expire_autorise_un_nouveau_declenchement(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _activate_mode(connection, tenant, tenant["target_point_id"], "automatic")
        _record(connection, tenant, 60.0, T0)
        _activate_rule(connection, _create_rule(connection, tenant))
        first = evaluate_automation_rules(connection, tenant_id=tenant["tenant_id"], at=T0)
        assert first[0]["status"] == "fired"

        later = T0 + timedelta(minutes=10)
        _record(connection, tenant, 60.0, later)
        second = evaluate_automation_rules(connection, tenant_id=tenant["tenant_id"], at=later)
        assert second[0]["status"] == "fired"
        assert len(list_commands_for_point(connection, point_id=tenant["target_point_id"])) == 2


def test_isolation_tenant_sur_les_regles_d_automatisation(tenant):
    other_tenant = create_tenant_with_energy_point("ClientAutomatisationAutre")
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant["tenant_id"])
            _activate_mode(connection, tenant, tenant["target_point_id"], "automatic")
            _record(connection, tenant, 60.0, T0)
            _activate_rule(connection, _create_rule(connection, tenant))

        with engine.begin() as connection:
            set_tenant_context(connection, other_tenant["tenant_id"])
            results = evaluate_automation_rules(
                connection, tenant_id=other_tenant["tenant_id"], at=T0
            )
        assert results == []
    finally:
        cleanup_tenant(other_tenant)
