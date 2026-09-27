"""Métriques HTTP minimales, format Prometheus (feature-benchmark-matrix.md,
ligne « Observabilité (logs structurés, métriques, traces, fraîcheur) » :
les logs structurés existent depuis F6, les métriques et traces restaient
absentes).

Compte les requêtes par méthode/route/statut et leur durée, sans rien
ajouter au chemin d'une requête (le décompte se fait où le journal
« requête traitée » s'écrit déjà, app/observability.py). Jamais de donnée
métier ni par tenant ici : seulement des agrégats sur l'ensemble du
service, exposés sans authentification comme /health — même niveau de
sensibilité.

`prometheus_client` (Apache-2.0, projet de référence du format
d'exposition, aucune dépendance) : une bibliothèque de mise en forme, pas
un service — rien à héberger, rien à acheter pour que ce module ait de la
valeur dès aujourd'hui (une personne peut lire /metrics directement).
"""

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram
from prometheus_client import generate_latest as _generate_latest

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


def record_request(*, method: str, route: str | None, status: int, duration_seconds: float) -> None:
    # Une route non reconnue (404 avant résolution) n'a pas de gabarit :
    # regroupée à part pour ne jamais faire exploser le nombre de séries
    # avec un chemin brut (identifiants, codes d'étiquette).
    label_route = route or "unmatched"
    REQUEST_COUNT.labels(method=method, route=label_route, status=str(status)).inc()
    REQUEST_DURATION_SECONDS.labels(method=method, route=label_route).observe(duration_seconds)


def render_latest() -> tuple[bytes, str]:
    return _generate_latest(REGISTRY), CONTENT_TYPE_LATEST
