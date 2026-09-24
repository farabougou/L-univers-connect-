"""Relais simulé : lecture (app/connectors/modbus.py) et écriture
(app/connectors/simulated_actuator.py) d'une bobine, contre un appareil
simulé (aucun matériel requis, jamais un vrai équipement — voir CLAUDE.md).
"""

import threading
import time

import pytest
from pymodbus.server import ServerStop, StartTcpServer

from app.connectors.modbus import ModbusReadError, read_modbus_points
from app.connectors.simulated_actuator import write_modbus_coil
from app.connectors.simulated_relay import SIMULATED_RELAY_POINTS
from scripts.simulated_relay_simulator import build_context

PORT = 5921


@pytest.fixture(scope="module", autouse=True)
def relay_simulator():
    thread = threading.Thread(
        target=StartTcpServer,
        args=(build_context(),),
        kwargs={"address": ("127.0.0.1", PORT)},
        daemon=True,
    )
    thread.start()
    time.sleep(0.5)
    yield
    ServerStop()
    thread.join(timeout=2)


def test_etat_initial_a_l_arret():
    values = read_modbus_points("127.0.0.1", PORT, SIMULATED_RELAY_POINTS)
    assert values["relay_state"] == 0.0


def test_ecrire_puis_relire_la_bobine():
    write_modbus_coil("127.0.0.1", PORT, 0, True)
    assert read_modbus_points("127.0.0.1", PORT, SIMULATED_RELAY_POINTS)["relay_state"] == 1.0

    write_modbus_coil("127.0.0.1", PORT, 0, False)
    assert read_modbus_points("127.0.0.1", PORT, SIMULATED_RELAY_POINTS)["relay_state"] == 0.0


def test_ecriture_hote_injoignable_leve_une_erreur_explicite():
    with pytest.raises(ModbusReadError):
        write_modbus_coil("127.0.0.1", 1, 0, True, timeout=0.5)
