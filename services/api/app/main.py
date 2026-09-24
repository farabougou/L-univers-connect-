from typing import Annotated, Any

from fastapi import Depends, FastAPI
from sqlalchemy import text

from app.auth import get_current_claims, require_role
from app.config import settings
from app.db import engine
from app.errors import ApiError, install_error_handlers
from app.observability import RequestLoggingMiddleware, configure_logging
from app.routers.analytics import router as analytics_router
from app.routers.assets import router as asset_registry_router
from app.routers.configs import router as configs_router
from app.routers.devices import router as devices_router
from app.routers.graph import router as graph_router
from app.routers.maintenance import router as maintenance_router
from app.routers.passport import router as passport_router
from app.routers.points import router as points_router
from app.routers.spatial import router as spatial_router
from app.routers.telemetry import router as telemetry_router

configure_logging(settings.log_level)

app = FastAPI(title="Physical Asset Intelligence OS API")
app.add_middleware(RequestLoggingMiddleware)
install_error_handlers(app)
app.include_router(asset_registry_router)
app.include_router(graph_router)
app.include_router(spatial_router)
app.include_router(points_router)
app.include_router(configs_router)
app.include_router(devices_router)
app.include_router(analytics_router)
app.include_router(passport_router)
app.include_router(maintenance_router)
app.include_router(telemetry_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise ApiError(503, "DATABASE_UNAVAILABLE") from exc

    return {"status": "ok"}


@app.get("/me")
def me(claims: Annotated[dict[str, Any], Depends(get_current_claims)]) -> dict[str, Any]:
    return {
        "sub": claims.get("sub"),
        "roles": claims.get("realm_access", {}).get("roles", []),
        "tenant_id": claims.get("tenant_id"),
    }


@app.get("/admin/ping")
def admin_ping(
    claims: Annotated[dict[str, Any], Depends(require_role("admin_tenant"))],
) -> dict[str, str]:
    return {"status": "ok"}
