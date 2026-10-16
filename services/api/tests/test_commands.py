"""Pipeline de commande (app/commands.py) : exception strictement limitée à
un appareil simulé — voir CLAUDE.md. Tests directs sur les fonctions
métier, sans passer par l'API HTTP (voir tests/test_commands_api.py pour ça).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.command_policies import COMMAND_POINT_POLICY, COMMAND_ROLES
from app.commands import (
    PENDING_EXPIRY,
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
    mark_command_timed_out,
)
from app.config_versions import activate_version, create_version
from app.db import engine
from app.devices import provision_device
from app.events import list_events_for_subject
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
            requester_roles=list(COMMAND_ROLES),
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
                requester_roles=list(COMMAND_ROLES),
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
                requester_roles=list(COMMAND_ROLES),
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
            requester_roles=list(COMMAND_ROLES),
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
            requester_roles=list(COMMAND_ROLES),
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
            requester_roles=list(COMMAND_ROLES),
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
            requester_roles=list(COMMAND_ROLES),
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
            requester_roles=list(COMMAND_ROLES),
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
            requester_roles=list(COMMAND_ROLES),
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


# --- Audit sécurité du 16/10/2026 (pistes Siemens SSA-333035) : une
# commande restée en attente pendant une coupure prolongée de l'automate
# ne doit ni être rejouée telle quelle, ni contourner une policy devenue
# entre-temps plus stricte — voir claim_pending_commands. ----------------


def _backdate_created_at(connection, command_id: uuid.UUID, created_at: datetime) -> None:
    """`commands.created_at` vient du serveur (`server_default=now()`),
    jamais du paramètre `at` de create_command — seul moyen réaliste de
    tester l'expiration sans dépendre de l'horloge réelle de la machine
    qui exécute les tests."""
    connection.execute(
        text("UPDATE commands SET created_at = :created_at WHERE id = :id"),
        {"created_at": created_at, "id": command_id},
    )


def test_une_commande_trop_longtemps_en_attente_expire_sans_etre_reclamee(commandable):
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
            requester_roles=list(COMMAND_ROLES),
        )
        _backdate_created_at(connection, command_id, T0)

        # L'automate revient trop tard : la commande est restée "pending"
        # plus longtemps que PENDING_EXPIRY, jamais réclamée avant.
        claimed = claim_pending_commands(
            connection,
            equipment_id=commandable["location_id"],
            edge_device_id=device_id,
            at=T0 + PENDING_EXPIRY + timedelta(seconds=1),
        )
        command = get_command(connection, command_id)
        events = list_events_for_subject(connection, subject_type="command", subject_id=command_id)

    assert claimed == []
    assert command["status"] == "failed"
    assert command["failure_reason"] == "COMMAND_EXPIRED"
    assert any(event["event_type"] == "COMMAND_FAILED" for event in events)


def test_une_commande_pas_encore_expiree_est_reclamee_normalement(commandable):
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
            requester_roles=list(COMMAND_ROLES),
        )
        _backdate_created_at(connection, command_id, T0)

        claimed = claim_pending_commands(
            connection,
            equipment_id=commandable["location_id"],
            edge_device_id=device_id,
            at=T0 + PENDING_EXPIRY - timedelta(seconds=1),
        )

    assert len(claimed) == 1
    assert claimed[0]["status"] == "sent"


def test_reclamation_revalide_la_policy_et_refuse_si_elle_s_est_durcie_entre_temps(commandable):
    """La commande est créée quand seul « technicien » est autorisé par la
    policy active. Avant que l'Edge ne la réclame, la policy est resserrée
    à « admin_tenant » seul (ex. un incident ailleurs a motivé une
    restriction) : la réclamation doit refuser, jamais exécuter une
    commande dont le rôle n'est plus habilité au moment où elle part
    réellement vers l'appareil."""
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        device_id, _ = provision_device(
            connection,
            tenant_id=commandable["tenant_id"],
            device_id="relais-test",
            created_by="test",
        )
        version_id = create_version(
            connection,
            tenant_id=commandable["tenant_id"],
            config_type=COMMAND_POINT_POLICY,
            subject_key=str(commandable["point_id"]),
            content={"allowed_roles": ["technicien"]},
            author="responsable",
            reason="test",
        )
        activate_version(
            connection, version_id=version_id, activated_by="responsable", activated_at=T0
        )

        command_id = create_command(
            connection,
            tenant_id=commandable["tenant_id"],
            point_id=commandable["point_id"],
            requested_value=1.0,
            requested_by="technicien-dupont",
            requester_roles=["technicien"],
        )

        # La policy se durcit avant que l'Edge ne réclame la commande.
        stricter_version_id = create_version(
            connection,
            tenant_id=commandable["tenant_id"],
            config_type=COMMAND_POINT_POLICY,
            subject_key=str(commandable["point_id"]),
            content={"allowed_roles": ["admin_tenant"]},
            author="responsable",
            reason="test",
        )
        activate_version(
            connection, version_id=stricter_version_id, activated_by="responsable", activated_at=T0
        )

        claimed = claim_pending_commands(
            connection, equipment_id=commandable["location_id"], edge_device_id=device_id, at=T0
        )
        command = get_command(connection, command_id)

    assert claimed == []
    assert command["status"] == "failed"
    assert command["failure_reason"] == "COMMAND_POLICY_ROLE_NOT_ALLOWED"


