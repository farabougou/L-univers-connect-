"""Balayage périodique du moteur d'automatisation (V2, dernière priorité :
voir app/automation_rules.py pour les garde-fous complets). Même mécanisme
que app.supervision_sweep et app.scheduled_commands_sweep : un tenant en
échec n'empêche jamais le balayage des suivants.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.automation_rules import evaluate_automation_rules
from app.tenancy import set_tenant_context

logger = logging.getLogger("paios.automation_rules_sweep")


def _all_tenant_ids(engine: Engine) -> list[uuid.UUID]:
    with engine.connect() as connection:
        return [row[0] for row in connection.execute(text("SELECT id FROM tenants"))]


def sweep_once(engine: Engine, *, at: datetime | None = None) -> dict[str, Any]:
    """Un tour complet de balayage, tous tenants confondus. Ne lève jamais
    d'exception pour un tenant en échec : les suivants sont quand même
    balayés, et l'échec est compté dans le résumé renvoyé."""
    at = at or datetime.now(UTC)
    summary = {"tenants_ok": 0, "tenants_failed": 0, "fired": 0, "blocked": 0}
    for tenant_id in _all_tenant_ids(engine):
        try:
            with engine.begin() as connection:
                set_tenant_context(connection, tenant_id)
                results = evaluate_automation_rules(connection, tenant_id=tenant_id, at=at)
            summary["tenants_ok"] += 1
            summary["fired"] += sum(1 for r in results if r["status"] == "fired")
            summary["blocked"] += sum(1 for r in results if r["status"] == "blocked")
        except Exception:
            logger.exception(f"balayage du tenant {tenant_id} interrompu, on continue")
            summary["tenants_failed"] += 1
    return summary
