"""Démon de sondage Modbus : relève un équipement à intervalle régulier
(M4). Parle à l'API par HTTP avec sa propre identité d'appareil — plus
aucun accès direct à la base de données (voir app/routers/devices.py,
app/connectors/edge_client.py).

La configuration (adresse de l'appareil, association point ↔ registre)
vient de GET /edge/config, relue à chaque tour : un changement fait depuis
la console web prend effet au tour suivant, sans redémarrage. Trois pannes
distinctes, trois réponses différentes :
- l'appareil Modbus est injoignable : rien à faire, on retentera au tour
  suivant, il n'y a pas de valeur à conserver puisqu'aucune n'a été lue ;
- l'API est injoignable après une lecture réussie : chaque valeur lue est
  mise dans un tampon local (fichier), jamais perdue, et repart avec les
  suivantes dès que la connexion revient ;
- aucune configuration active (jamais créée, ou retirée entre deux tours) :
  on journalise et on retente au tour suivant, jamais une exception qui
  arrêterait le démon.

Usage :
    python scripts/modbus_daemon.py --api-url http://localhost:8000 \
        --tenant <tenant_id> --device-id sdm120-cpt01 --equipment <id> \
        [--secret <secret> | variable d'environnement EDGE_DEVICE_SECRET] \
        [--interval 60] [--buffer fichier]

Arrêt propre : Ctrl+C ou SIGTERM. Le tampon, s'il contient des mesures en
attente, reste sur disque et sera renvoyé au prochain démarrage.
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

from app.connectors.edge_client import EdgeApiClient, PrivateKeyCredential
from app.connectors.modbus import ModbusReadError, find_register_by_name, read_modbus_points
from app.connectors.offline_buffer import BufferedReading, OfflineBuffer
from app.connectors.sdm120 import SDM120_POINTS
from app.connectors.simulated_actuator import write_modbus_coil
from app.connectors.simulated_relay import SIMULATED_RELAY_POINTS
from app.observability import configure_logging

logger = logging.getLogger("paios.modbus_daemon")

# Catalogues de registres connus de ce démon, par device_type — même
# principe que app/connectors/device_mapping.py côté API, dupliqué ici
# volontairement : le démon ne dépend plus des modules liés à la base.
DEVICE_REGISTER_CATALOGS = {"sdm120": SDM120_POINTS, "simulated_relay": SIMULATED_RELAY_POINTS}

# Les seuls device_type pour lesquels le démon va chercher des commandes en
# attente — même liste que SIMULATED_DEVICE_TYPES côté API
# (app/connectors/device_mapping.py), dupliquée ici pour la même raison que
# DEVICE_REGISTER_CATALOGS. Exception scopée à la règle non négociable 1 de
# CLAUDE.md : jamais le sdm120, jamais un vrai appareil.
COMMANDABLE_DEVICE_TYPES = {"simulated_relay"}

_stop = False


def _handle_stop(signum: int, frame: FrameType | None) -> None:
    global _stop
    _stop = True


def _load_config(
    api: EdgeApiClient, equipment_id: uuid.UUID
) -> tuple[str, int, str, list[tuple[uuid.UUID, object]]] | None:
    """None si aucune configuration active. Sinon (host, port, device_type,
    [(point_id, registre), ...])."""
    content = api.get_config(equipment_id)
    if content is None:
        return None
    catalog = DEVICE_REGISTER_CATALOGS[content["device_type"]]
    mappings = [
        (uuid.UUID(entry["point_id"]), find_register_by_name(catalog, entry["register_name"]))
        for entry in content["points"]
    ]
    return content["host"], content["port"], content["device_type"], mappings


def _execute_pending_commands(
    api: EdgeApiClient,
    *,
    equipment_id: uuid.UUID,
    host: str,
    port: int,
    mappings: list[tuple[uuid.UUID, object]],
) -> None:
    """Récupère les commandes en attente pour cet équipement et les exécute
    une à une : écriture de la bobine, relecture, accusé de réception. Une
    commande dont l'exécution échoue n'empêche pas les suivantes."""
    try:
        pending_commands = api.get_pending_commands(equipment_id)
    except httpx.HTTPError as exc:
        logger.error(
            f"API injoignable pour les commandes, nouvelle tentative au prochain tour : {exc}"
        )
        return

    register_by_point = dict(mappings)
    for command in pending_commands:
        point_id = uuid.UUID(command["point_id"])
        register = register_by_point.get(point_id)
        failure_reason = None
        actual_value = None
        success = False
        if register is None:
            failure_reason = "COMMAND_POINT_NOT_IN_CONFIG"
        else:
            try:
                write_modbus_coil(host, port, register.address, bool(command["requested_value"]))
                actual_value = read_modbus_points(host, port, [register])[register.name]
                success = True
            except ModbusReadError as exc:
                failure_reason = "MODBUS_WRITE_ERROR"
                logger.error(f"exécution de la commande {command['id']} impossible : {exc}")

        try:
            api.acknowledge_command(
                command["id"],
                success=success,
                actual_value=actual_value,
                failure_reason=failure_reason,
            )
            logger.info(f"commande {command['id']} : succès={success} valeur={actual_value}")
        except httpx.HTTPError as exc:
            logger.error(f"impossible d'accuser réception de la commande {command['id']} : {exc}")


def run(
    *,
    api: EdgeApiClient,
    equipment_id: uuid.UUID,
    interval_seconds: float,
    buffer: OfflineBuffer,
    source: str = "sdm120",
    max_cycles: int | None = None,
) -> int:
    """Boucle de sondage. `max_cycles` (réservé aux tests) arrête après N
    tours au lieu d'attendre Ctrl+C ; renvoie le nombre de tours effectués."""
    if _load_config(api, equipment_id) is None:
        raise SystemExit(
            f"Aucune configuration Modbus active pour l'équipement {equipment_id} "
            "(console web : Connexion Modbus, ou POST /configs puis /activate)."
        )
    logger.info(f"démon Modbus démarré, toutes les {interval_seconds:g}s")

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
                    "aucune configuration Modbus active pour cet équipement, "
                    "nouvelle tentative au prochain tour"
                )

        if resolved is not None:
            host, port, device_type, mappings = resolved
            if device_type in COMMANDABLE_DEVICE_TYPES:
                _execute_pending_commands(
                    api, equipment_id=equipment_id, host=host, port=port, mappings=mappings
                )
            try:
                values = read_modbus_points(host, port, [register for _, register in mappings])
            except ModbusReadError as exc:
                logger.error(f"lecture impossible, nouvelle tentative au prochain tour : {exc}")
            else:
                now = datetime.now(UTC)
                new_readings = [
                    BufferedReading(
                        tenant_id=api.tenant_id,
                        point_id=point_id,
                        value=values[register.name],
                        measured_at=now,
                        origin="measured",
                        source=source,
                    )
                    for point_id, register in mappings
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

    logger.info("démon Modbus arrêté")
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
    parser.add_argument("--source", default="sdm120")
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
    buffer_path = args.buffer or Path(f"modbus_buffer_{args.equipment}.jsonl")

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
