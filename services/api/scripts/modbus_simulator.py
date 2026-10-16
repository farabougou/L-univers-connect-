"""Simulateur Modbus TCP d'un compteur Eastron SDM120 (outil de développement).

But : valider le connecteur (app/connectors/modbus.py) sans matériel réel.
N'est jamais démarré en production — uniquement lancé à la main pendant le
développement, voir docs/dev/modbus.md.

Usage : python scripts/modbus_simulator.py [port, défaut 5020]
"""

import sys

from pymodbus.server import StartTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from app.connectors.sdm120 import SDM120_POINTS

# Valeurs plausibles pour une installation CVC de test, pas mesurées.
FAKE_VALUES = {
    "voltage": 231.4,
    "current": 2.37,
    "active_power": 548.0,
    "frequency": 50.0,
    "total_active_energy": 1284.6,
}


def build_context() -> SimDevice:
    input_registers = [
        SimData(
            address=point.address,
            values=FAKE_VALUES[point.name],
            datatype=DataType.FLOAT32,
        )
        for point in SDM120_POINTS
    ]
    # Le SDM120 réel ne répond qu'en registres d'entrée (function code 04) ;
    # les trois autres blocs sont sans objet mais requis par l'API du
    # simulateur, d'où ces entrées minimales.
    return SimDevice(
        id=1,
        simdata=(
            [SimData(address=0, datatype=DataType.BITS, values=False)],
            [SimData(address=0, datatype=DataType.BITS, values=False)],
            [SimData(address=0, datatype=DataType.REGISTERS, values=0)],
            input_registers,
        ),
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5020
    print(f"Simulateur SDM120 sur 127.0.0.1:{port} (Ctrl+C pour arrêter)")
    for point in SDM120_POINTS:
        print(f"  {point.name} = {FAKE_VALUES[point.name]} {point.unit}")
    StartTcpServer(build_context(), address=("127.0.0.1", port))
