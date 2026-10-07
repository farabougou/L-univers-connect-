"""Balayage périodique des commandes planifiées (V2, 02/10/2026) — même
mécanisme que app.supervision_sweep : une commande planifiée doit se
déclencher même si personne ne consulte l'application au moment voulu.

Chaque tenant est isolé dans sa propre transaction avec son propre contexte
RLS (set_tenant_context) : un échec sur un tenant est journalisé et
n'empêche jamais le balayage des suivants.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.scheduled_commands import dispatch_due_scheduled_commands
from app.tenancy import set_tenant_context

logger = logging.getLogger("paios.scheduled_commands_sweep")


def _all_tenant_ids(engine: Engine) -> list[uuid.UUID]:
    with engine.connect() as connection:
        return [row[0] for row in connection.execute(text("SELECT id FROM tenants"))]


def sweep_once(engine: Engine, *, at: datetime | None = None) -> dict[str, Any]:
    """Un tour complet de balayage, tous tenants confondus. Ne lève jamais
    d'exception pour un tenant en échec : les suivants sont quand même
    balayés, et l'échec est compté dans le résumé renvoyé."""
    at = at or datetime.now(UTC)
    summary = {"tenants_ok": 0, "tenants_failed": 0, "dispatched": 0, "failed": 0}
    for tenant_id in _all_tenant_ids(engine):
        try:
            with engine.begin() as connection:
                set_tenant_context(connection, tenant_id)
                results = dispatch_due_scheduled_commands(connection, tenant_id=tenant_id, at=at)
            summary["tenants_ok"] += 1
            summary["dispatched"] += sum(1 for r in results if r["status"] == "dispatched")
            summary["failed"] += sum(1 for r in results if r["status"] == "failed")
        except Exception:
            logger.exception(f"balayage du tenant {tenant_id} interrompu, on continue")
            summary["tenants_failed"] += 1
    return summary