def test_reclamation_revalide_la_commandabilite_et_refuse_si_le_point_a_cesse_de_l_etre(
    commandable,
):
    """Entre la création de la commande et la réclamation, l'équipement
    bascule vers une configuration non simulée (ex. un vrai sdm120
    installé à la place) : la commande ne doit jamais partir vers un
    appareil réel sous couvert d'une vérification faite avant ce
    changement — règle non négociable 1."""
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
            requester_roles=list(COMMAND_ROLES),
        )

    # Le point n'est plus servi par un appareil simulé (nouvelle config active).
    activate_device_mapping(
        tenant_id=commandable["tenant_id"],
        equipment_id=commandable["location_id"],
        host="127.0.0.1",
        port=5020,
        device_type="sdm120",
        points=[{"point_id": str(commandable["point_id"]), "register_name": "total_active_energy"}],
    )

    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        claimed = claim_pending_commands(
            connection, equipment_id=commandable["location_id"], edge_device_id=device_id, at=T0
        )
        command = get_command(connection, command_id)

    assert claimed == []
    assert command["status"] == "failed"
    assert command["failure_reason"] == "COMMAND_POINT_NOT_CONTROLLABLE"


def test_reclamation_d_un_equipement_n_affecte_pas_les_commandes_d_un_autre(commandable):
    """Expirer/refuser une commande au moment de la réclamation ne doit
    jamais déborder sur un autre équipement : la coupure (ou la policy
    durcie) d'un automate ne bloque jamais la commande d'un autre."""
    second = create_tenant_with_energy_point("ClientCommandesSecond")
    activate_device_mapping(
        tenant_id=second["tenant_id"],
        equipment_id=second["location_id"],
        host="127.0.0.1",
        port=5922,
        device_type="simulated_relay",
        points=[{"point_id": str(second["point_id"]), "register_name": "relay_state"}],
    )
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, commandable["tenant_id"])
            device_id, _ = provision_device(
                connection,
                tenant_id=commandable["tenant_id"],
                device_id="relais-expire",
                created_by="test",
            )
            expiring_command_id = create_command(
                connection,
                tenant_id=commandable["tenant_id"],
                point_id=commandable["point_id"],
                requested_value=1.0,
                requested_by="mohamed",
                requester_roles=list(COMMAND_ROLES),
            )
            _backdate_created_at(connection, expiring_command_id, T0)

        with engine.begin() as connection:
            set_tenant_context(connection, second["tenant_id"])
            second_device_id, _ = provision_device(
                connection,
                tenant_id=second["tenant_id"],
                device_id="relais-frais",
                created_by="test",
            )
            create_command(
                connection,
                tenant_id=second["tenant_id"],
                point_id=second["point_id"],
                requested_value=1.0,
                requested_by="mohamed",
                requester_roles=list(COMMAND_ROLES),
            )

        at = T0 + PENDING_EXPIRY + timedelta(seconds=1)
        with engine.begin() as connection:
            set_tenant_context(connection, commandable["tenant_id"])
            expired_claim = claim_pending_commands(
                connection,
                equipment_id=commandable["location_id"],
                edge_device_id=device_id,
                at=at,
            )
        with engine.begin() as connection:
            set_tenant_context(connection, second["tenant_id"])
            fresh_claim = claim_pending_commands(
                connection,
                equipment_id=second["location_id"],
                edge_device_id=second_device_id,
                at=at,
            )
    finally:
        cleanup_tenant(second)

    assert expired_claim == []
    assert len(fresh_claim) == 1
    assert fresh_claim[0]["status"] == "sent"


def test_chaque_etape_produit_un_evenement(commandable):
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
            requester_roles=list(COMMAND_ROLES),
            at=T0,
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
        events = list_events_for_subject(connection, subject_type="command", subject_id=command_id)

    # Même horodatage pour les trois (T0) : l'ordre entre elles n'est pas
    # garanti, seul l'ensemble compte ici.
    assert {e["event_type"] for e in events} == {
        "COMMAND_REQUESTED",
        "COMMAND_DISPATCHED",
        "COMMAND_VERIFIED",
    }


def test_commande_envoyee_depuis_trop_longtemps_devient_timed_out(commandable):
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
            requester_roles=list(COMMAND_ROLES),
            at=T0,
        )
        claim_pending_commands(
            connection, equipment_id=commandable["location_id"], edge_device_id=device_id, at=T0
        )

        too_soon = T0 + UNCONFIRMED_AFTER - timedelta(seconds=1)
        assert mark_command_timed_out(connection, command_id=command_id, at=too_soon) is None

        late = T0 + UNCONFIRMED_AFTER + timedelta(seconds=1)
        timed_out = mark_command_timed_out(connection, command_id=command_id, at=late)
        assert timed_out["status"] == "timed_out"
        assert timed_out["failure_reason"] == "COMMAND_TIMED_OUT"

        # Idempotente : un second appel ne fait rien (déjà dans un état terminal).
        assert mark_command_timed_out(connection, command_id=command_id, at=late) is None

        events = list_events_for_subject(connection, subject_type="command", subject_id=command_id)
    assert [e["event_type"] for e in events if e["event_type"] == "COMMAND_TIMED_OUT"] == [
        "COMMAND_TIMED_OUT"
    ]
