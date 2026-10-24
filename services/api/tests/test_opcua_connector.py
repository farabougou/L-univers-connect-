"""Connecteur OPC UA contre un serveur simulé (aucun matériel requis).

Le simulateur est un vrai serveur OPC UA (asyncua), avec deux variables
exposant des valeurs connues : ce test prouve que le connecteur dialogue
réellement en OPC UA (session, NodeId, lecture de valeur), pas seulement
contre une fonction Python.
"""

import asyncio
import threading

import pytest
from asyncua import Server, ua

from app.connectors.opcua import OpcuaPoint, OpcuaReadError, read_opcua_points

ENDPOINT_URL = "opc.tcp://127.0.0.1:4862/paios/test/"

FAKE_VALUES = {"temperature": 21.5, "setpoint": 19.0}


@pytest.fixture(scope="module", autouse=True)
def opcua_simulator():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()

    async def _build_server() -> tuple[Server, dict[str, str]]:
        server = Server()
        await server.init()
        server.set_endpoint(ENDPOINT_URL)
        idx = await server.register_namespace("paios-opcua-test")
        device = await server.nodes.objects.add_object(idx, "Device1")
        temperature = await device.add_variable(
            ua.NodeId(9001, idx), "Temperature", FAKE_VALUES["temperature"]
        )
        setpoint = await device.add_variable(
            ua.NodeId(9002, idx), "Setpoint", FAKE_VALUES["setpoint"]
        )
        await server.start()
        return server, {
            "temperature": temperature.nodeid.to_string(),
            "setpoint": setpoint.nodeid.to_string(),
        }

    server, node_ids = asyncio.run_coroutine_threadsafe(_build_server(), loop).result(timeout=5)

    yield node_ids

    asyncio.run_coroutine_threadsafe(server.stop(), loop).result(timeout=5)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)


def _points(node_ids: dict[str, str]) -> list[OpcuaPoint]:
    return [
        OpcuaPoint(name="temperature", node_id=node_ids["temperature"]),
        OpcuaPoint(name="setpoint", node_id=node_ids["setpoint"]),
    ]


def test_lit_tous_les_points_avec_la_bonne_valeur(opcua_simulator):
    values = read_opcua_points(ENDPOINT_URL, _points(opcua_simulator))

    assert values.keys() == FAKE_VALUES.keys()
    for name, expected in FAKE_VALUES.items():
        assert values[name] == pytest.approx(expected, abs=1e-3)


def test_serveur_injoignable_leve_une_erreur_explicite(opcua_simulator):
    with pytest.raises(OpcuaReadError):
        read_opcua_points("opc.tcp://127.0.0.1:48989/nope/", _points(opcua_simulator), timeout=1.0)


def test_node_id_inconnu_leve_une_erreur_explicite(opcua_simulator):
    unknown = [OpcuaPoint(name="inconnu", node_id="ns=99;i=99999")]
    with pytest.raises(OpcuaReadError):
        read_opcua_points(ENDPOINT_URL, unknown, timeout=2.0)


def test_node_id_invalide_leve_une_erreur_explicite(opcua_simulator):
    invalid = [OpcuaPoint(name="invalide", node_id="pas-un-nodeid")]
    with pytest.raises(OpcuaReadError):
        read_opcua_points(ENDPOINT_URL, invalid, timeout=2.0)
