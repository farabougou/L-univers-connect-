"""Planification de commande (app/scheduled_commands.py) : priorité
« planification » de la feuille de route V2. Tests directs sur les
fonctions métier — voir tests/test_scheduled_commands_api.py pour l'API."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.command_policies import COMMAND_POINT_POLICY, COMMAND_ROLES
from app.commands import CommandNotAllowed, get_command
from app.config_versions import activate_version, create_version
from app.db import engine
from app.events import list_events_for_subject
from app.scheduled_commands import (
    ScheduledCommandConflict,
    ScheduledCommandInThePast,
    ScheduledCommandNotFound,
    cancel_scheduled_command,
    dispatch_due_scheduled_commands,
    get_scheduled_command,
    list_scheduled_commands_for_point,
    schedule_command,
)
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code
from tests.modbus_fixtures import (
    activate_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_point,
)

T0 = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


@pytest.fixture
def commandable():
    created = create_tenant_with_energy_point("ClientPlanificationCommande")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=5921,
        device_type="simulated_relay",
        points=[{"point_id": str(created["point_id"]), "register_name": "relay_state"}],
    )
    yield created
    cleanup_tenant(created)


@pytest.fixture
def not_commandable():
    created = create_tenant_with_energy_point("ClientPlanificationNonCommandable")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=5020,
        points=[{"point_id": str(created["point_id"]), "register_name": "total_active_energy"}],
    )
    yield created
    cleanup_tenant(created)


def test_planifier_une_commande_sur_un_point_pilotable(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        scheduled_id = schedule_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            scheduled_for=T0 + timedelta(hours=1),
            requested_by="mohamed",
            requester_roles=list(COMMAND_ROLES),
            at=T0,
        )
        scheduled = get_scheduled_command(connection, scheduled_id)

    assert scheduled["status"] == "pending"
    assert scheduled["requested_value"] == pytest.approx(1.0)
    assert scheduled["command_id"] is None


def test_refuse_de_planifier_dans_le_passe(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        with raises_code(ScheduledCommandInThePast, "SCHEDULED_COMMAND_IN_THE_PAST"):
            schedule_command(
                connection,
                tenant_id=commandable["tenant_id"],
                point_id=commandable["point_id"],
                requested_value=1.0,
                scheduled_for=T0 - timedelta(minutes=1),
                requested_by="mohamed",
                requester_roles=list(COMMAND_ROLES),
                at=T0,
            )


def test_refuse_de_planifier_sur_un_point_non_pilotable(not_commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, not_commandable["tenant_id"])
        with raises_code(CommandNotAllowed, "COMMAND_POINT_NOT_CONTROLLABLE"):
            schedule_command(
                connection,
                tenant_id=not_commandable["tenant_id"],
                point_id=not_commandable["point_id"],
                requested_value=1.0,
                scheduled_for=T0 + timedelta(hours=1),
                requested_by="mohamed",
                requester_roles=list(COMMAND_ROLES),
                at=T0,
            )


def test_annuler_une_commande_planifiee(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        scheduled_id = schedule_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            scheduled_for=T0 + timedelta(hours=1),
            requested_by="mohamed",
            requester_roles=list(COMMAND_ROLES),
            at=T0,
        )
        cancelled = cancel_scheduled_command(
            connection, scheduled_command_id=scheduled_id, cancelled_by="responsable", at=T0
        )
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_by"] == "responsable"


def test_annuler_deux_fois_est_refuse(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        scheduled_id = schedule_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            scheduled_for=T0 + timedelta(hours=1),
            requested_by="mohamed",
            requester_roles=list(COMMAND_ROLES),
            at=T0,
        )
        cancel_scheduled_command(
            connection, scheduled_command_id=scheduled_id, cancelled_by="responsable", at=T0
        )
        with raises_code(ScheduledCommandConflict, "SCHEDULED_COMMAND_NOT_CANCELLABLE"):
            cancel_scheduled_command(
                connection, scheduled_command_id=scheduled_id, cancelled_by="responsable", at=T0
            )


def test_annuler_une_commande_inconnue_est_signale(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        with raises_code(ScheduledCommandNotFound, "SCHEDULED_COMMAND_NOT_FOUND"):
            cancel_scheduled_command(
                connection,
                scheduled_command_id=uuid.uuid4(),
                cancelled_by="responsable",
                at=T0,
            )


def test_lister_les_commandes_planifiees_d_un_point(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        schedule_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            scheduled_for=T0 + timedelta(hours=1),
            requested_by="mohamed",
            requester_roles=list(COMMAND_ROLES),
            at=T0,
        )
        schedule_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=0.0,
            scheduled_for=T0 + timedelta(hours=2),
            requested_by="mohamed",
            requester_roles=list(COMMAND_ROLES),
            at=T0,
        )
        listed = list_scheduled_commands_for_point(connection, point_id=commandable["point_id"])
    assert len(listed) == 2
    assert listed[0]["requested_value"] == 0.0  # la plus tardive d'abord


# --- Déclenchement (app.scheduled_commands_sweep) ------------------------------------------


def test_une_commande_due_est_declenchee_et_cree_une_commande_reelle(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        scheduled_id = schedule_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            scheduled_for=T0 + timedelta(minutes=5),
            requested_by="mohamed",
            requester_roles=list(COMMAND_ROLES),
            at=T0,
        )
        results = dispatch_due_scheduled_commands(
            connection, tenant_id=commandable["tenant_id"], at=T0 + timedelta(minutes=10)
        )
        assert len(results) == 1
        assert results[0]["status"] == "dispatched"
        command_id = results[0]["command_id"]
        command = get_command(connection, command_id)
        assert command["requested_value"] == pytest.approx(1.0)
        assert command["requested_by"] == "mohamed"

        events = list_events_for_subject(
            connection, subject_type="scheduled_command", subject_id=scheduled_id
        )
    assert "SCHEDULED_COMMAND_DISPATCHED" in {e["event_type"] for e in events}


def test_une_commande_pas_encore_due_reste_en_attente(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        schedule_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            scheduled_for=T0 + timedelta(hours=5),
            requested_by="mohamed",
            requester_roles=list(COMMAND_ROLES),
            at=T0,
        )
        results = dispatch_due_scheduled_commands(
            connection, tenant_id=commandable["tenant_id"], at=T0 + timedelta(minutes=1)
        )
    assert results == []


def test_une_commande_due_mais_devenue_non_pilotable_echoue_sans_forcer(commandable):
    """Le point perd son mapping simulé entre la planification et le
    déclenchement (ex. l'équipement n'est plus en Virtual Commissioning) :
    le déclenchement doit échouer proprement, jamais contourner la règle
    non négociable 1 parce que la planification avait réussi hier."""
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        scheduled_id = schedule_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            scheduled_for=T0 + timedelta(minutes=5),
            requested_by="mohamed",
            requester_roles=list(COMMAND_ROLES),
            at=T0,
        )
        # Retire le mapping simulé : le point n'est plus commandable.
        connection.execute(
            text(
                "UPDATE config_versions SET status = 'retired' "
                "WHERE config_type = 'modbus_device_mapping' AND status = 'active'"
            )
        )

        results = dispatch_due_scheduled_commands(
            connection, tenant_id=commandable["tenant_id"], at=T0 + timedelta(minutes=10)
        )
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert results[0]["failure_reason"] == "COMMAND_POINT_NOT_CONTROLLABLE"
        assert results[0]["command_id"] is None

        still_pending = get_scheduled_command(connection, scheduled_id)
    assert still_pending["status"] == "failed"


def test_une_commande_due_mais_bloquee_par_une_nouvelle_policy_echoue(commandable):
    """La policy a changé entre la planification et le déclenchement : le
    rôle qui avait planifié n'est plus autorisé — le déclenchement doit le
    détecter, pas commander quand même."""
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        schedule_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            scheduled_for=T0 + timedelta(minutes=5),
            requested_by="mohamed",
            requester_roles=["technicien"],
            at=T0,
        )
        version_id = create_version(
            connection,
            tenant_id=commandable["tenant_id"],
            config_type=COMMAND_POINT_POLICY,
            subject_key=str(commandable["point_id"]),
            content={"allowed_roles": ["admin_tenant"]},
            author="responsable",
            reason="test",
        )
        activate_version(
            connection, version_id=version_id, activated_by="responsable", activated_at=T0
        )

        results = dispatch_due_scheduled_commands(
            connection, tenant_id=commandable["tenant_id"], at=T0 + timedelta(minutes=10)
        )
    assert results[0]["status"] == "failed"
    assert results[0]["failure_reason"] == "COMMAND_POLICY_ROLE_NOT_ALLOWED"


def test_isolation_tenant_sur_les_commandes_planifiees(commandable):
    other_tenant = create_tenant_with_energy_point("ClientPlanificationAutre")
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, commandable["tenant_id"])
            scheduled_id = schedule_command(
                connection,
                tenant_id=commandable["tenant_id"],
                point_id=commandable["point_id"],
                requested_value=1.0,
                scheduled_for=T0 + timedelta(hours=1),
                requested_by="mohamed",
                requester_roles=list(COMMAND_ROLES),
                at=T0,
            )

        with engine.begin() as connection:
            set_tenant_context(connection, other_tenant["tenant_id"])
            assert get_scheduled_command(connection, scheduled_id) is None
            assert (
                list_scheduled_commands_for_point(connection, point_id=commandable["point_id"])
                == []
            )
    finally:
        cleanup_tenant(other_tenant)
