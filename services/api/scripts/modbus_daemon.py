"""Démon de sondage Modbus : relève un point à intervalle régulier (M3→M4).

Précurseur minimal de l'agent Edge : une seule boucle, un seul point, pas de
gestion de flotte ni de PKI (DEFER, voir ADR 012 §2.10-2.12). Deux pannes
distinctes, deux réponses différentes :
- l'appareil est injoignable (Modbus) : rien à faire, on retentera au tour
  suivant, il n'y a pas de valeur à conserver puisqu'aucune n'a été lue ;
- la base est injoignable (réseau du site, coupure) après une lecture
  réussie : la valeur est mise dans un tampon local (fichier), jamais
  perdue, et repart avec les suivantes dès que la connexion revient.

Usage :
    python scripts/modbus_daemon.py <tenant_id> <point_id> <host> \
        [port=502] [registre=total_active_energy] [intervalle_secondes=60] \
        [fichier_tampon]

Arrêt propre : Ctrl+C ou SIGTERM. Le tampon, s'il contient des mesures en
attente, reste sur disque et sera renvoyé au prochain démarrage.
"""

import logging
import signal
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

from app.connectors.modbus import (
    ModbusReadError,
    ModbusRegisterPoint,
    find_register_by_name,
    read_modbus_points,
)
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
    point_id: uuid.UUID,
    host: str,
    port: int,
    register: ModbusRegisterPoint,
    interval_seconds: float,
    buffer: OfflineBuffer,
    source: str = "sdm120",
    max_cycles: int | None = None,
) -> int:
    """Boucle de sondage. `max_cycles` (réservé aux tests) arrête après N
    tours au lieu d'attendre Ctrl+C ; renvoie le nombre de tours effectués."""
    logger.info(f"démon Modbus démarré : {host}:{port}, toutes les {interval_seconds:g}s")

    cycles_done = 0
    while not _stop and (max_cycles is None or cycles_done < max_cycles):
        cycle_started = time.monotonic()
        try:
            values = read_modbus_points(host, port, [register])
        except ModbusReadError as exc:
            logger.error(f"lecture impossible, nouvelle tentative au prochain tour : {exc}")
        else:
            now = datetime.now(UTC)
            new_reading = BufferedReading(
                tenant_id=tenant_id,
                point_id=point_id,
                value=values[register.name],
                measured_at=now,
                origin="measured",
                source=source,
            )
            pending = buffer.pending()
            items = [reading.as_item() for reading in pending] + [new_reading.as_item()]
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
            except Exception as exc:  # noqa: BLE001 — coupure BD : la mesure part au tampon.
                buffer.append(new_reading)
                logger.error(
                    f"base injoignable, mesure mise en tampon local "
                    f"({len(pending) + 1} en attente) : {exc}"
                )
        cycles_done += 1

        remaining = interval_seconds - (time.monotonic() - cycle_started)
        more_to_come = not _stop and (max_cycles is None or cycles_done < max_cycles)
        if remaining > 0 and more_to_come:
            time.sleep(remaining)

    logger.info("démon Modbus arrêté")
    return cycles_done


def main() -> None:
    configure_logging()
    if len(sys.argv) < 4:
        raise SystemExit(
            "Usage : python scripts/modbus_daemon.py <tenant_id> <point_id> <host> "
            "[port=502] [registre=total_active_energy] [intervalle_secondes=60] "
            "[fichier_tampon]"
        )
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    point_id = uuid.UUID(sys.argv[2])
    try:
        register = find_register_by_name(
            SDM120_POINTS, sys.argv[5] if len(sys.argv) > 5 else "total_active_energy"
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    buffer_path = (
        Path(sys.argv[7]) if len(sys.argv) > 7 else Path(f"modbus_buffer_{point_id}.jsonl")
    )
    run(
        tenant_id=uuid.UUID(sys.argv[1]),
        point_id=point_id,
        host=sys.argv[3],
        port=int(sys.argv[4]) if len(sys.argv) > 4 else 502,
        register=register,
        interval_seconds=float(sys.argv[6]) if len(sys.argv) > 6 else 60.0,
        buffer=OfflineBuffer(buffer_path),
    )


if __name__ == "__main__":
    main()
