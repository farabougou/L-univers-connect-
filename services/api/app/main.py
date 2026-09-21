from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text

from app.auth import get_current_claims, require_role
from app.db import engine

app = FastAPI(title="Physical Asset Intelligence OS API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc

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
