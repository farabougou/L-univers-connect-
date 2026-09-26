"""Plans 2D (ADR 011, étape S3) : un fichier (PDF/PNG/JPEG) rattaché à un
espace, stocké comme les photos (ADR 006). Un nouveau plan crée toujours une
nouvelle version, jamais un écrasement — imposé en base par des
déclencheurs qui interdisent toute modification et suppression (voir la
migration f65006c6d8c7), pas seulement par convention applicative.

Le numéro de version est un fait décidé ici, jamais fourni par le client :
il est calculé dans la même transaction que l'insertion, protégé contre une
course par la contrainte d'unicité (tenant_id, space_id, version) — un
conflit possible mais rare (deux envois simultanés sur le même espace) est
alors renvoyé comme une erreur à réessayer, jamais une donnée à moitié
écrite.
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.errors import DomainError

_FLOOR_PLAN_COLUMNS = (
    "id, space_id, version, storage_key, content_type, filename, sha256, "
    "uploaded_by, uploaded_at"
)

SUPPORTED_CONTENT_TYPES = ("application/pdf", "image/png", "image/jpeg")


class FloorPlanConflict(DomainError, ValueError):
    status = 409


class FloorPlanInvalid(DomainError, ValueError):
    status = 422


def record_floor_plan(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    space_id: uuid.UUID,
    storage_key: str,
    content_type: str,
    filename: str,
    sha256: str,
    uploaded_by: str,
) -> uuid.UUID:
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise FloorPlanInvalid("FLOOR_PLAN_CONTENT_TYPE_UNSUPPORTED", content_type=content_type)

    floor_plan_id = uuid.uuid4()
    try:
        connection.execute(
            text(
                """
                INSERT INTO floor_plans
                    (id, tenant_id, space_id, version, storage_key, content_type,
                     filename, sha256, uploaded_by)
                VALUES (
                    :id, :tenant_id, :space_id,
                    COALESCE(
                        (SELECT MAX(version) FROM floor_plans WHERE space_id = :space_id), 0
                    ) + 1,
                    :storage_key, :content_type, :filename, :sha256, :uploaded_by
                )
                """
            ),
            {
                "id": floor_plan_id,
                "tenant_id": tenant_id,
                "space_id": space_id,
                "storage_key": storage_key,
                "content_type": content_type,
                "filename": filename,
                "sha256": sha256,
                "uploaded_by": uploaded_by,
            },
        )
    except IntegrityError as exc:
        raise FloorPlanConflict("FLOOR_PLAN_VERSION_CONFLICT") from exc
    return floor_plan_id


def get_floor_plan(connection: Connection, floor_plan_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_FLOOR_PLAN_COLUMNS} FROM floor_plans WHERE id = :id"),
            {"id": floor_plan_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_floor_plans(connection: Connection, space_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"SELECT {_FLOOR_PLAN_COLUMNS} FROM floor_plans "
            "WHERE space_id = :space_id ORDER BY version DESC"
        ),
        {"space_id": space_id},
    ).mappings()
    return [dict(row) for row in rows]
