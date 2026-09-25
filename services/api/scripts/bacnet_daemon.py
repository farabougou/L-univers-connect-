"""Démon de sondage BACnet/IP : relève un équipement à intervalle régulier,
sur le même modèle que scripts/modbus_daemon.py (M4). Parle à l'API par
HTTP avec sa propre identité d'appareil — aucun accès direct à la base de
données (voir app/routers/devices.py, app/connectors/edge_client.py).

Contrairement à Modbus, BACnet ne connaît pas de "commande simulée" ici :
règle non négociable 1, aucune fonction d'écriture BACnet n'existe dans ce
dépôt (voir app/connectors/bacnet.py).

Usage :
    python scripts/bacnet_daemon.py --api-url http://localhost:8000 \
        --tenant <tenant_id> --device-id bacnet-cta01 --equipment <id> \
        [--secret <secret> | variable d'environnement EDGE_DEVICE_SECRET] \
        [--interval 60] [--buffer fichier]
"""

import argparse
import logging
import os
import signal
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

import httpx

from app.connectors.bacnet import BacnetPoint, BacnetReadError, read_bacnet_points
from app.connectors.edge_client import EdgeApiClient, PrivateKeyCredential
from app.connectors.offline_buffer import BufferedReading, OfflineBuffer
from app.observability import configure_logging

logger = logging.getLogger("paios.bacnet_daemon")

_stop = False


def _handle_stop(signum: int, frame: FrameType | None) -> None:
    global _stop
    _stop = True


def _load_config(
    api: EdgeApiClient, equipment_id: uuid.UUID
) -> tuple[str, list[tuple[uuid.UUID, BacnetPoint]]] | None:
    """None si aucune configuration active. Sinon (adresse BACnet, [(point_id, point), ...]).

    Le nom du point BACnet (utilisé comme clé du dictionnaire renvoyé par
    read_bacnet_points) est directement l'identifiant du point : contrairement
    à Modbus, il n'y a pas de nom de registre issu d'un catalogue fabricant.
    """
    content = api.get_bacnet_config(equipment_id)
    if content is None:
        return None
    mappings = [
        (
            uuid.UUID(entry["point_id"]),
            BacnetPoint(
                name=entry["point_id"],
                object_type=entry["object_type"],
                object_instance=entry["object_instance"],
                property_identifier=entry["property_identifier"],
                unit="",
            ),
        )
        for entry in content["points"]
    ]
    return content["address"], mappings


def run(
    *,
    api: EdgeApiClient,
    equipment_id: uuid.UUID,
    interval_seconds: float,
    buffer: OfflineBuffer,
    source: str = "bacnet",
    max_cycles: int | None = None,
) -> int:
    """Boucle de sondage. `max_cycles` (réservé aux tests) arrête après N
    tours au lieu d'attendre Ctrl+C ; renvoie le nombre de tours effectués."""
    if _load_config(api, equipment_id) is None:
        raise SystemExit(
            f"Aucune configuration BACnet active pour l'équipement {equipment_id} "
            "(console web : Connexion BACnet, ou POST /configs puis /activate)."
        )
    logger.info(f"démon BACnet démarré, toutes les {interval_seconds:g}s")

    cycles_done = 0
    while not _stop and (max_cycles is None or cycles_done < max_cycles):
        cycle_started = time.monotonic()
        resolved = None
        try:
            resolved = _load_config(api, equipment_id)
        except httpx.HTTPError as exc:
            logger.error(
                f"API injoignable pour la configuration, "
                f"nouvelle tentative au prochain tour : {exc}"
            )
        else:
            if resolved is None:
                logger.error(
                    "aucune configuration BACnet active pour cet équipement, "
                    "nouvelle tentative au prochain tour"
                )

        if resolved is not None:
            address, mappings = resolved
            try:
                values = read_bacnet_points(address, [point for _, point in mappings])
            except BacnetReadError as exc:
                logger.error(f"lecture impossible, nouvelle tentative au prochain tour : {exc}")
            else:
                now = datetime.now(UTC)
                new_readings = [
                    BufferedReading(
                        tenant_id=api.tenant_id,
                        point_id=point_id,
                        value=values[point.name],
                        measured_at=now,
                        origin="measured",
                        source=source,
                    )
                    for point_id, point in mappings
                ]
                pending = buffer.pending()
                items = [reading.as_http_item() for reading in pending + new_readings]
                try:
                    summary = api.post_measurements(items)
                    buffer.clear()
                    renvoi = f", {len(pending)} mesure(s) en tampon renvoyée(s)" if pending else ""
                    logger.info(f"relève effectuée{renvoi} : {summary}")
                except httpx.HTTPError as exc:
                    for reading in new_readings:
                        buffer.append(reading)
                    logger.error(
                        f"API injoignable, {len(new_readings)} mesure(s) mise(s) en tampon local "
                        f"({len(pending) + len(new_readings)} en attente au total) : {exc}"
                    )
        cycles_done += 1

        remaining = interval_seconds - (time.monotonic() - cycle_started)
        more_to_come = not _stop and (max_cycles is None or cycles_done < max_cycles)
        if remaining > 0 and more_to_come:
            time.sleep(remaining)

    logger.info("démon BACnet arrêté")
    return cycles_done


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
        help=(
            "Secret de l'appareil (par défaut : variable d'environnement "
            "EDGE_DEVICE_SECRET) — compatibilité uniquement, voir --private-key-file"
        ),
    )
    parser.add_argument(
        "--private-key-file",
        type=Path,
        default=os.environ.get("EDGE_DEVICE_PRIVATE_KEY_FILE"),
        help=(
            "Fichier de la clé privée de l'appareil (par défaut : variable "
            "d'environnement EDGE_DEVICE_PRIVATE_KEY_FILE) — modèle cible, voir "
            "scripts/generate_device_key.py. Remplace --secret, jamais les deux."
        ),
    )
    parser.add_argument(
        "--equipment",
        required=True,
        type=uuid.UUID,
        help="Identifiant de l'équipement (functional_location_id)",
    )
    parser.add_argument("--interval", type=float, default=60.0, help="Secondes entre deux tours")
    parser.add_argument("--buffer", type=Path, default=None, help="Fichier du tampon hors ligne")
    parser.add_argument("--source", default="bacnet")
    args = parser.parse_args()
    if bool(args.secret) == bool(args.private_key_file):
        parser.error(
            "indiquer exactement un de --secret ou --private-key-file "
            "(ou les variables d'environnement correspondantes)"
        )
    return args


def main() -> None:
    configure_logging()
    args = _parse_args()
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    buffer_path = args.buffer or Path(f"bacnet_buffer_{args.equipment}.jsonl")

    if args.private_key_file:
        credential = PrivateKeyCredential(
            private_key_pem=args.private_key_file.read_text(),
            device_id=args.device_id,
            tenant_id=args.tenant,
        )
        client_kwargs = {"credential": credential}
    else:
        client_kwargs = {"secret": args.secret}

    with EdgeApiClient(
        client=httpx.Client(base_url=args.api_url, timeout=10.0),
        tenant_id=args.tenant,
        device_id=args.device_id,
        **client_kwargs,
    ) as api:
        run(
            api=api,
            equipment_id=args.equipment,
            interval_seconds=args.interval,
            buffer=OfflineBuffer(buffer_path),
            source=args.source,
        )


if __name__ == "__main__":
    main()
