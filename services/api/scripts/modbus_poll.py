"""Relève manuelle : lit un équipement par Modbus et enregistre la mesure.

Outil de développement, pas encore l'agent Edge (M3-M4) : un seul tour, pas
de tampon hors ligne (voir scripts/modbus_daemon.py pour la boucle continue
et la résilience aux coupures). Utile pour vérifier qu'une configuration
Modbus fraîchement activée fonctionne, avant de lancer le démon.

L'équipement visé doit avoir une configuration « modbus_device_mapping »
active (console web : Connexion Modbus, ou API /configs).

Usage :
    python scripts/modbus_poll.py <tenant_id> <equipment_id>
"""

import sys
import uuid

from app.connectors.device_mapping import resolve_active_mapping
from app.connectors.ingest import poll_and_record
from app.db import engine
from app.tenancy import set_tenant_context


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Usage : python scripts/modbus_poll.py <tenant_id> <equipment_id>")
    tenant_id = uuid.UUID(sys.argv[1])
    equipment_id = uuid.UUID(sys.argv[2])

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        resolved = resolve_active_mapping(connection, equipment_id=equipment_id)
    if resolved is None:
        raise SystemExit(
            f"Aucune configuration Modbus active pour l'équipement {equipment_id} "
            "(console web : Connexion Modbus, ou POST /configs puis /activate)."
        )
    host, port, mappings = resolved

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        summary = poll_and_record(
            connection,
            tenant_id=tenant_id,
            host=host,
            port=port,
            mappings=mappings,
            source="sdm120",
        )
    print(summary)


if __name__ == "__main__":
    main()
