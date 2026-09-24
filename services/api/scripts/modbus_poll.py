"""Relève manuelle : lit un compteur SDM120 par Modbus et enregistre la mesure.

Outil de développement, pas encore l'agent Edge (M3-M4) : sert à valider la
chaîne complète (lecture Modbus → mesure enregistrée) contre un appareil
réel ou le simulateur, un point à la fois, avant de construire l'agent qui
tournera en continu sur site.

Usage :
    python scripts/modbus_poll.py <tenant_id> <point_id> <host> [port] [registre]

Le point visé doit déjà exister et être validé (voir la console web,
registre d'un équipement). Registre par défaut : total_active_energy
(voir app.connectors.sdm120.SDM120_POINTS pour les noms disponibles).
"""

import sys
import uuid

from app.connectors.ingest import PointModbusMapping, poll_and_record
from app.connectors.sdm120 import SDM120_POINTS
from app.db import engine
from app.tenancy import set_tenant_context


def _find_register(name: str):
    for point in SDM120_POINTS:
        if point.name == name:
            return point
    known = ", ".join(point.name for point in SDM120_POINTS)
    raise SystemExit(f"Registre inconnu : {name} (connus : {known})")


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(
            "Usage : python scripts/modbus_poll.py <tenant_id> <point_id> <host> "
            "[port=502] [registre=total_active_energy]"
        )
    tenant_id = uuid.UUID(sys.argv[1])
    point_id = uuid.UUID(sys.argv[2])
    host = sys.argv[3]
    port = int(sys.argv[4]) if len(sys.argv) > 4 else 502
    register = _find_register(sys.argv[5] if len(sys.argv) > 5 else "total_active_energy")

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        summary = poll_and_record(
            connection,
            tenant_id=tenant_id,
            host=host,
            port=port,
            mappings=[PointModbusMapping(point_id=point_id, register=register)],
            source="sdm120",
        )
    print(summary)


if __name__ == "__main__":
    main()
