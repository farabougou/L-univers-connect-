"""Démon de sondage Modbus : relève un point à intervalle régulier (M3→M4).

Précurseur minimal de l'agent Edge : une seule boucle, un seul point, pas de
tampon hors ligne ni de gestion de flotte (DEFER, voir ADR 012 §2.10-2.12).
Un cycle en échec (réseau, appareil éteint) n'arrête jamais les suivants :
c'est le seul comportement d'un composant censé tourner sans surveillance.

Usage :
    python scripts/modbus_daemon.py <tenant_id> <point_id> <host> \
        [port=502] [registre=total_active_energy] [intervalle_secondes=60]

Arrêt propre : Ctrl+C ou SIGTERM.
"""

import logging
import signal
import sys
import time
import uuid
from types import FrameType

from app.connectors.ingest import PointModbusMapping, poll_and_record
from app.connectors.modbus import ModbusRegisterPoint, find_register_by_name
from app.connectors.sdm120 import SDM120_POINTS
from app.db import engine
from app.observability import configure_logging
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
    max_cycles: int | None = None,
) -> int:
    """Boucle de sondage. `max_cycles` (réservé aux tests) arrête après N
    tours au lieu d'attendre Ctrl+C ; renvoie le nombre de tours effectués."""
    mapping = PointModbusMapping(point_id=point_id, register=register)
    logger.info(f"démon Modbus démarré : {host}:{port}, toutes les {interval_seconds:g}s")

    cycles_done = 0
    while not _stop and (max_cycles is None or cycles_done < max_cycles):
        cycle_started = time.monotonic()
        try:
            with engine.begin() as connection:
                set_tenant_context(connection, tenant_id)
                summary = poll_and_record(
                    connection,
                    tenant_id=tenant_id,
                    host=host,
                    port=port,
                    mappings=[mapping],
                    source="sdm120",
                )
            logger.info(f"relève effectuée : {summary}")
        except Exception as exc:  # noqa: BLE001 — un cycle raté ne doit jamais arrêter le démon.
            logger.error(f"relève impossible, nouvelle tentative au prochain tour : {exc}")
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
            "[port=502] [registre=total_active_energy] [intervalle_secondes=60]"
        )
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    try:
        register = find_register_by_name(
            SDM120_POINTS, sys.argv[5] if len(sys.argv) > 5 else "total_active_energy"
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    run(
        tenant_id=uuid.UUID(sys.argv[1]),
        point_id=uuid.UUID(sys.argv[2]),
        host=sys.argv[3],
        port=int(sys.argv[4]) if len(sys.argv) > 4 else 502,
        register=register,
        interval_seconds=float(sys.argv[6]) if len(sys.argv) > 6 else 60.0,
    )


if __name__ == "__main__":
    main()
