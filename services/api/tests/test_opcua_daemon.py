"""Démon de sondage OPC UA : même garanties que le démon BACnet
(scripts/bacnet_daemon.py, tests/test_bacnet_daemon.py) — voir
app/connectors/opcua.py et app/connectors/device_mapping.py.

Ces tests appellent l'application FastAPI réelle par HTTP (ASGITransport),
exactement le chemin qu'emprunte un appareil sur site, contre un simulateur
OPC UA réel (asyncua), pas un mock.
"""

import asyncio
import threading

import pytest
from asyncua import Server, ua
from sqlalchemy import text
from starlette.testclient import TestClient

from app.connectors.edge_client import EdgeApiClient
from app.connectors.offline_buffer import OfflineBuffer
from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from scripts.opcua_daemon import run
from tests.modbus_fixtures import (
    activate_opcua_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_and_power_points,
    create_tenant_with_energy_point,
    provision_device_for_tenant,
)

ENDPOINT_URL = "opc.tcp://127.0.0.1:4863/paios/test/"
FAKE_VALUE = 12.5


@pytest.fixture(scope="module", autouse=True)
def opcua_simulator():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()

    async def _build_server() -> tuple[Server, dict[str, str]]:
        server = Server()
        await server.init()
        server.set_endpoint(ENDPOINT_URL)
        idx = await server.register_namespace("paios-opcua-daemon-test")
        device = await server.nodes.objects.add_object(idx, "Device1")
        energie = await device.add_variable(ua.NodeId(9001, idx), "Energie", FAKE_VALUE)
        puissance = await device.add_variable(
            ua.NodeId(9002, idx), "Puissance", FAKE_VALUE * 2
        )
        await server.start()
        return server, {
            "energie": energie.nodeid.to_string(),
            "puissance": puissance.nodeid.to_string(),
        }

    server, node_ids = asyncio.run_coroutine_threadsafe(_build_server(), loop).result(timeout=5)

    yield node_ids

    asyncio.run_coroutine_threadsafe(server.stop(), loop).result(timeout=5)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)


def _api(tenant: dict) -> EdgeApiClient:
    return EdgeApiClient(
        client=TestClient(app),
        tenant_id=tenant["tenant_id"],
        device_id=tenant["device_id"],
        secret=tenant["secret"],
    )


def _measurement_count(tenant_id) -> int:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        return connection.execute(
            text("SELECT count(*) FROM measurements WHERE tenant_id = :id"), {"id": tenant_id}
        ).scalar()


@pytest.fixture
def tenant(opcua_simulator):
    created = create_tenant_with_energy_point("ClientOpcuaDaemon")
    activate_opcua_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        endpoint_url=ENDPOINT_URL,
        points=[{"point_id": str(created["point_id"]), "node_id": opcua_simulator["energie"]}],
    )
    secret = provision_device_for_tenant(tenant_id=created["tenant_id"], device_id="opcua-daemon")
    yield {**created, "device_id": "opcua-daemon", "secret": secret}
    cleanup_tenant(created)


@pytest.fixture
def tenant_two_points(opcua_simulator):
    created = create_tenant_with_energy_and_power_points("ClientOpcuaDaemonMulti")
    activate_opcua_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        endpoint_url=ENDPOINT_URL,
        points=[
            {
                "point_id": str(created["energy_point_id"]),
                "node_id": opcua_simulator["energie"],
            },
            {
                "point_id": str(created["power_point_id"]),
                "node_id": opcua_simulator["puissance"],
            },
        ],
    )
    secret = provision_device_for_tenant(tenant_id=created["tenant_id"], device_id="opcua-daemon")
    yield {**created, "device_id": "opcua-daemon", "secret": secret}
    cleanup_tenant(created)


def test_plusieurs_tours_enregistrent_plusieurs_mesures(tenant, tmp_path):
    with _api(tenant) as api:
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=3,
        )

    assert cycles == 3
    assert _measurement_count(tenant["tenant_id"]) == 3


def test_deux_points_du_meme_appareil_sont_releves_ensemble(tenant_two_points, tmp_path):
    with _api(tenant_two_points) as api:
        cycles = run(
            api=api,
            equipment_id=tenant_two_points["location_id"],
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=1,
        )

    assert cycles == 1
    assert _measurement_count(tenant_two_points["tenant_id"]) == 2


def test_aucune_configuration_active_arrete_le_demarrage(tenant, tmp_path):
    equipement_sans_mapping = tenant["point_id"]  # n'importe quel id sans mapping actif
    with _api(tenant) as api, pytest.raises(SystemExit):
        run(
            api=api,
            equipment_id=equipement_sans_mapping,
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=1,
        )


def test_un_tour_rate_n_arrete_pas_le_demon(tenant, tmp_path):
    # Reconfigure vers une adresse sans rien qui écoute : chaque tour échoue
    # côté lecture OPC UA, mais la boucle continue jusqu'à max_cycles au lieu
    # de lever une exception.
    activate_opcua_device_mapping(
        tenant_id=tenant["tenant_id"],
        equipment_id=tenant["location_id"],
        endpoint_url="opc.tcp://127.0.0.1:48988/nope/",
        points=[{"point_id": str(tenant["point_id"]), "node_id": "ns=2;i=9001"}],
    )
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    with _api(tenant) as api:
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=buffer,
            max_cycles=2,
        )

    assert cycles == 2
    assert _measurement_count(tenant["tenant_id"]) == 0
