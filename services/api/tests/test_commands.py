"""Pipeline de commande (app/commands.py) : exception strictement limitée à
un appareil simulé — voir CLAUDE.md. Tests directs sur les fonctions
métier, sans passer par l'API HTTP (voir tests/test_commands_api.py pour ça).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.commands import (
    UNCONFIRMED_AFTER,
    CommandConflict,
    CommandNotAllowed,
    CommandNotFound,
    acknowledge_command,
    claim_pending_commands,
    create_command,
    effective_status,
    get_command,
    list_commands_for_point,
)
from app.db import engine
from app.devices import provision_device
from app.tenancy import set_tenant_context
from tests.modbus_fixtures import (
    activate_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_point,
)

T0 = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


@pytest.fixture
def commandable():
    """Un point servi par un appareil explicitement simulé — le seul cas où
    une commande est acceptée."""
    created = create_tenant_with_energy_point("ClientCommandes")
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
    """Un point servi par le sdm120 (mesure réelle, non pilotable) : toute
    commande dessus doit être refusée."""
    created = create_tenant_with_energy_point("ClientNonCommandable")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=5020,
        points=[{"point_id": str(created["point_id"]), "register_name": "total_active_energy"}],
    )
    yield created
    cleanup_tenant(created)


def test_creer_une_commande_sur_un_point_pilote_par_un_appareil_simule(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        command_id = create_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            requested_by="mohamed",
        )
        command = get_command(connection, command_id)

    assert command["status"] == "pending"
    assert command["requested_value"] == pytest.approx(1.0)
    assert command["requested_by"] == "mohamed"


def test_refuse_une_commande_sur_un_point_non_pilotable(not_commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, not_commandable["tenant_id"])
        with pytest.raises(CommandNotAllowed) as info:
            create_command(
                connection,
                tenant_id=not_commandable["tenant_id"],
                point_id=not_commandable["point_id"],
                requested_value=1.0,
                requested_by="mohamed",
            )
    assert info.value.code == "COMMAND_POINT_NOT_CONTROLLABLE"


def test_refuse_une_commande_sur_un_point_sans_aucune_configuration(commandable):
    autre_point_id = uuid.uuid4()
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        with pytest.raises(CommandNotAllowed):
            create_command(
                connection,
                tenant_id=commandable["tenant_id"],
                point_id=autre_point_id,
                requested_value=1.0,
                requested_by="mohamed",
            )


def test_tenant_annonce_a_tort_ne_voit_pas_la_commande_de_l_autre(commandable):
    autre_tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Autre', :slug)"),
            {"id": autre_tenant_id, "slug": f"autre-cmd-{autre_tenant_id}"},
        )
        set_tenant_context(connection, commandable["tenant_id"])
        command_id = create_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            requested_by="mohamed",
        )

    with engine.begin() as connection:
        set_tenant_context(connection, autre_tenant_id)
        assert get_command(connection, command_id) is None
        assert list_commands_for_point(connection, point_id=commandable["point_id"]) == []

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": autre_tenant_id})


def test_claim_marque_sent_et_ne_renvoie_pas_deux_fois_la_meme_commande(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        device_id, _ = provision_device(
            connection,
            tenant_id=commandable["tenant_id"],
            device_id="relais-test",
            created_by="test",
        )
        create_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            requested_by="mohamed",
        )

        first_claim = claim_pending_commands(
            connection,
            equipment_id=commandable["location_id"],
            edge_device_id=device_id,
            at=T0,
        )
        second_claim = claim_pending_commands(
            connection,
            equipment_id=commandable["location_id"],
            edge_device_id=device_id,
            at=T0,
        )

    assert len(first_claim) == 1
    assert first_claim[0]["status"] == "sent"
    assert second_claim == []


def test_acquittement_reussi_avec_valeur_conforme_est_verifie(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        device_id, _ = provision_device(
            connection,
            tenant_id=commandable["tenant_id"],
            device_id="relais-test",
            created_by="test",
        )
        command_id = create_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            requested_by="mohamed",
        )
        claim_pending_commands(
            connection, equipment_id=commandable["location_id"], edge_device_id=device_id, at=T0
        )
        acknowledged = acknowledge_command(
            connection,
            command_id=command_id,
            success=True,
            actual_value=1.0,
            failure_reason=None,
            at=T0,
        )

    assert acknowledged["status"] == "verified"
    assert acknowledged["verified_at"] == T0
    assert acknowledged["failure_reason"] is None


def test_acquittement_avec_valeur_differente_echoue(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        device_id, _ = provision_device(
            connection,
            tenant_id=commandable["tenant_id"],
            device_id="relais-test",
            created_by="test",
        )
        command_id = create_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            requested_by="mohamed",
        )
        claim_pending_commands(
            connection, equipment_id=commandable["location_id"], edge_device_id=device_id, at=T0
        )
        acknowledged = acknowledge_command(
            connection,
            command_id=command_id,
            success=True,
            actual_value=0.0,
            failure_reason=None,
            at=T0,
        )

    assert acknowledged["status"] == "failed"
    assert acknowledged["failure_reason"] == "ACTUAL_STATE_MISMATCH"
    assert acknowledged["verified_at"] is None


def test_acquittement_d_echec_declare_par_l_edge(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        device_id, _ = provision_device(
            connection,
            tenant_id=commandable["tenant_id"],
            device_id="relais-test",
            created_by="test",
        )
        command_id = create_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            requested_by="mohamed",
        )
        claim_pending_commands(
            connection, equipment_id=commandable["location_id"], edge_device_id=device_id, at=T0
        )
        acknowledged = acknowledge_command(
            connection,
            command_id=command_id,
            success=False,
            actual_value=None,
            failure_reason="MODBUS_WRITE_ERROR",
            at=T0,
        )

    assert acknowledged["status"] == "failed"
    assert acknowledged["failure_reason"] == "MODBUS_WRITE_ERROR"


def test_acquitter_deux_fois_la_meme_commande_est_refuse(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        device_id, _ = provision_device(
            connection,
            tenant_id=commandable["tenant_id"],
            device_id="relais-test",
            created_by="test",
        )
        command_id = create_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            requested_by="mohamed",
        )
        claim_pending_commands(
            connection, equipment_id=commandable["location_id"], edge_device_id=device_id, at=T0
        )
        acknowledge_command(
            connection,
            command_id=command_id,
            success=True,
            actual_value=1.0,
            failure_reason=None,
            at=T0,
        )
        with pytest.raises(CommandConflict):
            acknowledge_command(
                connection,
                command_id=command_id,
                success=True,
                actual_value=1.0,
                failure_reason=None,
                at=T0,
            )


def test_acquitter_une_commande_inconnue_est_signale(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        with pytest.raises(CommandNotFound):
            acknowledge_command(
                connection,
                command_id=uuid.uuid4(),
                success=True,
                actual_value=1.0,
                failure_reason=None,
                at=T0,
            )


def test_statut_effectif_devient_unconfirmed_apres_le_delai():
    sent_command = {"status": "sent", "sent_at": T0}
    just_after = T0 + UNCONFIRMED_AFTER + timedelta(seconds=1)
    just_before = T0 + UNCONFIRMED_AFTER - timedelta(seconds=1)

    assert effective_status(sent_command, now=just_before) == "sent"
    assert effective_status(sent_command, now=just_after) == "unconfirmed"


def test_statut_effectif_ne_change_pas_les_statuts_terminaux():
    verified_command = {"status": "verified", "sent_at": T0}
    assert effective_status(verified_command, now=T0 + timedelta(days=1)) == "verified"
