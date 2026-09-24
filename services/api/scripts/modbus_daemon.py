"""Démon de sondage Modbus : relève plusieurs points à intervalle régulier
(M3→M4).

Précurseur minimal de l'agent Edge : une seule boucle, pas de gestion de
flotte ni de PKI (DEFER, voir ADR 012 §2.10-2.12). Tous les points d'un même
appareil sont lus en une seule connexion Modbus (voir read_modbus_points),
puis enregistrés ensemble. Deux pannes distinctes, deux réponses
différentes :
- l'appareil est injoignable (Modbus) : rien à faire, on retentera au tour
  suivant, il n'y a pas de valeur à conserver puisqu'aucune n'a été lue ;
- la base est injoignable (réseau du site, coupure) après une lecture
  réussie : chaque valeur lue est mise dans un tampon local (fichier),
  jamais perdue, et repart avec les suivantes dès que la connexion revient.

Usage :
    python scripts/modbus_daemon.py --tenant <tenant_id> --host <host> \
        --point <point_id>:<registre> [--point <point_id>:<registre> ...] \
        [--port 502] [--interval 60] [--buffer fichier]

Exemple (deux points du même compteur SDM120) :
    python scripts/modbus_daemon.py --tenant ... --host 192.168.1.50 \
        --point 8f2c...:total_active_energy --point a11b...:voltage

Arrêt propre : Ctrl+C ou SIGTERM. Le tampon, s'il contient des mesures en
attente, reste sur disque et sera renvoyé au prochain démarrage.
"""

import argparse
import logging
import signal
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

from app.connectors.ingest import PointModbusMapping
from app.connectors.modbus import ModbusReadError, find_register_by_name, read_modbus_points
from app.connectors.offline_buffer import BufferedReading, OfflineBuffer
from app.connectors.sdm120 import SDM120_POINTS
from app.db import engine
from app.observability import configure_logging
from app.telemetry import ingest_measurements
from app.tenancy import set_tenant_context

logger = logging.getLogger("paios.modbus_daemon")

_stop = False


def _handle_stop(signum: int, frame: FrameType | None) -> None:
    global _stop
    _stop = True


def run(
    *,
    tenant_id: uuid.UUID,
    host: str,
    port: int,
    mappings: list[PointModbusMapping],
    interval_seconds: float,
    buffer: OfflineBuffer,
    source: str = "sdm120",
    max_cycles: int | None = None,
) -> int:
    """Boucle de sondage. `max_cycles` (réservé aux tests) arrête après N
    tours au lieu d'attendre Ctrl+C ; renvoie le nombre de tours effectués."""
    logger.info(
        f"démon Modbus démarré : {host}:{port}, {len(mappings)} point(s), "
        f"toutes les {interval_seconds:g}s"
    )

    cycles_done = 0
    while not _stop and (max_cycles is None or cycles_done < max_cycles):
        cycle_started = time.monotonic()
        try:
            values = read_modbus_points(host, port, [m.register for m in mappings])
        except ModbusReadError as exc:
            logger.error(f"lecture impossible, nouvelle tentative au prochain tour : {exc}")
        else:
            now = datetime.now(UTC)
            new_readings = [
                BufferedReading(
                    tenant_id=tenant_id,
                    point_id=mapping.point_id,
                    value=values[mapping.register.name],
                    measured_at=now,
                    origin="measured",
                    source=source,
                )
                for mapping in mappings
            ]
            pending = buffer.pending()
            items = [reading.as_item() for reading in pending + new_readings]
            try:
                with engine.begin() as connection:
                    set_tenant_context(connection, tenant_id)
                    summary = ingest_measurements(
                        connection,
                        tenant_id=tenant_id,
                        items=items,
                        source=source,
                        received_at=now,
                    )
                buffer.clear()
                renvoi = f", {len(pending)} mesure(s) en tampon renvoyée(s)" if pending else ""
                logger.info(f"relève effectuée{renvoi} : {summary}")
            except Exception as exc:  # noqa: BLE001 — coupure BD : les mesures partent au tampon.
                for reading in new_readings:
                    buffer.append(reading)
                logger.error(
                    f"base injoignable, {len(new_readings)} mesure(s) mise(s) en tampon local "
                    f"({len(pending) + len(new_readings)} en attente au total) : {exc}"
                )
        cycles_done += 1

        remaining = interval_seconds - (time.monotonic() - cycle_started)
        more_to_come = not _stop and (max_cycles is None or cycles_done < max_cycles)
        if remaining > 0 and more_to_come:
            time.sleep(remaining)

    logger.info("démon Modbus arrêté")
    return cycles_done


def _parse_mapping(raw: str) -> PointModbusMapping:
    try:
        point_id_text, register_name = raw.split(":", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--point attend <point_id>:<registre>, reçu : {raw!r}"
        ) from exc
    try:
        point_id = uuid.UUID(point_id_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"point_id invalide : {point_id_text!r}") from exc
    try:
        register = find_register_by_name(SDM120_POINTS, register_name)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return PointModbusMapping(point_id=point_id, register=register)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tenant", required=True, type=uuid.UUID, help="Identifiant du client")
    parser.add_argument("--host", required=True, help="Adresse de l'appareil Modbus")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument(
        "--point",
        dest="mappings",
        required=True,
        action="append",
        type=_parse_mapping,
        metavar="POINT_ID:REGISTRE",
        help="Un point du registre associé à un nom de registre SDM120 ; répétable",
    )
    parser.add_argument("--interval", type=float, default=60.0, help="Secondes entre deux tours")
    parser.add_argument("--buffer", type=Path, default=None, help="Fichier du tampon hors ligne")
    parser.add_argument("--source", default="sdm120")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = _parse_args()
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    buffer_path = args.buffer or Path(f"modbus_buffer_{args.tenant}.jsonl")
    run(
        tenant_id=args.tenant,
        host=args.host,
        port=args.port,
        mappings=args.mappings,
        interval_seconds=args.interval,
        buffer=OfflineBuffer(buffer_path),
        source=args.source,
    )


if __name__ == "__main__":
    main()
