"""État des tâches planifiées (V4, priorité « Déploiement » : observabilité).

Les quatre balayages périodiques (`app/supervision_sweep.py`,
`app/scheduled_commands_sweep.py`, `app/automation_rules_sweep.py`,
`app/audit_anchor.py`) tournent déjà, chacun en isolant ses erreurs par
tenant ; jusqu'ici leur seule trace était une ligne de journal, perdue dès
que le processus qui l'a écrite se termine (le cas normal d'une tâche
planifiée externe : un conteneur par tour, voir Railway Cron Jobs — ADR
012, DEFERRED_EXTERNAL_DEPLOYMENT). Pour qu'on puisse répondre à « est-ce
que ça tourne encore ? » sans fouiller des journaux, chaque tour écrit une
ligne ici, lue par `GET /metrics` (app/metrics.py) — jamais un nouveau
tableau de bord, jamais une politique dupliquée.

Donnée de plateforme, jamais une donnée métier d'un tenant : un balayage
traite tous les tenants dans le même tour (voir migration
5d158928f01b). Insertion seulement — aucune fonction de ce module ne
modifie ou ne supprime une ligne déjà écrite.
"""

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


def record_job_run(
    connection: Connection,
    *,
    job_name: str,
    started_at: datetime,
    finished_at: datetime,
    succeeded: bool,
    summary: dict[str, Any],
    error: str | None = None,
) -> None:
    connection.execute(
        text(
            "INSERT INTO scheduled_job_runs "
            "(id, job_name, started_at, finished_at, succeeded, summary, error) "
            "VALUES (:id, :job_name, :started_at, :finished_at, :succeeded, "
            "CAST(:summary AS JSONB), :error)"
        ),
        {
            "id": uuid.uuid4(),
            "job_name": job_name,
            "started_at": started_at,
            "finished_at": finished_at,
            "succeeded": succeeded,
            "summary": json.dumps(summary, sort_keys=True, separators=(",", ":")),
            "error": error,
        },
    )


def run_and_record(
    engine: Engine, *, job_name: str, run_once: Callable[[], dict[str, Any]]
) -> dict[str, Any]:
    """Exécute `run_once` (un tour de balayage), enregistre toujours le
    résultat — succès avec son résumé, ou échec avec le message de
    l'exception — puis relaie cette exception à l'appelant si elle a eu
    lieu : la trace écrite ne doit jamais faire paraître un tour comme
    réussi s'il ne l'a pas été, et l'appelant garde son propre
    comportement (sortie en erreur en mode --once, par exemple)."""
    started_at = datetime.now(UTC)
    succeeded = False
    summary: dict[str, Any] = {}
    error: str | None = None
    try:
        summary = run_once()
        succeeded = True
        return summary
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        finished_at = datetime.now(UTC)
        with engine.begin() as connection:
            record_job_run(
                connection,
                job_name=job_name,
                started_at=started_at,
                finished_at=finished_at,
                succeeded=succeeded,
                summary=summary,
                error=error,
            )


def latest_job_runs(connection: Connection) -> list[dict[str, Any]]:
    """Le dernier tour connu de chaque tâche, le plus récent d'abord —
    jamais l'historique complet, qui n'a pas d'usage ici (GET /metrics
    n'affiche qu'un état courant)."""
    rows = connection.execute(
        text(
            "SELECT DISTINCT ON (job_name) job_name, started_at, finished_at, "
            "succeeded, summary, error "
            "FROM scheduled_job_runs ORDER BY job_name, started_at DESC"
        )
    ).mappings()
    return [dict(row) for row in rows]
