"""API de découverte BACnet (`app.routers.bacnet_discovery`) : demande de
scan côté humain, exécution et rapport côté agent Edge (directive de
Mohamed, 30/09/2026), lots, propositions, acceptation/rejet — rôles,
isolation des tenants, appareil injoignable. Palier SIMULATOR_TESTED (vrai
appareil BACnet Lab derrière l'appel HTTP)."""

import dataclasses
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.connectors.bacnet import BacnetReadError, discover_device, read_device_objects
from app.db import engine
from app.devices import provision_device
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


def _device_token(tenant, *, device_id: str = "bacnet-edge-01") -> str:
    """Provisionne un appareil Edge et l'authentifie, comme le ferait
    scripts/bacnet_discovery_agent.py sur site (secret partagé ici pour la
    simplicité du test, voir app.devices pour le modèle cible par clé
    privée)."""
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _, secret = provision_device(
            connection, tenant_id=tenant["tenant_id"], device_id=device_id, created_by="test"
        )
    auth = client.post(
        "/devices/auth",
        json={"tenant_id": str(tenant["tenant_id"]), "device_id": device_id, "secret": secret},
    )
    assert auth.status_code == 200, auth.text
    assert "discovery:execute" in auth.json()["scopes"]
    return auth.json()["access_token"]


