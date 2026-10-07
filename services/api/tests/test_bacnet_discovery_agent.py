"""Agent Edge de découverte BACnet (scripts/bacnet_discovery_agent.py) :
seul processus qui dialogue réellement en BACnet pour la découverte
(directive de Mohamed, 30/09/2026 — un appareil BACnet/IP vit sur le
réseau du site, jamais joignable depuis l'API hébergée). Ces tests
appellent l'application FastAPI réelle par HTTP (comme le fait
tests/test_bacnet_daemon.py pour la relève), contre un vrai appareil
simulé (BACnet Lab) — palier SIMULATOR_TESTED."""

import uuid

import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from app.bacnet_discovery import get_batch, request_discovery
from app.connectors.edge_client import EdgeApiClient
from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from scripts.bacnet_discovery_agent import run
from tests.bacnet_lab import BacnetLab
from tests.modbus_fixtures import provision_device_for_tenant
from tests.tenant_cleanup import purge_tenant

ADDRESS = "127.0.0.1:47833"
DEVICE_INSTANCE = 5013
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
    created = _create_tenant_with_equipment("ClientBacnetDiscoveryAgent")
    secret = provision_device_for_tenant(
        tenant_id=created["tenant_id"], device_id="bacnet-discovery-agent"
    )
    yield {**created, "device_id": "bacnet-discovery-agent", "secret": secret}
    purge_tenant(created["tenant_id"])


def _api(tenant: dict) -> EdgeApiClient:
    return EdgeApiClient(
        client=TestClient(app),
        tenant_id=tenant["tenant_id"],
        device_id=tenant["device_id"],
        secret=tenant["secret"],
    )


def _request(tenant: dict, *, address: str, timeout: float = 3.0) -> uuid.UUID:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return request_discovery(
            connection,
            tenant_id=tenant["tenant_id"],
            equipment_id=tenant["equipment_id"],
            address=address,
            scanned_by="test",
            timeout=timeout,
        )


def _batch(tenant: dict, batch_id: uuid.UUID) -> dict:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return get_batch(connection, batch_id)


def test_agent_execute_un_scan_en_attente_et_rapporte_les_propositions(tenant):
    batch_id = _request(tenant, address=ADDRESS)

    with _api(tenant) as api:
        cycles = run(
            api=api, equipment_id=tenant["equipment_id"], interval_seconds=0.05, max_cycles=1
        )

    assert cycles == 1
    batch = _batch(tenant, batch_id)
    assert batch["status"] == "ready"
    assert batch["device_instance"] == DEVICE_INSTANCE
    assert batch["proposal_count"] == 8
    assert batch["duplicate_count"] == 0


def test_agent_rapporte_un_appareil_injoignable(tenant):
    batch_id = _request(tenant, address=UNREACHABLE, timeout=0.5)

    with _api(tenant) as api:
        cycles = run(
            api=api, equipment_id=tenant["equipment_id"], interval_seconds=0.05, max_cycles=1
        )

    assert cycles == 1
    batch = _batch(tenant, batch_id)
    assert batch["status"] == "failed"
    assert batch["error_code"] == "BACNET_DEVICE_UNREACHABLE"


def test_agent_sans_scan_en_attente_ne_fait_rien(tenant):
    with _api(tenant) as api:
        cycles = run(
            api=api, equipment_id=tenant["equipment_id"], interval_seconds=0.05, max_cycles=2
        )

    assert cycles == 2


def test_agent_ne_rapporte_jamais_deux_fois_le_meme_scan(tenant):
    """Un lot déjà rapporté (par un tour précédent) ne redevient jamais
    'processing' : un second tour qui le revoit encore en attente ne
    devrait pas se produire, mais si l'API le renvoyait par erreur, l'agent
    absorbe le conflit (409) sans planter (voir _execute_one)."""
    batch_id = _request(tenant, address=ADDRESS)

    with _api(tenant) as api:
        cycles = run(
            api=api, equipment_id=tenant["equipment_id"], interval_seconds=0.05, max_cycles=2
        )

    assert cycles == 2
    batch = _batch(tenant, batch_id)
    assert batch["status"] == "ready"
