"""Domaine de découverte BACnet (`app.bacnet_discovery`) contre un vrai
appareil simulé (BACnet Lab) et une vraie base — palier SIMULATOR_TESTED.
Couvre la persistance des lots/propositions, la correspondance sémantique
réelle bout en bout, le cycle accepter/rejeter, les doublons sur reprise de
scan et l'isolation des tenants (règle non négociable 2)."""

import uuid

import pytest
from sqlalchemy import text

from app.bacnet_discovery import (
    DiscoveryProposalConflict,
    DiscoveryProposalNotFound,
    accept_proposal,
    get_batch,
    list_proposals,
    reason_message,
    reject_proposal,
    run_discovery,
)
from app.db import engine
from app.tenancy import set_tenant_context
from tests.bacnet_lab import BacnetLab
from tests.tenant_cleanup import purge_tenant

ADDRESS = "127.0.0.1:47831"
DEVICE_INSTANCE = 5011
UNREACHABLE = "127.0.0.1:47899"


@pytest.fixture(scope="module", autouse=True)
def lab():
    simulator = BacnetLab(ADDRESS, device_instance=DEVICE_INSTANCE)
    simulator.start()
    yield simulator
    simulator.stop()


def _create_tenant_with_equipment(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    equipment_id = uuid.uuid4()
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
                "VALUES (:id, :tenant_id, :site_id, 'cta-01', 'CTA Test')"
            ),
            {"id": equipment_id, "tenant_id": tenant_id, "site_id": site_id},
        )
    return {"tenant_id": tenant_id, "site_id": site_id, "equipment_id": equipment_id}


@pytest.fixture
def tenant():
    created = _create_tenant_with_equipment("ClientBacnetDiscovery")
    yield created
    purge_tenant(created["tenant_id"])


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant_with_equipment("ClientBacnetDiscoveryA")
    tenant_b = _create_tenant_with_equipment("ClientBacnetDiscoveryB")
    yield tenant_a, tenant_b
    purge_tenant(tenant_a["tenant_id"])
    purge_tenant(tenant_b["tenant_id"])


def _scan(tenant: dict, *, address: str = ADDRESS, timeout: float = 3.0) -> uuid.UUID:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return run_discovery(
            connection,
            tenant_id=tenant["tenant_id"],
            equipment_id=tenant["equipment_id"],
            address=address,
            scanned_by="test",
            timeout=timeout,
        )


def test_run_discovery_produit_un_lot_pret_avec_une_proposition_par_point(tenant):
    batch_id = _scan(tenant)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        batch = get_batch(connection, batch_id)
        proposals = list_proposals(connection, batch_id=batch_id)

    assert batch["status"] == "ready"
    assert batch["error_code"] is None
    assert batch["device_instance"] == DEVICE_INSTANCE
    assert batch["object_count"] == 8
    assert batch["proposal_count"] == 8
    assert batch["duplicate_count"] == 0
    assert len(proposals) == 8
    assert {p["status"] for p in proposals} == {"proposed"}


def test_run_discovery_propose_des_correspondances_sensees_jamais_inventees(tenant):
    batch_id = _scan(tenant)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        proposals = list_proposals(connection, batch_id=batch_id)
    by_name = {p["object_name"]: p for p in proposals}

    temperature = by_name["T Depart CTA"]
    assert temperature["proposed_point_class"] == "temperature_sensor"
    assert temperature["proposed_unit"] == "Cel"
    assert float(temperature["confidence"]) == pytest.approx(0.9)
    assert temperature["reason_code"] == "BACNET_UNITS_TEMPERATURE"

    setpoint = by_name["Consigne Depart CTA"]
    assert setpoint["proposed_point_class"] == "temperature_setpoint"
    assert setpoint["reason_code"] == "BACNET_UNITS_TEMPERATURE_SETPOINT"

    fault = by_name["Defaut General CTA"]
    assert fault["proposed_point_class"] == "fault_status"

    run_status = by_name["Marche Ventilateur"]
    assert run_status["proposed_point_class"] == "run_status"

    enable_status = by_name["Autorisation Marche"]
    assert enable_status["proposed_point_class"] == "enable_status"

    # Sans unité utilisable ni mot-clé reconnu : jamais de correspondance
    # inventée, la proposition reste à revoir par une personne.
    unclassified = by_name["AI-07"]
    assert unclassified["proposed_point_class"] is None
    assert unclassified["confidence"] is None
    assert unclassified["reason_code"] == "NO_RELIABLE_SIGNAL"

    # Aucune classe multi-état générique dans le vocabulaire : toujours à
    # revoir, jamais une classe inventée pour ce type de valeur.
    mode = by_name["Mode CTA"]
    assert mode["proposed_point_class"] is None
    assert mode["reason_code"] == "MULTISTATE_NOT_YET_MAPPED"
    assert mode["states"] == {"1": "Arret", "2": "Confort", "3": "Reduit"}


def test_reason_message_est_traduit_dans_les_deux_langues():
    assert reason_message("BACNET_UNITS_TEMPERATURE", "fr") != reason_message(
        "BACNET_UNITS_TEMPERATURE", "en"
    )
    assert reason_message("BACNET_UNITS_TEMPERATURE", "fr")
    # Un code inconnu retombe sur la raison « à revoir », jamais une erreur.
    assert reason_message("CODE_INEXISTANT") == reason_message("NO_RELIABLE_SIGNAL")


