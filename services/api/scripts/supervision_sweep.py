"""CLI du balayage périodique de supervision (voir app/supervision_sweep.py).

La supervision doit fonctionner même lorsqu'aucun utilisateur ne consulte
l'application (directive de Mohamed du 24/09/2026) : ce script est
l'appelant qui manquait, pas une nouvelle politique.

Deux façons de l'exécuter, selon l'environnement :
- `--once` : un seul tour puis sortie immédiate. C'est le mode attendu par
  une tâche planifiée externe — en production, un service Railway Cron Jobs
  qui exécute cette commande sur un horaire, sans processus permanent de
  plus ;
- `--interval <secondes>` (par défaut, 60 s) : boucle locale, pour le
  développement (`docker compose`) ou tant qu'aucune tâche planifiée n'est
  encore configurée.

Usage :
    python scripts/supervision_sweep.py --once
    python scripts/supervision_sweep.py --interval 60
"""

import argparse
import logging
import signal
import time
from types import FrameType

from app.db import engine
from app.observability import configure_logging
from app.supervision_sweep import sweep_once

logger = logging.getLogger("paios.supervision_sweep")

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
        "--interval", type=float, default=60.0, help="Secondes entre deux tours (mode boucle)"
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
