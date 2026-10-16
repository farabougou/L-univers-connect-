"""Carte de registres Eastron SDM120-Modbus (documentation constructeur publique).

Donnée pure, pas de logique : voir app/connectors/modbus.py pour
l'adaptateur générique qui l'utilise. Registres d'entrée (function code 04),
flottants 32 bits, gros-boutiste.
"""

from app.connectors.modbus import ModbusClientMixin, ModbusRegisterPoint

FLOAT32 = ModbusClientMixin.DATATYPE.FLOAT32

SDM120_POINTS = [
    ModbusRegisterPoint(
        name="voltage", address=0, register_kind="input", data_type=FLOAT32, unit="V"
    ),
    ModbusRegisterPoint(
        name="current", address=6, register_kind="input", data_type=FLOAT32, unit="A"
    ),
    ModbusRegisterPoint(
        name="active_power", address=12, register_kind="input", data_type=FLOAT32, unit="W"
    ),
    ModbusRegisterPoint(
        name="frequency", address=70, register_kind="input", data_type=FLOAT32, unit="Hz"
    ),
    ModbusRegisterPoint(
        name="total_active_energy",
        address=342,
        register_kind="input",
        data_type=FLOAT32,
        unit="kWh",
    ),
]
