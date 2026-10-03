"""Connecteur Modbus contre un appareil simulé (aucun matériel requis).

Le simulateur (scripts/modbus_simulator.py) sert exactement la même carte de
registres qu'un vrai SDM120 : ce test prouve que le connecteur se connecte,
lit les bons registres et décode les bonnes valeurs, avant tout branchement
sur un appareil réel.
"""

import threading
import time

import pytest
from pymodbus.server import ServerStop, StartTcpServer

from app.connectors.modbus import ModbusReadError, read_modbus_points
from app.connectors.sdm120 import SDM120_POINTS
from scripts.modbus_simulator import FAKE_VALUES, build_context

PORT = 5099


@pytest.fixture(scope="module", autouse=True)
def modbus_simulator():
    thread = threading.Thread(
        target=StartTcpServer,
        args=(build_context(),),
        kwargs={"address": ("127.0.0.1", PORT)},
        daemon=True,
    )
    thread.start()
    time.sleep(0.5)  # laisse le serveur ouvrir le port avant le premier test
    yield
    ServerStop()
    thread.join(timeout=2)


def test_lit_tous_les_points_avec_la_bonne_precision_flottante():
    values = read_modbus_points("127.0.0.1", PORT, SDM120_POINTS)

    assert values.keys() == FAKE_VALUES.keys()
    for name, expected in FAKE_VALUES.items():
        assert values[name] == pytest.approx(expected, abs=1e-3)


def test_applique_le_facteur_scale():
    from dataclasses import replace

    scaled_point = replace(SDM120_POINTS[0], scale=10.0)
    values = read_modbus_points("127.0.0.1", PORT, [scaled_point])
    assert values["voltage"] == pytest.approx(FAKE_VALUES["voltage"] * 10, abs=1e-2)


def test_hote_injoignable_leve_une_erreur_explicite():
    with pytest.raises(ModbusReadError):
        read_modbus_points("127.0.0.1", 1, SDM120_POINTS, timeout=0.5)
