"""Carte du relais simulé (V1, validation du pipeline de commande).

Jamais un vrai appareil : ce catalogue sert uniquement à valider que la
chaîne autorisation → commande → Edge → exécution → vérification → audit
fonctionne de bout en bout, sans jamais toucher un équipement réel (voir
CLAUDE.md, exception à la règle non négociable 1, décision du 24/09/2026).

Une seule bobine : l'état marche/arrêt. Function code 01 en lecture, 05 en
écriture — la lecture est déjà couverte par app/connectors/modbus.py,
l'écriture ne vit que dans app/connectors/simulated_actuator.py.
"""

from app.connectors.modbus import ModbusRegisterPoint

RELAY_STATE_ADDRESS = 0

SIMULATED_RELAY_POINTS = [
    ModbusRegisterPoint(
        name="relay_state", address=RELAY_STATE_ADDRESS, register_kind="coil", unit=""
    ),
]
