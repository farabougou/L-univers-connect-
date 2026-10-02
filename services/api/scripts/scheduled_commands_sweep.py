"""CLI du balayage périodique des commandes planifiées (voir
app/scheduled_commands_sweep.py).

Deux façons de l'exécuter, selon l'environnement :
- `--once` : un seul tour puis sortie immédiate. C'est le mode attendu par
  une tâche planifiée externe (Railway Cron Jobs en production) ;
- `--interval <secondes>` (par défaut, 30 s) : boucle locale, pour le
  développement ou tant qu'aucune tâche planifiée n'est encore configurée.
  Plus fréquent que le balayage de supervision (60 s) : une commande
  planifiée attend d'être dans la fenêtre passée, pas seulement détectée.

Usage :
    python scripts/scheduled_commands_sweep.py --once
    python scripts/scheduled_commands_sweep.py --interval 30
"""

import argparse
import logging
import signal
import time
from types import FrameType

from app.db import engine
from app.observability import configure_logging
from app.scheduled_commands_sweep import sweep_once

logger = logging.getLogger("paios.scheduled_commands_sweep")

_stop = False


def _handle_stop(signum: int, frame: FrameType | None) -> None:
    global _stop
    _stop = True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--once",
        action="store_true",
        help="Un seul tour de balayage puis sortie (tâche planifiée externe)",
    )
    parser.add_argument(
        "--interval", type=float, default=30.0, help="Secondes entre deux tours (mode boucle)"
    )
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = _parse_args()

    if args.once:
        summary = sweep_once(engine)
        logger.info(f"balayage terminé : {summary}")
        return

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    logger.info(f"balayage périodique démarré, toutes les {args.interval:g}s")
    while not _stop:
        cycle_started = time.monotonic()
        summary = sweep_once(engine)
        logger.info(f"balayage effectué : {summary}")
        remaining = args.interval - (time.monotonic() - cycle_started)
        if remaining > 0 and not _stop:
            time.sleep(remaining)
    logger.info("balayage périodique arrêté")


if __name__ == "__main__":
    main()