def _edge_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _scan_and_complete(tenant, manager, *, address: str = ADDRESS, timeout: float = 3.0) -> dict:
    """Simule le cycle complet : une personne demande un scan, l'agent Edge
    le récupère, l'exécute réellement contre le BACnet Lab et rapporte le
    résultat — jamais un raccourci qui exécuterait le connecteur dans ce
    processus API (voir l'en-tête de app.bacnet_discovery)."""
    scan_response = _scan(tenant, manager, address=address, timeout=timeout)
    assert scan_response.status_code == 201, scan_response.text
    batch = scan_response.json()
    assert batch["status"] == "processing"

    token = _device_token(tenant)
    pending = client.get(
        f"/edge/bacnet-discovery/pending?equipment_id={tenant['equipment_id']}",
        headers=_edge_headers(token),
    )
    assert pending.status_code == 200, pending.text
    assert batch["id"] in [row["id"] for row in pending.json()]

    device_info = discover_device(address, timeout=timeout)
    objects = read_device_objects(address, device_info.device_instance, timeout=timeout)
    result = client.post(
        f"/edge/bacnet-discovery/{batch['id']}/result",
        headers=_edge_headers(token),
        json={
            "device_instance": device_info.device_instance,
            "objects": [dataclasses.asdict(obj) for obj in objects],
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def _scan_and_fail(tenant, manager, *, address: str = UNREACHABLE, timeout: float = 0.5) -> dict:
    scan_response = _scan(tenant, manager, address=address, timeout=timeout)
    assert scan_response.status_code == 201, scan_response.text
    batch = scan_response.json()

    token = _device_token(tenant)
    with pytest.raises(BacnetReadError):
        discover_device(address, timeout=timeout)

    result = client.post(
        f"/edge/bacnet-discovery/{batch['id']}/failure",
        headers=_edge_headers(token),
        json={"error_code": "BACNET_DEVICE_UNREACHABLE"},
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_scan_cree_un_lot_en_cours_sans_appel_reseau(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)

    response = _scan(tenant_a, manager)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "processing"
    assert body["device_instance"] is None
    assert body["proposal_count"] is None
    assert body["timeout_seconds"] == pytest.approx(3.0)

    batches = _call(
        "GET", f"/bacnet-discovery/batches?equipment_id={tenant_a['equipment_id']}", manager
    ).json()
    assert len(batches) == 1
    assert batches[0]["id"] == body["id"]


def test_agent_edge_execute_le_scan_et_rapporte_les_propositions(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)

    batch = _scan_and_complete(tenant_a, manager)

    assert batch["status"] == "ready"
    assert batch["proposal_count"] == 8
    assert batch["object_count"] == 8
    assert batch["duplicate_count"] == 0

    proposals = _call("GET", f"/bacnet-discovery/batches/{batch['id']}/proposals", manager).json()
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
    batch = _scan_and_complete(tenant_a, manager)

    proposals = _call(
        "GET",
        f"/bacnet-discovery/batches/{batch['id']}/proposals",
        {**manager, "Accept-Language": "en"},
    ).json()

    by_name = {p["object_name"]: p for p in proposals}
    assert by_name["T Depart CTA"]["reason_message"] != "Unité de température BACnet reconnue."


def test_agent_edge_rapporte_un_appareil_injoignable(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)

    batch = _scan_and_fail(tenant_a, manager)

    assert batch["status"] == "failed"
    assert batch["error_code"] == "BACNET_DEVICE_UNREACHABLE"


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
    batch = _scan_and_complete(tenant_a, manager)
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
    batch = _scan_and_complete(tenant_a, manager)
    proposals = _call("GET", f"/bacnet-discovery/batches/{batch['id']}/proposals", manager).json()
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
    batch = _scan_and_complete(tenant_a, manager)
    proposal_id = _call(
        "GET", f"/bacnet-discovery/batches/{batch['id']}/proposals", manager
    ).json()[0]["id"]

    first = _call("POST", f"/bacnet-discovery-proposals/{proposal_id}/accept", manager, json={})
    second = _call("POST", f"/bacnet-discovery-proposals/{proposal_id}/accept", manager, json={})

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "BACNET_DISCOVERY_PROPOSAL_ALREADY_DECIDED"


def test_rejeter_sans_raison_est_une_erreur_de_validation(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    batch = _scan_and_complete(tenant_a, manager)
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

    other_batch = _call("GET", f"/bacnet-discovery/batches/{batch['id']}", _tech(tenant_b))
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


def test_jeton_humain_est_refuse_sur_les_routes_edge(two_tenants) -> None:
    tenant_a, _ = two_tenants
    batch = _scan(tenant_a, _manager(tenant_a)).json()

    pending = _call(
        "GET",
        f"/edge/bacnet-discovery/pending?equipment_id={tenant_a['equipment_id']}",
        _manager(tenant_a),
    )
    result = _call(
        "POST",
        f"/edge/bacnet-discovery/{batch['id']}/result",
        _manager(tenant_a),
        json={"device_instance": 1, "objects": []},
    )

    assert pending.status_code == 401
    assert result.status_code == 401


def test_agent_dun_autre_tenant_ne_voit_aucun_scan_en_attente(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    _scan(tenant_a, _manager(tenant_a))
    token_b = _device_token(tenant_b, device_id="bacnet-edge-b")

    pending = client.get(
        f"/edge/bacnet-discovery/pending?equipment_id={tenant_a['equipment_id']}",
        headers=_edge_headers(token_b),
    )

    assert pending.status_code == 200
    assert pending.json() == []


def test_rapporter_deux_fois_le_meme_scan_est_un_conflit(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    scan_response = _scan(tenant_a, manager, address=UNREACHABLE, timeout=0.5)
    batch = scan_response.json()
    token = _device_token(tenant_a)

    first = client.post(
        f"/edge/bacnet-discovery/{batch['id']}/failure",
        headers=_edge_headers(token),
        json={"error_code": "BACNET_DEVICE_UNREACHABLE"},
    )
    second = client.post(
        f"/edge/bacnet-discovery/{batch['id']}/failure",
        headers=_edge_headers(token),
        json={"error_code": "BACNET_DEVICE_UNREACHABLE"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "BACNET_DISCOVERY_BATCH_ALREADY_COMPLETED"


def test_rapporter_un_scan_inexistant_est_introuvable(two_tenants) -> None:
    tenant_a, _ = two_tenants
    token = _device_token(tenant_a)

    response = client.post(
        f"/edge/bacnet-discovery/{uuid.uuid4()}/failure",
        headers=_edge_headers(token),
        json={"error_code": "BACNET_DEVICE_UNREACHABLE"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "BACNET_DISCOVERY_BATCH_NOT_FOUND"


def _last_seen_at(tenant, device_id: str):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return connection.execute(
            text("SELECT last_seen_at FROM edge_devices WHERE device_id = :device_id"),
            {"device_id": device_id},
        ).scalar()


def test_activite_de_lagent_edge_alimente_le_diagnostic_de_connectivite(two_tenants) -> None:
    """Chaque appel de l'agent Edge (liste des scans en attente, rapport de
    résultat ou d'échec) doit se voir dans le diagnostic de connectivité
    déjà affiché ailleurs dans le produit (tableau de bord Portfolio,
    app/devices.py::communication_status) — pas seulement à l'authentification."""
    tenant_a, _ = two_tenants
    device_id = "bacnet-edge-diag"
    token = _device_token(tenant_a, device_id=device_id)

    # Recule artificiellement le dernier contact pour distinguer sans
    # ambiguïté « touché par l'authentification » de « touché par l'appel
    # de découverte lui-même » (l'horloge seule ne le garantirait pas dans
    # un test rapide).
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        connection.execute(
            text(
                "UPDATE edge_devices SET last_seen_at = now() - interval '1 hour' "
                "WHERE device_id = :device_id"
            ),
            {"device_id": device_id},
        )
    backdated = _last_seen_at(tenant_a, device_id)

    response = client.get(
        f"/edge/bacnet-discovery/pending?equipment_id={tenant_a['equipment_id']}",
        headers=_edge_headers(token),
    )
    assert response.status_code == 200
    seen_after_poll = _last_seen_at(tenant_a, device_id)
    assert seen_after_poll > backdated
