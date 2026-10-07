"""Connecteur BACnet contre un appareil simulé (aucun matériel requis).

Le simulateur est une vraie application BACnet (bacpypes3), avec deux objets
"analog-input" exposant des valeurs connues : ce test prouve que le
connecteur dialogue réellement en BACnet/IP (adressage, décodage de
propriété), pas seulement contre une fonction Python.
"""

import argparse
import asyncio
import threading

import pytest
from bacpypes3.app import Application
from bacpypes3.basetypes import StatusFlags
from bacpypes3.local.analog import AnalogInputObject

from app.connectors.bacnet import BacnetPoint, BacnetReadError, read_bacnet_points

ADDRESS = "127.0.0.1:47810"

FAKE_VALUES = {"temperature": 21.5, "setpoint": 19.0}

POINTS = [
    BacnetPoint(name="temperature", object_type="analog-input", object_instance=1, unit="°C"),
    BacnetPoint(name="setpoint", object_type="analog-input", object_instance=2, unit="°C"),
]


@pytest.fixture(scope="module", autouse=True)
def bacnet_simulator():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()

    async def _build_server() -> Application:
        args = argparse.Namespace(
            name="paios-bacnet-test-server",
            instance=3969998,
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
                objectName="Temperature",
                presentValue=FAKE_VALUES["temperature"],
                statusFlags=StatusFlags([0, 0, 0, 0]),
                covIncrement=0.1,
                units="degreesCelsius",
            )
        )
        application.add_object(
            AnalogInputObject(
                objectIdentifier=("analog-input", 2),
                objectName="Setpoint",
                presentValue=FAKE_VALUES["setpoint"],
                statusFlags=StatusFlags([0, 0, 0, 0]),
                covIncrement=0.1,
                units="degreesCelsius",
            )
        )
        return application

    server_app = asyncio.run_coroutine_threadsafe(_build_server(), loop).result(timeout=5)

    yield

    loop.call_soon_threadsafe(server_app.close)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)


def test_lit_tous_les_points_avec_la_bonne_valeur():
    values = read_bacnet_points(ADDRESS, POINTS)

    assert values.keys() == FAKE_VALUES.keys()
    for name, expected in FAKE_VALUES.items():
        assert values[name] == pytest.approx(expected, abs=1e-3)


def test_hote_injoignable_leve_une_erreur_explicite():
    with pytest.raises(BacnetReadError):
        read_bacnet_points("127.0.0.1:47899", POINTS, timeout=0.5)


def test_objet_inconnu_leve_une_erreur_explicite():
    unknown = [
        BacnetPoint(name="inconnu", object_type="analog-input", object_instance=99, unit="°C")
    ]
    with pytest.raises(BacnetReadError):
        read_bacnet_points(ADDRESS, unknown, timeout=1.0)
