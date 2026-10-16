"""Recherche globale en lecture seule (ADR 014, Command Center ; feature-
benchmark-matrix.md, ligne « Recherche globale »). Interroge dans la même
requête ce qui existe déjà séparément — sites, espaces, équipements,
identifiants/QR, ordres de travail — jamais une nouvelle source de vérité,
un agrégat de lecture au moment de la requête.

Filtrage par tenant (RLS déjà forcée sur chaque table) et par motif texte
entièrement côté serveur : jamais une liste complète renvoyée puis filtrée
dans le navigateur (ADR 014 §5).

Alarmes, constats et interventions restent hors de cette première version :
leur texte affiché est produit à l'affichage depuis un code et des
paramètres (ADR 013), jamais stocké comme une phrase — il n'y a donc rien à
chercher par motif texte côté base sans reconstruire la traduction pour
chaque langue à chaque recherche. Une recherche par code (ex. reason_code)
reste possible dans un incrément séparé, sans toucher à cette fonction.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

_RESULT_LIMIT_PER_KIND = 10


def search(connection: Connection, *, query: str) -> list[dict[str, Any]]:
    """Résultats triés par catégorie puis par nom, au plus
    `_RESULT_LIMIT_PER_KIND` par catégorie — une recherche n'est jamais une
    exportation complète."""
    term = query.strip()
    if not term:
        return []
    pattern = f"%{term}%"
    results: list[dict[str, Any]] = []

    results += [
        {"kind": "site", "id": str(row.id), "label": row.name}
        for row in connection.execute(
            text(
                "SELECT id, name FROM sites WHERE archived_at IS NULL AND name ILIKE :pattern "
                "ORDER BY name LIMIT :limit"
            ),
            {"pattern": pattern, "limit": _RESULT_LIMIT_PER_KIND},
        )
    ]
    results += [
        {"kind": "space", "id": str(row.id), "label": f"{row.code} — {row.name}"}
        for row in connection.execute(
            text(
                "SELECT id, code, name FROM spaces WHERE valid_to IS NULL "
                "AND (code ILIKE :pattern OR name ILIKE :pattern) ORDER BY code LIMIT :limit"
            ),
            {"pattern": pattern, "limit": _RESULT_LIMIT_PER_KIND},
        )
    ]
    results += [
        {"kind": "functional_location", "id": str(row.id), "label": f"{row.code} — {row.name}"}
        for row in connection.execute(
            text(
                "SELECT id, code, name FROM functional_locations WHERE archived_at IS NULL "
                "AND (code ILIKE :pattern OR name ILIKE :pattern) ORDER BY code LIMIT :limit"
            ),
            {"pattern": pattern, "limit": _RESULT_LIMIT_PER_KIND},
        )
    ]
    results += [
        {"kind": "tag", "id": str(row.node_id), "label": row.code}
        for row in connection.execute(
            text(
                "SELECT node_id, code FROM asset_tags WHERE status = 'active' "
                "AND code ILIKE :pattern ORDER BY code LIMIT :limit"
            ),
            {"pattern": pattern, "limit": _RESULT_LIMIT_PER_KIND},
        )
    ]
    results += [
        {"kind": "work_order", "id": str(row.id), "label": row.title}
        for row in connection.execute(
            text(
                "SELECT id, title FROM work_orders WHERE title ILIKE :pattern "
                "ORDER BY created_at DESC LIMIT :limit"
            ),
            {"pattern": pattern, "limit": _RESULT_LIMIT_PER_KIND},
        )
    ]
    return results
