"""Pagination facultative des listes qui grossissent sans fin (audit V5 du
20/10/2026).

Mesuré sur une base de test : 4 000 lignes -> 0,1 à 0,2 s et 1,5 Mo ; 100 000
lignes -> 3 à 4 s et 35 Mo pour `/work-orders`, `/interventions`, `/alarms`.
Aucune de ces routes ne permettait de borner la réponse.

Volontairement **facultative** : sans `limit`, la réponse est exactement celle
d'avant (politique d'évolution additive, docs/spec/api-stability-and-connector-sdk.md).
Plafonner d'office aurait masqué sans prévenir des alarmes ou des ordres de
travail à un client qui en a beaucoup — pire qu'une réponse lente. Les écrans
actuels filtrent déjà côté serveur (`handling_status`) ; l'adoption de la
pagination par les écrans est une décision d'interface distincte.

`X-Total-Count` donne le nombre total de lignes correspondant aux filtres dès
que `limit` est fourni, pour que le client sache s'il lui en manque.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Query, Response

MAX_PAGE_SIZE = 1000
TOTAL_COUNT_HEADER = "X-Total-Count"


@dataclass(frozen=True)
class Page:
    limit: int | None = None
    offset: int = 0


def page_params(
    limit: Annotated[
        int | None,
        Query(
            ge=1,
            le=MAX_PAGE_SIZE,
            description="Nombre maximal de lignes. Absent : toutes les lignes.",
        ),
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Nombre de lignes à passer.")] = 0,
) -> Page:
    return Page(limit=limit, offset=offset)


def paginate(sql: str, params: dict[str, Any], page: Page) -> tuple[str, dict[str, Any]]:
    """Ajoute LIMIT/OFFSET à une requête dont l'ORDER BY est déjà déterministe
    (une clé unique en dernier critère)."""
    if page.limit is not None:
        sql += " LIMIT :page_limit"
        params = {**params, "page_limit": page.limit}
    if page.offset:
        sql += " OFFSET :page_offset"
        params = {**params, "page_offset": page.offset}
    return sql, params


def announce_total(response: Response, page: Page, count_rows: Callable[[], int]) -> None:
    """N'exécute le COUNT que si le client a demandé une page."""
    if page.limit is not None:
        response.headers[TOTAL_COUNT_HEADER] = str(count_rows())
