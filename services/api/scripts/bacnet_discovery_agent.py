"""Agent Edge de découverte BACnet/IP : exécute sur site les scans demandés
depuis la console web (directive de Mohamed, 30/09/2026 — « le terrain doit
servir à découvrir, comparer, mesurer, corriger, valider, pas à
développer sur place »).

Un appareil BACnet/IP vit sur le réseau local d'un site, injoignable depuis
l'API hébergée dans le cloud : `POST /bacnet-discovery/scan` ne fait donc
que créer une demande (lot en 'processing'), sans réseau. Cet agent, lancé
sur site, récupère les demandes en attente (`GET
/edge/bacnet-discovery/pending`), exécute réellement le dialogue BACnet
(`app.connectors.bacnet.discover_device`, `read_device_objects` — jamais
d'écriture, règle non négociable 1) et rapporte le résultat ou l'échec.

Même identité d'appareil, même modèle de portée que le démon de relève
(scripts/bacnet_daemon.py) : ce n'est pas le même rôle (celui-ci exécute des
scans ponctuels demandés par une personne, jamais une relève cyclique), mais
la même authentification par appareil peut servir aux deux si l'appareil
Edge du site porte les deux portées.

Usage :
    python scripts/bacnet_discovery_agent.py --api-url http://localhost:8000 \
        --tenant <tenant_id> --device-id bacnet-cta01 --equipment <id> \
        [--secret <secret> | variable d'environnement EDGE_DEVICE_SECRET] \
        [--interval 15] [--once]
"""

import argparse
import dataclasses
import logging
import os
import signal
import time
import uuid
from pathlib import Path
from types import FrameType

import httpx

from app.connectors.bacnet import BacnetReadError, discover_device, read_device_objects
from app.connectors.edge_client import EdgeApiClient, PrivateKeyCredential
from app.observability import configure_logging

logger = logging.getLogger("paios.bacnet_discovery_agent")

_stop = False


def _handle_stop(signum: int, frame: FrameType | None) -> None:
    global _stop
    _stop = True


def _execute_one(api: EdgeApiClient, batch: dict) -> None:
    """Exécute un scan demandé et rapporte toujours un résultat, même en
    échec (appareil injoignable, inventaire refusé) : jamais une exception
    qui laisserait le lot muet côté personne — même principe que le domaine
    avant qu'il ne s'exécute ici (voir app.bacnet_discovery)."""
    batch_id = uuid.UUID(batch["id"])
    address = batch["address"]
    timeout = float(batch["timeout_seconds"])
    logger.info(f"scan demandé pour {address} (lot {batch_id}, délai {timeout:g}s)")

    try:
        device_info = discover_device(address, timeout=timeout)
    except BacnetReadError as exc:
        logger.error(f"appareil injoignable à {address} : {exc}")
        _report_failure(api, batch_id, "BACNET_DEVICE_UNREACHABLE")
        return

    try:
        objects = read_device_objects(address, device_info.device_instance, timeout=timeout)
    except BacnetReadError as exc:
        logger.error(f"inventaire impossible pour {address} : {exc}")
        _report_failure(api, batch_id, "BACNET_INVENTORY_FAILED")
        return

    payload = [dataclasses.asdict(obj) for obj in objects]
    try:
        result = api.submit_bacnet_discovery_result(
            batch_id, device_instance=device_info.device_instance, objects=payload
        )
        logger.info(
            f"scan rapporté pour {address} : "
            f"{result['proposal_count']} proposition(s), {result['duplicate_count']} doublon(s)"
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            logger.info(f"lot {batch_id} déjà rapporté (probablement par un tour précédent)")
        else:
            raise


def _report_failure(api: EdgeApiClient, batch_id: uuid.UUID, error_code: str) -> None:
    try:
        api.submit_bacnet_discovery_failure(batch_id, error_code=error_code)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 409:
            raise


def run(
    *,
    api: EdgeApiClient,
    equipment_id: uuid.UUID,
    interval_seconds: float,
    max_cycles: int | None = None,
) -> int:
    """Boucle de sondage des scans en attente. `max_cycles` (réservé aux
    tests et à --once) arrête après N tours au lieu d'attendre Ctrl+C ;
    renvoie le nombre de tours effectués."""
    logger.info(f"agent de découverte BACnet démarré, toutes les {interval_seconds:g}s")

    cycles_done = 0
    while not _stop and (max_cycles is None or cycles_done < max_cycles):
        cycle_started = time.monotonic()
        try:
            pending = api.get_pending_bacnet_discovery(equipment_id)
        except httpx.HTTPError as exc:
            logger.error(f"API injoignable pour les scans en attente : {exc}")
            pending = []

        for batch in pending:
            try:
                _execute_one(api, batch)
            except httpx.HTTPError as exc:
                logger.error(f"API injoignable en rapportant le scan {batch['id']} : {exc}")

        cycles_done += 1
        remaining = interval_seconds - (time.monotonic() - cycle_started)
        more_to_come = not _stop and (max_cycles is None or cycles_done < max_cycles)
        if remaining > 0 and more_to_come:
            time.sleep(remaining)

    logger.info("agent de découverte BACnet arrêté")
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
    parser.add_argument(
        "--interval", type=float, default=15.0, help="Secondes entre deux vérifications"
    )
    parser.add_argument(
        "--once", action="store_true", help="Un seul tour, puis quitte (scan à la demande)"
    )
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
            max_cycles=1 if args.once else None,
        )


if __name__ == "__main__":
    main()
