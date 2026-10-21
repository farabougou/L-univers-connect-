"""Flux de changements incrémental du mobile (voir app/sync_feed.py).

Ajout pur : aucune route existante n'est modifiée (politique d'évolution
additive, docs/spec/api-stability-and-connector-sdk.md). Les charges sont
volontairement minimales (uniquement ce qu'affiche l'application) : sur une
connexion faible, chaque octet compte."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.engine import Connection

from app.auth import require_any_role
from app.deps import get_tenant_connection
from app.errors import api_error
from app.sync_feed import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    NIL_ID,
    Cursor,
    FeedCursorInvalid,
    database_now,
    decode_cursor,
    encode_cursor,
    fetch_page,
    next_cursor,
)

router = APIRouter()

_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")

AfterParam = Annotated[
    str | None,
    Query(description="Point de reprise remis par la page précédente. Absent : depuis le début."),
]
LimitParam = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
SinceParam = Annotated[
    datetime | None,
    Query(
        description=(
            "Premier parcours seulement (sans `after`) : ne livrer que les lignes créées "
            "à partir de cette date, avec fuseau horaire. Permet à un téléphone de ne "
            "charger qu'une fenêtre récente de l'historique."
        )
    ),
]


class InterventionFeedItem(BaseModel):
    id: uuid.UUID
    intervention_type: str
    started_at: datetime
    ended_at: datetime | None
    summary: str | None
    functional_location_id: uuid.UUID | None
    work_order_id: uuid.UUID | None


class LocationFeedItem(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    # Un équipement archivé est retiré de la liste locale, un équipement
    # désarchivé y revient : l'archivage est la seule « suppression » de la
    # plateforme (rien n'est effacé, voir règle non négociable 3).
    archived: bool


class InterventionFeedPage(BaseModel):
    items: list[InterventionFeedItem]
    next_cursor: str | None
    has_more: bool


class LocationFeedPage(BaseModel):
    items: list[LocationFeedItem]
    next_cursor: str | None
    has_more: bool


def _decode(after: str | None, since: datetime | None = None):
    """Point de départ du parcours : le curseur reçu ; à défaut, `since` ; à défaut,
    le début. `since` ne s'applique jamais à une reprise (un curseur fait foi)."""
    try:
        if after:
            return decode_cursor(after)
        if since is not None:
            if since.tzinfo is None:
                raise FeedCursorInvalid("SYNC_CURSOR_INVALID")
            return Cursor(at=since, id=NIL_ID)
        return None
    except FeedCursorInvalid as exc:
        raise api_error(exc, 400) from exc


@router.get("/sync/interventions", response_model=InterventionFeedPage)
def sync_interventions(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    after: AfterParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
    since: SinceParam = None,
) -> InterventionFeedPage:
    requested = _decode(after, since)
    rows, last, has_more = fetch_page(
        connection,
        table="interventions",
        columns=(
            "id, intervention_type, started_at, ended_at, summary, "
            "functional_location_id, work_order_id"
        ),
        date_column="created_at",
        after=requested,
        limit=limit,
    )
    cursor = next_cursor(
        requested=requested, last=last, has_more=has_more, now=database_now(connection)
    )
    return InterventionFeedPage(
        items=[InterventionFeedItem(**row) for row in rows],
        next_cursor=encode_cursor(cursor) if cursor else None,
        has_more=has_more,
    )


@router.get("/sync/functional-locations", response_model=LocationFeedPage)
def sync_functional_locations(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    after: AfterParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> LocationFeedPage:
    requested = _decode(after)
    rows, last, has_more = fetch_page(
        connection,
        table="functional_locations",
        columns="id, code, name, (archived_at IS NOT NULL) AS archived",
        date_column="updated_at",
        after=requested,
        limit=limit,
    )
    cursor = next_cursor(
        requested=requested, last=last, has_more=has_more, now=database_now(connection)
    )
    return LocationFeedPage(
        items=[LocationFeedItem(**row) for row in rows],
        next_cursor=encode_cursor(cursor) if cursor else None,
        has_more=has_more,
    )
