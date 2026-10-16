"""Ancrage externe du journal d'audit (voir feature-benchmark-matrix.md,
ligne "Journal d'audit append-only chaîné par hachage" : ancrage externe
signalé comme restant à faire).

Le chaînage interne (`app/audit.py`, `verify_chain_integrity`) détecte
qu'une entrée déjà écrite a été modifiée ou supprimée : chaque entrée porte
le hachage de la précédente, donc toucher une entrée casse la chaîne à
partir de ce point. Mais quelqu'un avec un accès complet à Postgres (erreur
d'exploitation, identifiants de service compromis — pas le fonctionnement
normal de l'application, qui ne permet ni UPDATE ni DELETE sur cette table,
voir la migration 5929036bce23) pourrait réécrire la chaîne en entier depuis
le début, hachages recalculés à la suite : la vérification interne ne
verrait plus rien d'anormal, puisqu'elle ne compare la chaîne qu'à
elle-même.

Ce module ne change rien à `app/audit.py` : il ajoute un témoin extérieur.
Chaque tour, pour chaque tenant qui a au moins une entrée, il journalise le
dernier hachage connu (`seq`, `entry_hash`) dans les journaux applicatifs
(sortie standard, voir app/observability.py), conservés par l'hébergeur
indépendamment de Postgres. Un attaquant qui ne contrôle que la base ne peut
plus réécrire la chaîne sans que cela se voie : il faudrait aussi altérer un
système de journalisation séparé, déjà expédié.

Même isolation par tenant que app/supervision_sweep.py : une erreur sur un
tenant ne bloque jamais l'ancrage des suivants.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.tenancy import set_tenant_context

logger = logging.getLogger("paios.audit_anchor")


def _all_tenant_ids(engine: Engine) -> list[uuid.UUID]:
    with engine.connect() as connection:
        return [row[0] for row in connection.execute(text("SELECT id FROM tenants"))]


def _anchor_tenant(connection: Connection, tenant_id: uuid.UUID) -> bool:
    """Renvoie True si une entrée a été ancrée, False si ce tenant n'a
    encore aucune entrée (rien à ancrer)."""
    row = (
        connection.execute(
            text(
                "SELECT seq, entry_hash FROM audit_log WHERE tenant_id = :tenant_id "
                "ORDER BY seq DESC LIMIT 1"
            ),
            {"tenant_id": tenant_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return False

    # "audit_tenant_id" et non "tenant_id" : ce dernier champ est réservé au
    # contexte d'une requête HTTP (voir app/observability.py) et injecté sur
    # chaque ligne de log dès qu'une requête a été traitée dans ce
    # processus — le réutiliser ici lève une erreur ("Attempt to overwrite").
    logger.info(
        "ancrage du journal d'audit",
        extra={
            "event": "audit.anchored",
            "audit_tenant_id": str(tenant_id),
            "seq": row["seq"],
            "entry_hash": row["entry_hash"],
        },
    )
    return True


def anchor_once(engine: Engine) -> dict[str, Any]:
    """Un tour complet d'ancrage, tous tenants confondus. Ne lève jamais
    d'exception pour un tenant en échec : les suivants sont quand même
    ancrés, et l'échec est compté dans le résumé renvoyé."""
    summary = {"tenants_anchored": 0, "tenants_empty": 0, "tenants_failed": 0}
    for tenant_id in _all_tenant_ids(engine):
        try:
            with engine.begin() as connection:
                set_tenant_context(connection, tenant_id)
                anchored = _anchor_tenant(connection, tenant_id)
            if anchored:
                summary["tenants_anchored"] += 1
            else:
                summary["tenants_empty"] += 1
        except Exception:
            logger.exception(f"ancrage du tenant {tenant_id} interrompu, on continue")
            summary["tenants_failed"] += 1
    return summary
