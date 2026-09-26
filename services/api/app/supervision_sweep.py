"""Balayage périodique de supervision (directive de Mohamed du 24/09/2026,
complément) : LA SUPERVISION DOIT FONCTIONNER MÊME LORSQU'AUCUN UTILISATEUR
NE CONSULTE L'APPLICATION.

app/monitoring.py porte déjà toute la politique (État → Événement →
Politique → Alerte) ; jusqu'ici elle n'était évaluée qu'à la prochaine
lecture d'un point de lecture dédié (GET /functional-locations/{id}/status,
GET /points/{id}/trust). Ce module ajoute l'appelant manquant : un balayage
de toute la flotte, tenant par tenant, qui appelle exactement les mêmes
fonctions — aucune nouvelle logique d'alerte, aucune duplication de la
politique.

Pas de nouveau composant d'infrastructure : `sweep_once` est une fonction
pure côté base de données, appelable aussi bien depuis une boucle locale
(`scripts/supervision_sweep.py --interval`) que depuis une tâche planifiée
externe qui exécute le script une fois puis s'arrête (Railway Cron Jobs en
production : un service qui se réveille sur un horaire, pas un processus
permanent de plus).

Chaque tenant est isolé dans sa propre transaction avec son propre contexte
RLS (`set_tenant_context`) : une erreur sur un tenant est journalisée et
n'empêche jamais le balayage des suivants. La table `tenants` elle-même
n'est pas soumise à la RLS (registre racine, jamais une donnée métier) :
elle peut donc être listée avant de balayer chaque tenant séparément.

Communication et fraîcheur de donnée restent deux axes indépendants (même
principe que app/equipment_status.py) : un équipement peut rester "online"
au sens de ses points d'état pendant qu'un point de mesure particulier
devient "stale" faute de relevé récent — deux constats séparés, avec leurs
propres clés de déduplication et leurs propres événements.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.equipment_status import compute_equipment_status
from app.monitoring import evaluate_communication_status, evaluate_data_freshness
from app.points import list_points
from app.tenancy import set_tenant_context
from app.trust import compute_trust

logger = logging.getLogger("paios.supervision_sweep")


def _all_tenant_ids(engine: Engine) -> list[uuid.UUID]:
    with engine.connect() as connection:
        return [row[0] for row in connection.execute(text("SELECT id FROM tenants"))]


def _sweep_tenant(connection: Connection, tenant_id: uuid.UUID, at: datetime) -> dict[str, int]:
    counts = {"equipment_evaluated": 0, "points_evaluated": 0}

    locations = (
        connection.execute(text("SELECT id, code FROM functional_locations")).mappings().all()
    )
    for location in locations:
        status = compute_equipment_status(connection, location["id"], at)
        if status["communication_status"] == "unknown":
            # Aucune donnée exploitable : on ne sait pas encore, jamais
            # affirmé comme "en ligne" ni "hors ligne" (même règle que
            # app/equipment_status.py et evaluate_communication_status).
            continue
        evaluate_communication_status(
            connection,
            tenant_id=tenant_id,
            functional_location_id=location["id"],
            location_code=location["code"],
            status=status,
            at=at,
        )
        counts["equipment_evaluated"] += 1

    for point in list_points(connection):
        if point["expected_interval_seconds"] is None:
            # Sans intervalle attendu, la fraîcheur ne peut pas être
            # affirmée (même choix que pour la communication ci-dessus).
            continue
        trust = compute_trust(connection, point, at)
        evaluate_data_freshness(connection, tenant_id=tenant_id, point=point, trust=trust, at=at)
        counts["points_evaluated"] += 1

    return counts


def sweep_once(engine: Engine, *, at: datetime | None = None) -> dict[str, Any]:
    """Un tour complet de balayage, tous tenants confondus. Ne lève jamais
    d'exception pour un tenant en échec : les suivants sont quand même
    balayés, et l'échec est compté dans le résumé renvoyé."""
    at = at or datetime.now(UTC)
    summary = {
        "tenants_ok": 0,
        "tenants_failed": 0,
        "equipment_evaluated": 0,
        "points_evaluated": 0,
    }
    for tenant_id in _all_tenant_ids(engine):
        try:
            with engine.begin() as connection:
                set_tenant_context(connection, tenant_id)
                counts = _sweep_tenant(connection, tenant_id, at)
            summary["tenants_ok"] += 1
            summary["equipment_evaluated"] += counts["equipment_evaluated"]
            summary["points_evaluated"] += counts["points_evaluated"]
        except Exception:
            logger.exception(f"balayage du tenant {tenant_id} interrompu, on continue")
            summary["tenants_failed"] += 1
    return summary
