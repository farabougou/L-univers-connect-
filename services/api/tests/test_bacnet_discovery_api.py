"""API de découverte BACnet (`app.routers.bacnet_discovery`) : scan, lots,
propositions, acceptation/rejet — rôles, isolation des tenants, appareil
injoignable. Palier SIMULATOR_TESTED (vrai appareil BACnet Lab derrière
l'appel HTTP)."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.bacnet_lab import BacnetLab
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)

ADDRESS = "127.0.0.1:47832"
DEVICE_INSTANCE = 5012
UNREACHABLE = "127.0.0.1:47899"


@pytest.fixture(scope="module", autouse=True)
def lab():
    simulator = BacnetLab(ADDRESS, device_instance=DEVICE_INSTANCE)
    simulator.start()
    yield simulator
    simulator.stop()


def _create_tenant(name: str) -> dict:
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
def two_tenants():
    tenant_a = _create_tenant("ClientBacnetDiscoveryApiA")
    tenant_b = _create_tenant("ClientBacnetDiscoveryApiB")
    yield tenant_a, tenant_b
    purge_tenant(tenant_a["tenant_id"])
    purge_tenant(tenant_b["tenant_id"])


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(tenant_id=str(tenant['tenant_id']), roles=roles)}"
    }


def _manager(tenant):
    return _headers(tenant, ["responsable_exploitation"])


def _tech(tenant):
    return _headers(tenant, ["technicien"])


def _call(method, path, headers, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def _scan(tenant, headers, *, address: str = ADDRESS, timeout: float = 3.0):
    return _call(
        "POST",
        "/bacnet-discovery/scan",
        headers,
        json={"equipment_id": str(tenant["equipment_id"]), "address": address, "timeout": timeout},
    )


def test_scan_cree_un_lot_pret_avec_les_propositions(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)

    response = _scan(tenant_a, manager)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["proposal_count"] == 8
    assert body["object_count"] == 8
    assert body["duplicate_count"] == 0

    batches = _call(
        "GET", f"/bacnet-discovery/batches?equipment_id={tenant_a['equipment_id']}", manager
    ).json()
    assert len(batches) == 1
    assert batches[0]["id"] == body["id"]

    single_batch = _call("GET", f"/bacnet-discovery/batches/{body['id']}", manager)
    assert single_batch.status_code == 200
    assert single_batch.json()["id"] == body["id"]

    proposals = _call(
        "GET", f"/bacnet-discovery/batches/{body['id']}/proposals", manager
    ).json()
    assert len(proposals) == 8
    by_name = {p["object_name"]: p for p in proposals}
    temperature = by_name["T Depart CTA"]
    assert temperature["proposed_point_class"] == "temperature_sensor"
    assert temperature["reason_message"]
    assert temperature["reason_message"][0].isupper()
    unclassified = by_name["AI-07"]
    assert unclassified["proposed_point_class"] is None
    assert unclassified["reason_code"] == "NO_RELIABLE_SIGNAL"


def test_scan_en_anglais_traduit_les_raisons(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    batch = _scan(tenant_a, manager).json()

    proposals = _call(
        "GET",
        f"/bacnet-discovery/batches/{batch['id']}/proposals",
        {**manager, "Accept-Language": "en"},
    ).json()

    by_name = {p["object_name"]: p for p in proposals}
    assert by_name["T Depart CTA"]["reason_message"] != "Unité de température BACnet reconnue."


def test_scan_appareil_injoignable_referme_le_lot_en_echec(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)

    response = _scan(tenant_a, manager, address=UNREACHABLE, timeout=0.5)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_code"] == "BACNET_DEVICE_UNREACHABLE"


def test_scan_equipement_inexistant_est_refuse(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)

    response = _call(
        "POST",
        "/bacnet-discovery/scan",
        manager,
        json={"equipment_id": str(uuid.uuid4()), "address": ADDRESS},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "FUNCTIONAL_LOCATION_NOT_FOUND"


def test_technicien_peut_lire_mais_pas_scanner_ni_decider(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    tech = _tech(tenant_a)
    batch = _scan(tenant_a, manager).json()
    proposal_id = _call(
        "GET", f"/bacnet-discovery/batches/{batch['id']}/proposals", manager
    ).json()[0]["id"]

    scan_attempt = _scan(tenant_a, tech)
    accept_attempt = _call(
        "POST", f"/bacnet-discovery-proposals/{proposal_id}/accept", tech, json={}
    )
    reject_attempt = _call(
        "POST",
        f"/bacnet-discovery-proposals/{proposal_id}/reject",
        tech,
        json={"reason": "x"},
    )
    read_attempt = _call(
        "GET", f"/bacnet-discovery/batches?equipment_id={tenant_a['equipment_id']}", tech
    )

    assert scan_attempt.status_code == 403
    assert accept_attempt.status_code == 403
    assert reject_attempt.status_code == 403
    assert read_attempt.status_code == 200


def test_accepter_puis_rejeter_des_propositions(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    batch = _scan(tenant_a, manager).json()
    proposals = _call(
        "GET", f"/bacnet-discovery/batches/{batch['id']}/proposals", manager
    ).json()
    by_name = {p["object_name"]: p for p in proposals}

    accepted = _call(
        "POST",
        f"/bacnet-discovery-proposals/{by_name['T Depart CTA']['id']}/accept",
        manager,
        json={},
    )
    rejected = _call(
        "POST",
        f"/bacnet-discovery-proposals/{by_name['P Refoulement']['id']}/reject",
        manager,
        json={"reason": "Deja instrumente ailleurs"},
    )

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["created_point_id"] is not None

    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Deja instrumente ailleurs"


def test_accepter_deux_fois_est_un_conflit(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    batch = _scan(tenant_a, manager).json()
    proposal_id = _call(
        "GET", f"/bacnet-discovery/batches/{batch['id']}/proposals", manager
    ).json()[0]["id"]

    first = _call(
        "POST", f"/bacnet-discovery-proposals/{proposal_id}/accept", manager, json={}
    )
    second = _call(
        "POST", f"/bacnet-discovery-proposals/{proposal_id}/accept", manager, json={}
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "BACNET_DISCOVERY_PROPOSAL_ALREADY_DECIDED"


def test_rejeter_sans_raison_est_une_erreur_de_validation(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    batch = _scan(tenant_a, manager).json()
    proposal_id = _call(
        "GET", f"/bacnet-discovery/batches/{batch['id']}/proposals", manager
    ).json()[0]["id"]

    response = _call(
        "POST", f"/bacnet-discovery-proposals/{proposal_id}/reject", manager, json={"reason": ""}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_lot_et_propositions_inexistants_sont_introuvables(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)

    missing_batch = _call("GET", f"/bacnet-discovery/batches/{uuid.uuid4()}", manager)
    missing_accept = _call(
        "POST", f"/bacnet-discovery-proposals/{uuid.uuid4()}/accept", manager, json={}
    )
    missing_reject = _call(
        "POST",
        f"/bacnet-discovery-proposals/{uuid.uuid4()}/reject",
        manager,
        json={"reason": "x"},
    )

    assert missing_batch.status_code == 404
    assert missing_batch.json()["code"] == "BACNET_DISCOVERY_BATCH_NOT_FOUND"
    assert missing_accept.status_code == 404
    assert missing_accept.json()["code"] == "BACNET_DISCOVERY_PROPOSAL_NOT_FOUND"
    assert missing_reject.status_code == 404
    assert missing_reject.json()["code"] == "BACNET_DISCOVERY_PROPOSAL_NOT_FOUND"


def test_lot_et_propositions_dun_autre_tenant_sont_introuvables(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    manager_a = _manager(tenant_a)
    batch = _scan(tenant_a, manager_a).json()

    other_batch = _call(
        "GET", f"/bacnet-discovery/batches/{batch['id']}", _tech(tenant_b)
    )
    other_proposals = _call(
        "GET", f"/bacnet-discovery/batches/{batch['id']}/proposals", _tech(tenant_b)
    )

    assert other_batch.status_code == 404
    assert other_proposals.status_code == 404


def test_equipement_dun_autre_tenant_est_introuvable_pour_le_scan(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants

    response = _call(
        "POST",
        "/bacnet-discovery/scan",
        _manager(tenant_b),
        json={"equipment_id": str(tenant_a["equipment_id"]), "address": ADDRESS},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "FUNCTIONAL_LOCATION_NOT_FOUND"