def test_run_discovery_appareil_injoignable_referme_le_lot_en_echec(tenant):
    batch_id = _scan(tenant, address=UNREACHABLE, timeout=0.5)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        batch = get_batch(connection, batch_id)

    assert batch["status"] == "failed"
    assert batch["error_code"] == "BACNET_DEVICE_UNREACHABLE"
    assert batch["object_count"] is None
    assert batch["proposal_count"] is None


def test_rescan_marque_les_objets_deja_acceptes_comme_doublons(tenant):
    first_batch_id = _scan(tenant)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        proposals = list_proposals(connection, batch_id=first_batch_id)
        temperature = next(p for p in proposals if p["object_name"] == "T Depart CTA")
        accept_proposal(
            connection,
            tenant_id=tenant["tenant_id"],
            proposal_id=temperature["id"],
            decided_by="test",
        )

    second_batch_id = _scan(tenant)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        second_batch = get_batch(connection, second_batch_id)
        second_proposals = list_proposals(connection, batch_id=second_batch_id)

    assert second_batch["duplicate_count"] == 1
    assert second_batch["proposal_count"] == 7
    by_name = {p["object_name"]: p for p in second_proposals}
    assert by_name["T Depart CTA"]["status"] == "duplicate"
    assert by_name["P Refoulement"]["status"] == "proposed"


def test_accept_proposal_cree_un_vrai_point_par_le_meme_chemin_que_la_saisie_manuelle(tenant):
    batch_id = _scan(tenant)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        proposals = list_proposals(connection, batch_id=batch_id)
        temperature = next(p for p in proposals if p["object_name"] == "T Depart CTA")

        accepted = accept_proposal(
            connection,
            tenant_id=tenant["tenant_id"],
            proposal_id=temperature["id"],
            decided_by="alice",
        )

        assert accepted["status"] == "accepted"
        assert accepted["decided_by"] == "alice"
        assert accepted["created_point_id"] is not None

        point = connection.execute(
            text(
                "SELECT point_class, unit, functional_location_id, mapping_status, "
                "mapping_confidence FROM points WHERE id = :id"
            ),
            {"id": accepted["created_point_id"]},
        ).mappings().one()

    assert point["point_class"] == "temperature_sensor"
    assert point["unit"] == "Cel"
    assert point["functional_location_id"] == tenant["equipment_id"]
    # Accepter une découverte n'est pas la commissionner : la validation
    # reste une étape séparée.
    assert point["mapping_status"] == "proposed"
    assert point["mapping_confidence"] == pytest.approx(0.9)


def test_accept_proposal_permet_de_corriger_la_classe_avant_creation(tenant):
    batch_id = _scan(tenant)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        proposals = list_proposals(connection, batch_id=batch_id)
        unclassified = next(p for p in proposals if p["object_name"] == "AI-07")
        assert unclassified["proposed_point_class"] is None

        accepted = accept_proposal(
            connection,
            tenant_id=tenant["tenant_id"],
            proposal_id=unclassified["id"],
            decided_by="alice",
            point_class="pressure_sensor",
            unit="kPa",
            code="ai07-manuel",
            name="Capteur corrige manuellement",
        )

        point = connection.execute(
            text("SELECT point_class, unit, code, name FROM points WHERE id = :id"),
            {"id": accepted["created_point_id"]},
        ).mappings().one()

    assert point["point_class"] == "pressure_sensor"
    assert point["unit"] == "kPa"
    assert point["code"] == "ai07-manuel"
    assert point["name"] == "Capteur corrige manuellement"


def test_accept_proposal_deja_decidee_est_un_conflit(tenant):
    batch_id = _scan(tenant)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        proposal_id = list_proposals(connection, batch_id=batch_id)[0]["id"]
        accept_proposal(
            connection, tenant_id=tenant["tenant_id"], proposal_id=proposal_id, decided_by="test"
        )

        with pytest.raises(DiscoveryProposalConflict):
            accept_proposal(
                connection,
                tenant_id=tenant["tenant_id"],
                proposal_id=proposal_id,
                decided_by="test",
            )


def test_reject_proposal_exige_une_raison_et_est_conservee(tenant):
    batch_id = _scan(tenant)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        proposal_id = list_proposals(connection, batch_id=batch_id)[0]["id"]

        rejected = reject_proposal(
            connection,
            proposal_id=proposal_id,
            decided_by="test",
            reason="Point deja instrumente par un autre moyen",
        )

        assert rejected["status"] == "rejected"
        assert rejected["rejection_reason"] == "Point deja instrumente par un autre moyen"

        with pytest.raises(DiscoveryProposalConflict):
            reject_proposal(
                connection, proposal_id=proposal_id, decided_by="test", reason="deuxieme essai"
            )


def test_decider_une_proposition_inexistante_leve_une_erreur_explicite(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(DiscoveryProposalNotFound):
            accept_proposal(
                connection,
                tenant_id=tenant["tenant_id"],
                proposal_id=uuid.uuid4(),
                decided_by="test",
            )
        with pytest.raises(DiscoveryProposalNotFound):
            reject_proposal(
                connection, proposal_id=uuid.uuid4(), decided_by="test", reason="x"
            )


def test_isolation_des_tenants_un_autre_tenant_ne_voit_aucun_lot_ni_proposition(two_tenants):
    tenant_a, tenant_b = two_tenants
    batch_id = _scan(tenant_a)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b["tenant_id"])
        batch_seen_by_b = get_batch(connection, batch_id)
        proposals_seen_by_b = list_proposals(connection, batch_id=batch_id)

    assert batch_seen_by_b is None
    assert proposals_seen_by_b == []
