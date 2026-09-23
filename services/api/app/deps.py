import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.engine import Connection

from app.auth import get_current_claims
from app.db import engine
from app.errors import ApiError
from app.observability import set_tenant
from app.tenancy import set_tenant_context


def get_connection() -> Iterator[Connection]:
    """Une connexion par requête, dans une transaction validée en fin de route."""
    with engine.begin() as connection:
        yield connection


def get_tenant_id(claims: Annotated[dict, Depends(get_current_claims)]) -> uuid.UUID:
    raw_tenant_id = claims.get("tenant_id")
    if not raw_tenant_id:
        raise ApiError(400, "TOKEN_TENANT_MISSING")
    try:
        tenant_id = uuid.UUID(str(raw_tenant_id))
    except ValueError as exc:
        raise ApiError(400, "TOKEN_TENANT_INVALID") from exc
    set_tenant(tenant_id)
    return tenant_id


def get_tenant_connection(
    connection: Annotated[Connection, Depends(get_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
) -> Connection:
    """Connexion déjà positionnée sur le tenant du jeton (voir app.tenancy).

    Toute route qui dépend de cette fonction ne peut, par construction,
    lire ou écrire que les données du tenant de l'utilisateur connecté.
    """
    set_tenant_context(connection, tenant_id)
    return connection
