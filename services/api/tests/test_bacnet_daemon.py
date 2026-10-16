"""Démon de sondage BACnet : même garanties que le démon Modbus
(scripts/modbus_daemon.py, tests/test_modbus_daemon.py), pour un protocole
qui n'a pas de catalogue de registres par fabricant — voir
app/connectors/bacnet.py et app/connectors/device_mapping.py.

Ces tests appellent l'application FastAPI réelle par HTTP (ASGITransport),
exactement le chemin qu'emprunte un appareil sur site, contre un simulateur
BACnet réel (bacpypes3), pas un mock.
"""

import argparse
import asyncio
import threading

import pytest
from bacpypes3.app import Application
from bacpypes3.basetypes import StatusFlags
from bacpypes3.local.analog import AnalogInputObject
from sqlalchemy import text
from starlette.testclient import TestClient

from app.connectors.edge_client import EdgeApiClient
from app.connectors.offline_buffer import OfflineBuffer
from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from scripts.bacnet_daemon import run
from tests.modbus_fixtures import (
    activate_bacnet_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_and_power_points,
    create_tenant_with_energy_point,
    provision_device_for_tenant,
)

ADDRESS = "127.0.0.1:47813"
FAKE_VALUE = 12.5


@pytest.fixture(scope="module", autouse=True)
def bacnet_simulator():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()

    async def _build_server() -> Application:
        args = argparse.Namespace(
            name="paios-bacnet-daemon-test-server",
            instance=3969997,
            network=0,
            address=ADDRESS,
            vendoridentifier=999,
            foreign=None,
            ttl=30,
            bbmd=None,
        )
        application = Application.from_args(args)
        application.add_object(
            AnalogInputObject(
                objectIdentifier=("analog-input", 1),
                objectName="Energie",
                presentValue=FAKE_VALUE,
                statusFlags=StatusFlags([0, 0, 0, 0]),
                covIncrement=0.1,
                units="kilowattHours",
            )
        )
        application.add_object(
            AnalogInputObject(
                objectIdentifier=("analog-input", 2),
                objectName="Puissance",
                presentValue=FAKE_VALUE * 2,
                statusFlags=StatusFlags([0, 0, 0, 0]),
                covIncrement=0.1,
                units="watts",
            )
        )
        return application

    server_app = asyncio.run_coroutine_threadsafe(_build_server(), loop).result(timeout=5)

    yield

    loop.call_soon_threadsafe(server_app.close)
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
def tenant():
    created = create_tenant_with_energy_point("ClientBacnetDaemon")
    activate_bacnet_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        address=ADDRESS,
        points=[
            {
                "point_id": str(created["point_id"]),
                "object_type": "analog-input",
                "object_instance": 1,
            }
        ],
    )
    secret = provision_device_for_tenant(tenant_id=created["tenant_id"], device_id="bacnet-daemon")
    yield {**created, "device_id": "bacnet-daemon", "secret": secret}
    cleanup_tenant(created)


@pytest.fixture
def tenant_two_points():
    created = create_tenant_with_energy_and_power_points("ClientBacnetDaemonMulti")
    activate_bacnet_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        address=ADDRESS,
        points=[
            {
                "point_id": str(created["energy_point_id"]),
                "object_type": "analog-input",
                "object_instance": 1,
            },
            {
                "point_id": str(created["power_point_id"]),
                "object_type": "analog-input",
                "object_instance": 2,
            },
        ],
    )
    secret = provision_device_for_tenant(tenant_id=created["tenant_id"], device_id="bacnet-daemon")
    yield {**created, "device_id": "bacnet-daemon", "secret": secret}
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
    # côté lecture BACnet, mais la boucle continue jusqu'à max_cycles au lieu
    # de lever une exception.
    activate_bacnet_device_mapping(
        tenant_id=tenant["tenant_id"],
        equipment_id=tenant["location_id"],
        address="127.0.0.1:47898",
        points=[
            {
                "point_id": str(tenant["point_id"]),
                "object_type": "analog-input",
                "object_instance": 1,
            }
        ],
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
