"""CLI de l'ancrage externe du journal d'audit (voir app/audit_anchor.py).

Même principe d'exécution que scripts/supervision_sweep.py :
- `--once` : un seul tour puis sortie immédiate. Mode attendu par une tâche
  planifiée externe — en production, un service Railway Cron Jobs qui
  exécute cette commande sur un horaire, sans processus permanent de plus ;
- `--interval <secondes>` (par défaut, 3600 s) : boucle locale, pour le
  développement ou tant qu'aucune tâche planifiée n'est encore configurée.

Usage :
    python scripts/anchor_audit_log.py --once
    python scripts/anchor_audit_log.py --interval 3600
"""

import argparse
import logging
import signal
import time
from types import FrameType

from app.audit_anchor import anchor_once
from app.db import engine
from app.observability import configure_logging

logger = logging.getLogger("paios.audit_anchor")

_stop = False


def _handle_stop(signum: int, frame: FrameType | None) -> None:
    global _stop
    _stop = True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--once",
        action="store_true",
        help="Un seul tour d'ancrage puis sortie (tâche planifiée externe)",
    )
    parser.add_argument(
        "--interval", type=float, default=3600.0, help="Secondes entre deux tours (mode boucle)"
    )
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = _parse_args()

    if args.once:
        summary = anchor_once(engine)
        logger.info(f"ancrage terminé : {summary}")
        return

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    logger.info(f"ancrage périodique démarré, toutes les {args.interval:g}s")
    while not _stop:
        cycle_started = time.monotonic()
        summary = anchor_once(engine)
        logger.info(f"ancrage effectué : {summary}")
        remaining = args.interval - (time.monotonic() - cycle_started)
        if remaining > 0 and not _stop:
            time.sleep(remaining)
    logger.info("ancrage périodique arrêté")


if __name__ == "__main__":
    main()
