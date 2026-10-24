"""Cohérence de la capacité déclarée (consolidation V5 du 21/10/2026).

Trois réglages doivent rester cohérents entre eux, et aucun ne l'était vérifié :

1. Les requêtes HTTP traitées en même temps (`max_in_flight_requests`) ne doivent
   jamais dépasser les connexions disponibles dans le pool. Au-dessus, on
   retrouve l'interblocage mesuré à 150 clients (voir app/admission.py) : la
   valeur est donc ramenée à la capacité du pool, avec un avertissement.
2. Le total de connexions de toutes les instances (pool × processus × répliques)
   doit tenir dans les connexions autorisées par PostgreSQL, moins une réserve
   pour l'administration, les migrations et les sauvegardes.
3. Des compteurs de débit en mémoire ne sont exacts qu'avec un seul processus.

La vérification a lieu au démarrage et ne bloque jamais le service : elle écrit
dans le journal ce qu'elle a constaté (valeurs lues sur la base réelle), pour
qu'un changement de configuration ou de plan d'hébergement ne casse pas la
plateforme en silence.
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import Settings

logger = logging.getLogger("paios.capacity")

# Connexions laissées à l'administration, aux migrations et aux sauvegardes.
CONNECTION_RESERVE = 10


@dataclass(frozen=True)
class CapacityFinding:
    code: str
    detail: dict[str, Any]


def pool_capacity(settings: Settings) -> int:
    return settings.db_pool_size + settings.db_max_overflow


def effective_max_in_flight(settings: Settings) -> int:
    """Requêtes simultanées admises par processus : la capacité du pool, ou moins
    si l'exploitation le demande ; jamais plus (voir l'en-tête du module)."""
    capacity = pool_capacity(settings)
    if settings.max_in_flight_requests <= 0:
        return capacity
    return min(settings.max_in_flight_requests, capacity)


def worker_count(environ: Mapping[str, str] | None = None) -> int:
    """Nombre de processus uvicorn : `WEB_CONCURRENCY`, comme uvicorn lui-même."""
    raw = (environ if environ is not None else os.environ).get("WEB_CONCURRENCY", "")
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def evaluate_capacity(
    settings: Settings, *, max_connections: int | None, workers: int
) -> list[CapacityFinding]:
    findings: list[CapacityFinding] = []
    capacity = pool_capacity(settings)

    if settings.max_in_flight_requests > capacity:
        findings.append(
            CapacityFinding(
                "admission_above_pool",
                {
                    "configured": settings.max_in_flight_requests,
                    "applied": effective_max_in_flight(settings),
                    "pool_capacity": capacity,
                },
            )
        )

    instances = workers * max(1, settings.expected_replicas)
    required = capacity * instances
    if max_connections is not None and required > max_connections - CONNECTION_RESERVE:
        findings.append(
            CapacityFinding(
                "connections_over_budget",
                {
                    "required": required,
                    "available": max_connections - CONNECTION_RESERVE,
                    "max_connections": max_connections,
                    "pool_capacity": capacity,
                    "instances": instances,
                },
            )
        )

    if settings.rate_limit_storage_uri.startswith("memory:") and instances > 1:
        findings.append(
            CapacityFinding(
                "rate_limit_not_shared",
                {"instances": instances, "storage": "memory"},
            )
        )
    return findings


def read_max_connections(engine: Engine) -> int | None:
    try:
        with engine.connect() as connection:
            return int(connection.execute(text("SHOW max_connections")).scalar_one())
    except Exception:
        return None


def report_capacity(engine: Engine, settings: Settings) -> list[CapacityFinding]:
    """Vérifie et journalise. Ne lève jamais : un échec de vérification ne doit
    pas empêcher le service de démarrer."""
    try:
        max_connections = read_max_connections(engine)
        workers = worker_count()
        findings = evaluate_capacity(settings, max_connections=max_connections, workers=workers)
        logger.info(
            "capacité déclarée",
            extra={
                "event": "capacity.checked",
                "detail": {
                    "pool_capacity": pool_capacity(settings),
                    "max_in_flight": effective_max_in_flight(settings),
                    "workers": workers,
                    "replicas": settings.expected_replicas,
                    "max_connections": max_connections,
                    "rate_limit_storage": settings.rate_limit_storage_uri.split(":")[0],
                    "client_ip_header": settings.client_ip_header or None,
                },
            },
        )
        for finding in findings:
            logger.warning(
                f"capacité incohérente : {finding.code}",
                extra={"event": f"capacity.{finding.code}", "detail": finding.detail},
            )
        return findings
    except Exception:
        logger.exception("vérification de la capacité impossible")
        return []
