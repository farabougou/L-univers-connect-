"""Simulateur Modbus TCP d'un relais pilotable (outil de développement).

But : valider le pipeline de commande (autorisation → Edge → exécution →
vérification → audit) sans jamais toucher un équipement réel — voir
CLAUDE.md, exception à la règle non négociable 1. N'est jamais démarré en
production, uniquement lancé à la main ou par les tests.

Usage : python scripts/simulated_relay_simulator.py [port, défaut 5021]
"""

import sys

from pymodbus.server import StartTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from app.connectors.simulated_relay import RELAY_STATE_ADDRESS


def build_context() -> SimDevice:
    coils = [SimData(address=RELAY_STATE_ADDRESS, datatype=DataType.BITS, values=False)]
    return SimDevice(
        id=1,
        simdata=(
            coils,
            [SimData(address=0, datatype=DataType.BITS, values=False)],
            [SimData(address=0, datatype=DataType.REGISTERS, values=0)],
            [SimData(address=0, datatype=DataType.REGISTERS, values=0)],
        ),
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5021
    print(f"Simulateur de relais sur 127.0.0.1:{port} (Ctrl+C pour arrêter)")
    StartTcpServer(build_context(), address=("127.0.0.1", port))
