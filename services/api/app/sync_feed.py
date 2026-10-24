"""Flux de changements incrémental pour les clients à connexion faible
(consolidation V5 du 21/10/2026).

Problème : l'application mobile téléchargeait TOUTES les interventions (35 Mo à
100 000 lignes) et tous les équipements à chaque synchronisation. Ici, le client
ne demande que ce qui a changé depuis son dernier point de reprise (`curseur`),
par pages de taille bornée, et peut s'interrompre à tout moment.

Garanties et limite, dans cet ordre :

1. Pas de doublon, pas de trou à l'intérieur d'un parcours. Le parcours suit
   l'ordre `(date, id)` : l'identifiant départage les lignes de même date (une
   transaction qui insère 500 lignes leur donne la même date), donc une page ne
   coupe jamais une égalité au hasard.

2. Reprise après interruption. Le curseur d'une page est celui de sa dernière
   ligne : un client qui a appliqué la page N repart exactement après elle. Le
   client enregistre le curseur dans la même transaction locale que les lignes
   de la page (voir apps/mobile/src/lib/syncFeed.ts).

3. Écritures tardives. Une ligne datée T peut devenir visible APRÈS qu'un client
   a déjà dépassé T (sa transaction s'est terminée plus tard que celles qui l'ont
   suivie). Pour ne jamais la perdre, le curseur remis en FIN de parcours est
   reculé de `OVERLAP` : le prochain parcours relit cette fenêtre. Les lignes
   relues sont reconnues par leur identifiant, donc sans doublon côté client
   (insertion ou mise à jour, jamais ajout).

   Limite assumée et testée : une transaction qui resterait ouverte plus de
   `OVERLAP` avant de se valider pourrait être manquée. Aucune requête de
   l'application ne dure ce temps (une création d'intervention est une seule
   requête de quelques millisecondes).

Les interventions ne sont jamais modifiées ni supprimées par l'application :
leur date de création suffit. Un équipement est archivé puis désarchivé : il
est donc livré de nouveau, avec `archived`, à chacune de ses modifications
(colonne `updated_at`, tenue par un déclencheur).
"""

import base64
import binascii
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError

OVERLAP = timedelta(minutes=5)
DEFAULT_LIMIT = 200
MAX_LIMIT = 500
NIL_ID = uuid.UUID(int=0)


class FeedCursorInvalid(DomainError, ValueError):
    pass


@dataclass(frozen=True, order=True)
class Cursor:
    at: datetime
    id: uuid.UUID


def encode_cursor(cursor: Cursor) -> str:
    raw = f"{cursor.at.astimezone(UTC).isoformat()}|{cursor.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str) -> Cursor:
    try:
        padded = value + "=" * (-len(value) % 4)
        at_text, id_text = base64.urlsafe_b64decode(padded.encode()).decode().split("|")
        at = datetime.fromisoformat(at_text)
        if at.tzinfo is None:
            raise ValueError("date sans fuseau")
        return Cursor(at=at, id=uuid.UUID(id_text))
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise FeedCursorInvalid("SYNC_CURSOR_INVALID") from exc


def next_cursor(
    *, requested: Cursor | None, last: Cursor | None, has_more: bool, now: datetime
) -> Cursor | None:
    """Curseur à remettre au client avec une page.

    Au milieu d'un parcours (`has_more`), on avance exactement jusqu'à la dernière
    ligne : le parcours doit progresser. En fin de parcours, on recule jusqu'à
    `now - OVERLAP` si la dernière ligne est plus récente (écritures tardives,
    point 3 de l'en-tête du module)."""
    position = last or requested
    if position is None or has_more:
        return position
    return min(position, Cursor(at=now - OVERLAP, id=NIL_ID))


def fetch_page(
    connection: Connection,
    *,
    table: str,
    columns: str,
    date_column: str,
    after: Cursor | None,
    limit: int,
) -> tuple[list[dict[str, Any]], Cursor | None, bool]:
    """Lit une page après `after`, dans l'ordre `(date, id)`. Les noms de table et
    de colonnes viennent du code, jamais d'une entrée externe. La sécurité par
    ligne limite la lecture au client authentifié. Demande `limit + 1` lignes pour
    savoir s'il en reste, sans second COUNT."""
    where = f"WHERE ({date_column}, id) > (:after_at, :after_id) " if after else ""
    rows = (
        connection.execute(
            text(
                f"SELECT {columns}, {date_column} AS _cursor_at FROM {table} "
                f"{where}ORDER BY {date_column}, id LIMIT :page_limit"
            ),
            {
                "page_limit": limit + 1,
                **({"after_at": after.at, "after_id": after.id} if after else {}),
            },
        )
        .mappings()
        .all()
    )
    has_more = len(rows) > limit
    page = [dict(row) for row in rows[:limit]]
    last = Cursor(at=page[-1]["_cursor_at"], id=page[-1]["id"]) if page else None
    return page, last, has_more


def database_now(connection: Connection) -> datetime:
    """Heure de la base, la même horloge que les dates des lignes (`created_at`,
    `updated_at`) : évite tout écart entre l'horloge du serveur d'application et
    celle de la base."""
    return connection.execute(text("SELECT clock_timestamp()")).scalar_one()
