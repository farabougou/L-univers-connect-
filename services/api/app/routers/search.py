"""Recherche globale (ADR 014, Command Center) : voir app/search.py pour le
détail de ce qui est interrogé et pourquoi alarmes/constats/interventions
restent hors de cette première version."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from app.auth import require_any_role
from app.deps import get_tenant_connection
from app.schemas import SearchResultOut
from app.search import search

router = APIRouter()

_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


@router.get("/search", response_model=list[SearchResultOut])
def run_search(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    q: Annotated[str, Query(min_length=1, max_length=200)],
) -> list[SearchResultOut]:
    return [SearchResultOut(**result) for result in search(connection, query=q)]
