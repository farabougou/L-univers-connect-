"""Documents d'équipement (section 36, point 10 — directive UI/dashboard) :
manuels, certificats, garanties, fiches techniques, contrats, rapports de
conformité rattachés à une position fonctionnelle. Stockés comme les plans
2D (ADR 011) mais sans version partagée : chaque envoi est un document
indépendant, jamais un écrasement d'un précédent (règle non négociable 3).
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError

_DOCUMENT_COLUMNS = (
    "id, functional_location_id, category, storage_key, content_type, filename, "
    "sha256, uploaded_by, uploaded_at"
)

SUPPORTED_CONTENT_TYPES = ("application/pdf", "image/png", "image/jpeg")
CATEGORIES = (
    "manual",
    "certificate",
    "warranty",
    "datasheet",
    "compliance_report",
    "contract",
    "other",
)


class DocumentInvalid(DomainError, ValueError):
    status = 422


def record_document(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    functional_location_id: uuid.UUID,
    category: str,
    storage_key: str,
    content_type: str,
    filename: str,
    sha256: str,
    uploaded_by: str,
) -> uuid.UUID:
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise DocumentInvalid("DOCUMENT_CONTENT_TYPE_UNSUPPORTED", content_type=content_type)
    if category not in CATEGORIES:
        raise DocumentInvalid("DOCUMENT_CATEGORY_UNKNOWN", category=category)

    document_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO documents
                (id, tenant_id, functional_location_id, category, storage_key,
                 content_type, filename, sha256, uploaded_by)
            VALUES (
                :id, :tenant_id, :functional_location_id, :category, :storage_key,
                :content_type, :filename, :sha256, :uploaded_by
            )
            """
        ),
        {
            "id": document_id,
            "tenant_id": tenant_id,
            "functional_location_id": functional_location_id,
            "category": category,
            "storage_key": storage_key,
            "content_type": content_type,
            "filename": filename,
            "sha256": sha256,
            "uploaded_by": uploaded_by,
        },
    )
    return document_id


def get_document(connection: Connection, document_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE id = :id"),
            {"id": document_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_documents(
    connection: Connection, functional_location_id: uuid.UUID
) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"SELECT {_DOCUMENT_COLUMNS} FROM documents "
            "WHERE functional_location_id = :functional_location_id "
            "ORDER BY uploaded_at DESC"
        ),
        {"functional_location_id": functional_location_id},
    ).mappings()
    return [dict(row) for row in rows]


def list_portfolio_documents(connection: Connection) -> list[dict[str, Any]]:
    """Tous les documents du tenant, avec le nom et le code de l'équipement
    visé — pour l'écran Documents (bibliothèque de tout le portefeuille),
    sans jamais demander à la personne de connaître l'équipement d'avance."""
    rows = connection.execute(
        text(
            f"""
            SELECT {", ".join(f"d.{col}" for col in _DOCUMENT_COLUMNS.split(", "))},
                   fl.code AS functional_location_code,
                   fl.name AS functional_location_name
            FROM documents d
            JOIN functional_locations fl ON fl.id = d.functional_location_id
            ORDER BY d.uploaded_at DESC
            """
        )
    ).mappings()
    return [dict(row) for row in rows]
