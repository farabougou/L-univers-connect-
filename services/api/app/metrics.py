"""Métriques HTTP et tâches planifiées, format Prometheus
(feature-benchmark-matrix.md, ligne « Observabilité (logs structurés,
métriques, traces, fraîcheur) » : les logs structurés existent depuis F6 ;
V4 (priorité « Déploiement ») ajoute l'état des tâches planifiées.

Compte les requêtes par méthode/route/statut et leur durée, sans rien
ajouter au chemin d'une requête (le décompte se fait où le journal
« requête traitée » s'écrit déjà, app/observability.py). Jamais de donnée
métier ni par tenant ici : seulement des agrégats sur l'ensemble du
service, exposés sans authentification comme /health — même niveau de
sensibilité.

Les jauges de tâches planifiées (`paios_job_last_run_*`) ne peuvent pas
être tenues à jour en mémoire comme les compteurs HTTP ci-dessus : chaque
tour de balayage s'exécute dans son propre processus, de courte durée
(`scripts/*.py --once`, appelé par une tâche planifiée externe — voir
app/job_runs.py), jamais celui qui sert /metrics. Elles sont donc
recalculées à chaque lecture de /metrics depuis `scheduled_job_runs`
(dernier tour connu de chaque tâche), pas accumulées ici.

`prometheus_client` (Apache-2.0, projet de référence du format
d'exposition, aucune dépendance) : une bibliothèque de mise en forme, pas
un service — rien à héberger, rien à acheter pour que ce module ait de la
valeur dès aujourd'hui (une personne peut lire /metrics directement).
"""

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client import generate_latest as _generate_latest
from sqlalchemy.engine import Connection

from app.job_runs import latest_job_runs

REGISTRY = CollectorRegistry()

REQUEST_COUNT = Counter(
    "paios_http_requests_total",
    "Nombre de requêtes HTTP traitées, par méthode, route et code de statut.",
    ["method", "route", "status"],
    registry=REGISTRY,
)
REQUEST_DURATION_SECONDS = Histogram(
    "paios_http_request_duration_seconds",
    "Durée des requêtes HTTP, par méthode et route.",
    ["method", "route"],
    registry=REGISTRY,
)
JOB_LAST_RUN_TIMESTAMP_SECONDS = Gauge(
    "paios_job_last_run_timestamp_seconds",
    "Horodatage (epoch) de fin du dernier tour connu de cette tâche planifiée.",
    ["job"],
    registry=REGISTRY,
)
JOB_LAST_RUN_SUCCESS = Gauge(
    "paios_job_last_run_success",
    "1 si le dernier tour connu de cette tâche a réussi, 0 sinon.",
    ["job"],
    registry=REGISTRY,
)
JOB_LAST_RUN_DURATION_SECONDS = Gauge(
    "paios_job_last_run_duration_seconds",
    "Durée du dernier tour connu de cette tâche planifiée, en secondes.",
    ["job"],
    registry=REGISTRY,
)


def record_request(*, method: str, route: str | None, status: int, duration_seconds: float) -> None:
    # Une route non reconnue (404 avant résolution) n'a pas de gabarit :
    # regroupée à part pour ne jamais faire exploser le nombre de séries
    # avec un chemin brut (identifiants, codes d'étiquette).
    label_route = route or "unmatched"
    REQUEST_COUNT.labels(method=method, route=label_route, status=str(status)).inc()
    REQUEST_DURATION_SECONDS.labels(method=method, route=label_route).observe(duration_seconds)


def _update_job_gauges(connection: Connection) -> None:
    for run in latest_job_runs(connection):
        job = run["job_name"]
        JOB_LAST_RUN_TIMESTAMP_SECONDS.labels(job=job).set(run["finished_at"].timestamp())
        JOB_LAST_RUN_SUCCESS.labels(job=job).set(1 if run["succeeded"] else 0)
        JOB_LAST_RUN_DURATION_SECONDS.labels(job=job).set(
            (run["finished_at"] - run["started_at"]).total_seconds()
        )


def render_latest(connection: Connection) -> tuple[bytes, str]:
    _update_job_gauges(connection)
    return _generate_latest(REGISTRY), CONTENT_TYPE_LATEST
