"""Relève manuelle : lit un équipement par Modbus et enregistre la mesure.

Outil de développement, pas la boucle continue (voir scripts/modbus_daemon.py
pour ça) : un seul tour, pas de tampon hors ligne. Utile pour vérifier
qu'une configuration Modbus fraîchement activée fonctionne, avant de lancer
le démon.

Depuis M4, ce script parle à l'API par HTTP avec une identité d'appareil
(voir scripts/modbus_daemon.py) — exactement le même chemin que le démon,
pour que « ça marche en manuel » garantisse que la vraie boucle marchera
aussi.

L'équipement visé doit avoir une configuration « modbus_device_mapping »
active (console web : Connexion Modbus, ou API /configs).

Usage :
    python scripts/modbus_poll.py --api-url http://localhost:8000 \
        --tenant <tenant_id> --device-id sdm120-cpt01 --equipment <id> \
        [--secret <secret> | variable d'environnement EDGE_DEVICE_SECRET]
"""

import argparse
import os
import uuid
from datetime import UTC, datetime

import httpx

from app.connectors.edge_client import EdgeApiClient
from app.connectors.modbus import find_register_by_name, read_modbus_points
from app.connectors.offline_buffer import BufferedReading
from app.connectors.sdm120 import SDM120_POINTS

DEVICE_REGISTER_CATALOGS = {"sdm120": SDM120_POINTS}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-url", default="http://localhost:8000", help="Base de l'API")
    parser.add_argument("--tenant", required=True, type=uuid.UUID, help="Identifiant du client")
    parser.add_argument(
        "--device-id", required=True, help="Identifiant de cet appareil (voir POST /devices)"
    )
    parser.add_argument(
        "--secret",
        default=os.environ.get("EDGE_DEVICE_SECRET"),
        help="Secret de l'appareil (par défaut : variable d'environnement EDGE_DEVICE_SECRET)",
    )
    parser.add_argument(
        "--equipment",
        required=True,
        type=uuid.UUID,
        help="Identifiant de l'équipement (functional_location_id)",
    )
    parser.add_argument("--source", default="sdm120")
    args = parser.parse_args()
    if not args.secret:
        parser.error("--secret requis (ou variable d'environnement EDGE_DEVICE_SECRET)")
    return args


def main() -> None:
    args = _parse_args()

    with EdgeApiClient(
        client=httpx.Client(base_url=args.api_url, timeout=10.0),
        tenant_id=args.tenant,
        device_id=args.device_id,
        secret=args.secret,
    ) as api:
        content = api.get_config(args.equipment)
        if content is None:
            raise SystemExit(
                f"Aucune configuration Modbus active pour l'équipement {args.equipment} "
                "(console web : Connexion Modbus, ou POST /configs puis /activate)."
            )
        catalog = DEVICE_REGISTER_CATALOGS[content["device_type"]]
        mappings = [
            (uuid.UUID(entry["point_id"]), find_register_by_name(catalog, entry["register_name"]))
            for entry in content["points"]
        ]

        now = datetime.now(UTC)
        values = read_modbus_points(
            content["host"], content["port"], [register for _, register in mappings]
        )
        items = [
            BufferedReading(
                tenant_id=args.tenant,
                point_id=point_id,
                value=values[register.name],
                measured_at=now,
                origin="measured",
                source=args.source,
            ).as_http_item()
            for point_id, register in mappings
        ]
        summary = api.post_measurements(items)
    print(summary)


if __name__ == "__main__":
    main()
