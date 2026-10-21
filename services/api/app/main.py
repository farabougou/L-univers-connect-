from typing import Annotated, Any

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.gzip import GZipMiddleware
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.admission import AdmissionControlMiddleware
from app.auth import get_current_claims, require_role
from app.config import settings
from app.db import engine
from app.deps import get_tenant_connection
from app.errors import ApiError, install_error_handlers
from app.metrics import render_latest
from app.observability import RequestLoggingMiddleware, configure_logging
from app.rate_limit import install_rate_limiting, limiter
from app.routers.analytics import router as analytics_router
from app.routers.assets import router as asset_registry_router
from app.routers.bacnet_discovery import router as bacnet_discovery_router
from app.routers.commands import router as commands_router
from app.routers.configs import router as configs_router
from app.routers.connectors import router as connectors_router
from app.routers.devices import router as devices_router
from app.routers.documents import router as documents_router
from app.routers.energy import router as energy_router
from app.routers.floor_plans import router as floor_plans_router
from app.routers.graph import router as graph_router
from app.routers.ifc_import import router as ifc_import_router
from app.routers.maintenance import router as maintenance_router
from app.routers.passport import router as passport_router
from app.routers.points import router as points_router
from app.routers.providers import router as providers_router
from app.routers.regulatory import router as regulatory_router
from app.routers.search import router as search_router
from app.routers.spatial import router as spatial_router
from app.routers.sync import router as sync_router
from app.routers.telemetry import router as telemetry_router

configure_logging(settings.log_level)

app = FastAPI(title="Enoryx API")
install_rate_limiting(app)
# Compression (consolidation V5 du 21/10/2026) : sur une connexion faible, un
# JSON de liste se compresse d'un facteur 5 à 10. Réponses de 1 Kio et plus
# seulement, et seulement si le client l'accepte (Accept-Encoding: gzip).
# Ajoutée EN PREMIER, donc la plus interne : elle voit la réponse complète de la
# route (seuil de taille respecté, longueur annoncée). Plus à l'extérieur, la
# journalisation (BaseHTTPMiddleware) transforme toute réponse en flux, et la
# compression s'appliquerait à des réponses de quelques octets.
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    AdmissionControlMiddleware,
    max_in_flight=settings.max_in_flight_requests
    or settings.db_pool_size + settings.db_max_overflow,
    queue_timeout_seconds=settings.admission_queue_timeout_seconds,
    exempt_paths=frozenset({"/health"}),
)
app.add_middleware(RequestLoggingMiddleware)
install_error_handlers(app)

# Pas de CORSMiddleware, volontairement : aucun composant client du web
# (apps/web, "use client") n'appelle cette API directement avec un jeton —
# tout passe par le serveur Next.js (architecture BFF, voir
# apps/web/src/lib/api.ts et proxy.ts) qui détient le cookie httpOnly.
# Avant d'ajouter CORS pour permettre un appel navigateur direct, vérifier
# que ce choix d'architecture a réellement changé (trouvé par l'audit
# sécurité du 02/10/2026 : l'absence de CORS n'était pas documentée comme un
# choix délibéré, risque qu'un futur appel direct ajoute un
# `allow_origins=["*"]` sans réfléchir à l'impact).
app.include_router(asset_registry_router)
app.include_router(bacnet_discovery_router)
app.include_router(graph_router)
app.include_router(spatial_router)
app.include_router(points_router)
app.include_router(configs_router)
app.include_router(connectors_router)
app.include_router(devices_router)
app.include_router(commands_router)
app.include_router(analytics_router)
app.include_router(passport_router)
app.include_router(maintenance_router)
app.include_router(telemetry_router)
app.include_router(energy_router)
app.include_router(floor_plans_router)
app.include_router(ifc_import_router)
app.include_router(documents_router)
app.include_router(providers_router)
app.include_router(regulatory_router)
app.include_router(search_router)
app.include_router(sync_router)


@app.get("/health")
@limiter.exempt
def health() -> dict[str, str]:
    """Sonde de la plateforme (Railway, supervision) : jamais limitée en débit.
    Sans cette exemption, un excès de trafic anonyme — qui partage le quota de
    l'adresse IP du proxy — ferait répondre 429 à la sonde, et la plateforme
    pourrait juger le service en panne et le redémarrer en plein incident
    (audit V5 du 20/10/2026). Aucun accès à la base : coût nul."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise ApiError(503, "DATABASE_UNAVAILABLE") from exc

    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    """Agrégats seulement (requêtes par méthode/route/statut, durée, dernier
    tour de chaque tâche planifiée) : aucune donnée métier ni par tenant —
    même niveau de sensibilité que /health, donc sans authentification
    (voir app/metrics.py). Connexion directe, sans contexte tenant : les
    tâches planifiées (app/job_runs.py) ne sont pas une donnée de tenant,
    même raisonnement que `tenants` elle-même."""
    with engine.connect() as connection:
        body, content_type = render_latest(connection)
    return Response(content=body, media_type=content_type)


@app.get("/me")
def me(
    claims: Annotated[dict[str, Any], Depends(get_current_claims)],
    connection: Annotated[Connection, Depends(get_tenant_connection)],
) -> dict[str, Any]:
    tenant_name = connection.execute(
        text("SELECT name FROM tenants WHERE id = :id"), {"id": claims.get("tenant_id")}
    ).scalar()
    return {
        "sub": claims.get("sub"),
        "roles": claims.get("realm_access", {}).get("roles", []),
        "tenant_id": claims.get("tenant_id"),
        # Nom lisible du client, jamais son identifiant technique affiché à
        # une personne (trouvé exposé en brut sur l'accueil mobile par
        # l'audit de bout en bout du 02/10/2026).
        "tenant_name": tenant_name,
    }


@app.get("/admin/ping")
def admin_ping(
    claims: Annotated[dict[str, Any], Depends(require_role("admin_tenant"))],
) -> dict[str, str]:
    return {"status": "ok"}
