"""Balayage périodique du moteur d'automatisation (app/automation_rules_sweep.py) :
même principe que app/supervision_sweep.py et app/scheduled_commands_sweep.py."""

from datetime import UTC, datetime
from unittest.mock import patch

from sqlalchemy import text

from app.automation_rules import AUTOMATION_RULE
from app.automation_rules_sweep import sweep_once
from app.config_versions import activate_version, create_version
from app.db import engine
from app.point_control_mode import POINT_CONTROL_MODE
from app.points import create_point, decide_point, get_point
from app.telemetry import record_measurement
from app.tenancy import set_tenant_context
from tests.modbus_fixtures import (
    activate_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_point,
)

T0 = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


def _commandable_tenant(name: str) -> dict:
    created = create_tenant_with_energy_point(name)
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
    created["target_point_id"] = target_point_id
    return created


def _ready_to_fire(tenant: dict) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        mode_version = create_version(
            connection,
            tenant_id=tenant["tenant_id"],
            config_type=POINT_CONTROL_MODE,
            subject_key=str(tenant["target_point_id"]),
            content={"mode": "automatic"},
            author="responsable",
            reason="test",
        )
        activate_version(
            connection, version_id=mode_version, activated_by="admin_tenant", activated_at=T0
        )
        point = get_point(connection, tenant["point_id"])
        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=point,
            value=60.0,
            measured_at=T0,
            origin="simulated",
            source="simulator",
            received_at=T0,
        )
        rule_version = create_version(
            connection,
            tenant_id=tenant["tenant_id"],
            config_type=AUTOMATION_RULE,
            subject_key=f"rule:{tenant['point_id']}",
            content={
                "title": "Règle de test",
                "trigger_point_id": str(tenant["point_id"]),
                "operator": ">",
                "threshold": 50.0,
                "target_point_id": str(tenant["target_point_id"]),
                "requested_value": 1.0,
            },
            author="responsable",
            reason="test",
        )
        activate_version(
            connection, version_id=rule_version, activated_by="admin_tenant", activated_at=T0
        )


def test_le_balayage_declenche_une_regle_prete_sans_lecture_utilisateur():
    tenant = _commandable_tenant("ClientBalayageAutomatisation")
    try:
        _ready_to_fire(tenant)
        summary = sweep_once(engine, at=T0)
        assert summary["fired"] >= 1

        with engine.begin() as connection:
            set_tenant_context(connection, tenant["tenant_id"])
            status = connection.execute(
                text("SELECT status FROM commands WHERE point_id = :point_id"),
                {"point_id": tenant["target_point_id"]},
            ).scalar()
        assert status == "pending"
    finally:
        cleanup_tenant(tenant)


def test_un_tenant_en_erreur_n_empeche_pas_le_balayage_des_autres():
    tenant_a = _commandable_tenant("ClientBalayageAutoA")
    tenant_b = _commandable_tenant("ClientBalayageAutoB")
    try:
        with engine.connect() as connection:
            total_tenants = connection.execute(text("SELECT count(*) FROM tenants")).scalar()

        def _boom_for_a(connection, *, tenant_id, at):
            if tenant_id == tenant_a["tenant_id"]:
                raise RuntimeError("panne simulée")
            return []

        with patch(
            "app.automation_rules_sweep.evaluate_automation_rules", side_effect=_boom_for_a
        ) as mock_evaluate:
            summary = sweep_once(engine, at=T0)

        called_tenant_ids = {call.kwargs["tenant_id"] for call in mock_evaluate.call_args_list}
        assert {tenant_a["tenant_id"], tenant_b["tenant_id"]} <= called_tenant_ids
        assert summary["tenants_failed"] >= 1
        assert summary["tenants_ok"] + summary["tenants_failed"] == total_tenants
    finally:
        cleanup_tenant(tenant_a)
        cleanup_tenant(tenant_b)
