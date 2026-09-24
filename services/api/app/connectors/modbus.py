"""Connecteur Modbus générique (ADR 012 §2.12 : SDK de connecteur).

Adaptateur volontairement sans connaissance d'un fabricant particulier : la
carte des registres d'un appareil précis (ex. app/connectors/sdm120.py) est
une donnée passée en paramètre, jamais codée en dur ici (règle non
négociable 8 : pas de dépendance à un constructeur dans le noyau).

Lecture seule par construction (règle non négociable 1) : ce module ne
propose aucune fonction d'écriture de registre.
"""

from dataclasses import dataclass
from typing import Literal

from pymodbus.client import ModbusTcpClient
from pymodbus.client.mixin import ModbusClientMixin
from pymodbus.exceptions import ModbusException

RegisterKind = Literal["input", "holding"]


class ModbusReadError(Exception):
    """Échec de lecture d'un point Modbus (réseau, appareil, registre)."""


@dataclass(frozen=True)
class ModbusRegisterPoint:
    """Un point mesuré, décrit par sa position dans la carte de registres."""

    name: str
    address: int
    register_kind: RegisterKind
    data_type: ModbusClientMixin.DATATYPE
    unit: str
    scale: float = 1.0


def find_register_by_name(points: list[ModbusRegisterPoint], name: str) -> ModbusRegisterPoint:
    for point in points:
        if point.name == name:
            return point
    known = ", ".join(point.name for point in points)
    raise ValueError(f"Registre inconnu : {name} (connus : {known})")


def read_modbus_points(
    host: str,
    port: int,
    points: list[ModbusRegisterPoint],
    *,
    device_id: int = 1,
    timeout: float = 3.0,
) -> dict[str, float]:
    """Lit une liste de points sur un appareil Modbus TCP. Renvoie nom → valeur.

    Une seule connexion pour tous les points, fermée dans tous les cas.
    """
    client = ModbusTcpClient(host, port=port, timeout=timeout)
    if not client.connect():
        raise ModbusReadError(f"Connexion impossible à {host}:{port}")

    values: dict[str, float] = {}
    try:
        for point in points:
            register_count = point.data_type.value[1]
            try:
                if point.register_kind == "input":
                    response = client.read_input_registers(
                        point.address, count=register_count, device_id=device_id
                    )
                else:
                    response = client.read_holding_registers(
                        point.address, count=register_count, device_id=device_id
                    )
            except ModbusException as exc:
                raise ModbusReadError(f"Lecture de « {point.name} » impossible") from exc

            if response.isError():
                raise ModbusReadError(f"Appareil en erreur pour « {point.name} »")

            raw = ModbusClientMixin.convert_from_registers(response.registers, point.data_type)
            values[point.name] = float(raw) * point.scale
    finally:
        client.close()

    return values
