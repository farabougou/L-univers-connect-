"""La seule fonction d'écriture vers un équipement de tout le dépôt.

Exception strictement limitée à un appareil explicitement simulé (voir
CLAUDE.md, exception à la règle non négociable 1, décision de Mohamed du
24/09/2026) : jamais un vrai équipement, jamais le compteur SDM120, jamais
un site client réel. app/connectors/modbus.py reste sans aucune fonction
d'écriture — c'est ici, et seulement ici, que ça s'écrit.

Le seul appelant légitime est le traitement des commandes côté Edge
(scripts/modbus_daemon.py), lui-même déclenché uniquement quand la
configuration active de l'équipement a pour device_type "simulated_relay"
(voir app/connectors/device_mapping.py, app/commands.py) : deux
vérifications indépendantes avant qu'une seule ligne de ce fichier ne
s'exécute.
"""

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from app.connectors.modbus import ModbusReadError


def write_modbus_coil(
    host: str, port: int, address: int, value: bool, *, device_id: int = 1, timeout: float = 3.0
) -> None:
    client = ModbusTcpClient(host, port=port, timeout=timeout)
    if not client.connect():
        raise ModbusReadError(f"Connexion impossible à {host}:{port}")
    try:
        try:
            response = client.write_coil(address, value, device_id=device_id)
        except ModbusException as exc:
            raise ModbusReadError(f"Écriture de la bobine {address} impossible") from exc
        if response.isError():
            raise ModbusReadError(f"Appareil en erreur pour l'écriture de la bobine {address}")
    finally:
        client.close()
