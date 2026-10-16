"""Relie une lecture Modbus à l'enregistrement réel d'une mesure (F3, M3).

Étape volontairement minimale : associe des points déjà créés à des
registres Modbus donnés en paramètre à l'appel, sans les persister nulle
part pour l'instant (pas de nouvelle table tant que ce chemin n'est pas
confirmé sur un appareil réel — voir scripts/modbus_poll.py).

Réutilise ingest_measurements (app/telemetry.py), qui traite déjà chaque
point indépendamment et qualifie chaque valeur (bornes, horloge, mise en
service) : ce module ne fait qu'amener les valeurs jusque-là.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Connection

from app.connectors.modbus import ModbusRegisterPoint, read_modbus_points
from app.telemetry import ingest_measurements


@dataclass(frozen=True)
class PointModbusMapping:
    """Associe, pour un seul relevé, un point existant à un registre."""

    point_id: uuid.UUID
    register: ModbusRegisterPoint


def poll_and_record(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    host: str,
    port: int,
    mappings: list[PointModbusMapping],
    source: str,
    device_id: int = 1,
) -> dict[str, Any]:
    """Lit tous les registres en une seule connexion Modbus, puis enregistre
    chaque mesure. Un même horodatage pour tout le lot : ces valeurs viennent
    de la même interrogation de l'appareil."""
    registers = [mapping.register for mapping in mappings]
    values = read_modbus_points(host, port, registers, device_id=device_id)

    now = datetime.now(UTC)
    items = [
        {
            "point_id": mapping.point_id,
            "value": values[mapping.register.name],
            "measured_at": now,
            # "measured" : un relevé Modbus est une vraie mesure physique de
            # l'appareil, jamais une valeur générée (voir ck_measurements_origin).
            "origin": "measured",
        }
        for mapping in mappings
    ]
    return ingest_measurements(
        connection, tenant_id=tenant_id, items=items, source=source, received_at=now
    )
