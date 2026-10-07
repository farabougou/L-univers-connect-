"""Balayage périodique des commandes planifiées (app/scheduled_commands_sweep.py) :
une commande planifiée doit se déclencher même si personne ne consulte
l'application au moment voulu (même principe que app/supervision_sweep.py)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import text

from app.command_policies import COMMAND_ROLES
from app.db import engine
from app.scheduled_commands import schedule_command
from app.scheduled_commands_sweep import sweep_once
from app.tenancy import set_tenant_context
from tests.modbus_fixtures import (
    activate_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_point,
)

T0 = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _commandable_tenant(name: str) -> dict:
    created = create_tenant_with_energy_point(name)
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=5921,
        device_type="simulated_relay",
        points=[{"point_id": str(created["point_id"]), "register_name": "relay_state"}],
    )
    return created


def test_le_balayage_declenche_une_commande_due_sans_lecture_utilisateur():
    tenant = _commandable_tenant("ClientBalayagePlanification")
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant["tenant_id"])
            schedule_command(
                connection,
                tenant_id=tenant["tenant_id"],
                point_id=tenant["point_id"],
                requested_value=1.0,
                scheduled_for=T0 + timedelta(minutes=5),
                requested_by="mohamed",
                requester_roles=list(COMMAND_ROLES),
                at=T0,
            )

        summary = sweep_once(engine, at=T0 + timedelta(minutes=10))
        assert summary["dispatched"] >= 1

        with engine.begin() as connection:
            set_tenant_context(connection, tenant["tenant_id"])
            status = connection.execute(
                text("SELECT status FROM scheduled_commands WHERE point_id = :point_id"),
                {"point_id": tenant["point_id"]},
            ).scalar()
        assert status == "dispatched"
    finally:
        cleanup_tenant(tenant)


def test_un_tenant_en_erreur_n_empeche_pas_le_balayage_des_autres():
    tenant_a = _commandable_tenant("ClientBalayagePlanifA")
    tenant_b = _commandable_tenant("ClientBalayagePlanifB")
    try:
        with engine.connect() as connection:
            total_tenants = connection.execute(text("SELECT count(*) FROM tenants")).scalar()

        def _boom_for_a(connection, *, tenant_id, at):
            if tenant_id == tenant_a["tenant_id"]:
                raise RuntimeError("panne simulée")
            return []

        with patch(
            "app.scheduled_commands_sweep.dispatch_due_scheduled_commands",
            side_effect=_boom_for_a,
        ) as mock_dispatch:
            summary = sweep_once(engine, at=T0)

        called_tenant_ids = {call.kwargs["tenant_id"] for call in mock_dispatch.call_args_list}
        assert {tenant_a["tenant_id"], tenant_b["tenant_id"]} <= called_tenant_ids
        assert summary["tenants_failed"] >= 1
        assert summary["tenants_ok"] + summary["tenants_failed"] == total_tenants
    finally:
        cleanup_tenant(tenant_a)
        cleanup_tenant(tenant_b)
