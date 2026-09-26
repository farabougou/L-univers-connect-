"""Import BIM/IFC vers le registre (ADR 011, section 2 « BIM / IFC »).

Ne dépend jamais d'ifcopenshell : seulement des structures simples renvoyées
par app.importers.ifc_parser (SpaceProposal, EquipmentProposal), déjà
dépouillées de tout ce qui est propre à la bibliothèque. Un changement de
parseur, y compris pour une version majeure incompatible, ne touche jamais
ce module.

Toute donnée importée reste une proposition tant qu'une personne ne l'a pas
acceptée (ADR 011, point 9 : « toute détection automatique doit rester
vérifiable/corrigeable »). Accepter une proposition passe par les mêmes
fonctions de création que la saisie manuelle (app.spatial.create_space,
app.assets.create_functional_location) : un seul chemin de création, jamais
un second modèle d'actifs pour l'import.

La hiérarchie s'accepte du haut vers le bas (bâtiment, puis étage, puis
pièce, puis équipement) : une proposition dont le parent IFC n'est pas
encore une position/un espace réel du registre est refusée, jamais
approximée.
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.assets import create_functional_location
from app.errors import DomainError
from app.importers.ifc_parser import IfcParseResult
from app.spatial import create_space

_BATCH_COLUMNS = (
    "id, site_id, storage_key, filename, sha256, status, error_code, ifc_schema, "
    "space_proposal_count, equipment_proposal_count, skipped_element_count, "
    "uploaded_by, uploaded_at"
)
_PROPOSAL_COLUMNS = (
    "id, batch_id, proposal_type, ifc_class, ifc_global_id, name, space_type, "
    "parent_ifc_global_id, containing_space_ifc_global_id, status, created_node_id, "
    "decided_by, decided_at, rejection_reason, created_at"
)

class ImportBatchNotFound(DomainError, LookupError):
    status = 404


class ImportProposalNotFound(DomainError, LookupError):
    status = 404


class ImportProposalConflict(DomainError, ValueError):
    status = 409


class ImportProposalInvalid(DomainError, ValueError):
    status = 422


def _slug(text_value: str, *, suffix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text_value.lower()).strip("-") or "element"
    return f"{slug[:60]}-{suffix.lower()}"


def create_batch(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    storage_key: str,
    filename: str,
    sha256: str,
    uploaded_by: str,
) -> uuid.UUID:
    batch_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO ifc_import_batches "
            "(id, tenant_id, site_id, storage_key, filename, sha256, uploaded_by) "
            "VALUES (:id, :tenant_id, :site_id, :storage_key, :filename, :sha256, :uploaded_by)"
        ),
        {
            "id": batch_id,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "storage_key": storage_key,
            "filename": filename,
            "sha256": sha256,
            "uploaded_by": uploaded_by,
        },
    )
    return batch_id


def mark_batch_failed(connection: Connection, *, batch_id: uuid.UUID, error_code: str) -> None:
    connection.execute(
        text(
            "UPDATE ifc_import_batches SET status = 'failed', error_code = :error_code "
            "WHERE id = :id"
        ),
        {"error_code": error_code, "id": batch_id},
    )


def store_parse_result(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    result: IfcParseResult,
) -> None:
    """Enregistre chaque candidat comme une proposition distincte et
    referme le lot. Les espaces d'abord (les équipements s'y rattachent)."""
    for space in result.spaces:
        connection.execute(
            text(
                "INSERT INTO ifc_import_proposals "
                "(id, tenant_id, batch_id, proposal_type, ifc_class, ifc_global_id, name, "
                "space_type, parent_ifc_global_id) VALUES "
                "(:id, :tenant_id, :batch_id, 'space', :ifc_class, :ifc_global_id, :name, "
                ":space_type, :parent_ifc_global_id)"
            ),
            {
                "id": uuid.uuid4(),
                "tenant_id": tenant_id,
                "batch_id": batch_id,
                "ifc_class": space.ifc_class,
                "ifc_global_id": space.ifc_global_id,
                "name": space.name,
                "space_type": space.space_type,
                "parent_ifc_global_id": space.parent_ifc_global_id,
            },
        )
    for equipment in result.equipment:
        connection.execute(
            text(
                "INSERT INTO ifc_import_proposals "
                "(id, tenant_id, batch_id, proposal_type, ifc_class, ifc_global_id, name, "
                "containing_space_ifc_global_id) VALUES "
                "(:id, :tenant_id, :batch_id, 'equipment', :ifc_class, :ifc_global_id, :name, "
                ":containing_space_ifc_global_id)"
            ),
            {
                "id": uuid.uuid4(),
                "tenant_id": tenant_id,
                "batch_id": batch_id,
                "ifc_class": equipment.ifc_class,
                "ifc_global_id": equipment.ifc_global_id,
                "name": equipment.name,
                "containing_space_ifc_global_id": equipment.containing_space_ifc_global_id,
            },
        )
    connection.execute(
        text(
            "UPDATE ifc_import_batches SET status = 'ready', ifc_schema = :schema, "
            "space_proposal_count = :space_count, equipment_proposal_count = :equipment_count, "
            "skipped_element_count = :skipped WHERE id = :id"
        ),
        {
            "schema": result.schema,
            "space_count": len(result.spaces),
            "equipment_count": len(result.equipment),
            "skipped": result.skipped_element_count,
            "id": batch_id,
        },
    )


def get_batch(connection: Connection, batch_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_BATCH_COLUMNS} FROM ifc_import_batches WHERE id = :id"),
            {"id": batch_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_batches(connection: Connection, *, site_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"SELECT {_BATCH_COLUMNS} FROM ifc_import_batches "
            "WHERE site_id = :site_id ORDER BY uploaded_at DESC"
        ),
        {"site_id": site_id},
    ).mappings()
    return [dict(row) for row in rows]


def get_proposal(connection: Connection, proposal_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_PROPOSAL_COLUMNS} FROM ifc_import_proposals WHERE id = :id"),
            {"id": proposal_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_proposals(
    connection: Connection,
    *,
    batch_id: uuid.UUID,
    proposal_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    query = f"SELECT {_PROPOSAL_COLUMNS} FROM ifc_import_proposals WHERE batch_id = :batch_id"
    params: dict[str, Any] = {"batch_id": batch_id}
    if proposal_type is not None:
        query += " AND proposal_type = :proposal_type"
        params["proposal_type"] = proposal_type
    if status is not None:
        query += " AND status = :status"
        params["status"] = status
    query += (
        " ORDER BY (CASE WHEN proposal_type = 'space' THEN 0 ELSE 1 END), created_at"
    )
    rows = connection.execute(text(query), params).mappings()
    return [dict(row) for row in rows]


def _resolve_node_by_global_id(
    connection: Connection, *, batch_id: uuid.UUID, ifc_global_id: str | None
) -> uuid.UUID | None:
    if ifc_global_id is None:
        return None
    return connection.execute(
        text(
            "SELECT created_node_id FROM ifc_import_proposals "
            "WHERE batch_id = :batch_id AND ifc_global_id = :ifc_global_id "
            "AND status = 'accepted'"
        ),
        {"batch_id": batch_id, "ifc_global_id": ifc_global_id},
    ).scalar()


def accept_proposal(
    connection: Connection, *, tenant_id: uuid.UUID, proposal_id: uuid.UUID, decided_by: str
) -> dict[str, Any]:
    proposal = get_proposal(connection, proposal_id)
    if proposal is None:
        raise ImportProposalNotFound("IFC_IMPORT_PROPOSAL_NOT_FOUND")
    if proposal["status"] != "proposed":
        raise ImportProposalConflict("IFC_IMPORT_PROPOSAL_ALREADY_DECIDED")
    batch = get_batch(connection, proposal["batch_id"])

    if proposal["proposal_type"] == "space":
        node_id = _accept_space(connection, tenant_id=tenant_id, batch=batch, proposal=proposal)
    else:
        node_id = _accept_equipment(
            connection, tenant_id=tenant_id, batch=batch, proposal=proposal
        )

    connection.execute(
        text(
            "UPDATE ifc_import_proposals SET status = 'accepted', created_node_id = :node_id, "
            "decided_by = :decided_by, decided_at = :decided_at WHERE id = :id"
        ),
        {
            "node_id": node_id,
            "decided_by": decided_by,
            "decided_at": datetime.now(UTC),
            "id": proposal_id,
        },
    )
    return get_proposal(connection, proposal_id)


def _accept_space(
    connection: Connection, *, tenant_id: uuid.UUID, batch: dict, proposal: dict
) -> uuid.UUID:
    parent_id = None
    if proposal["space_type"] != "building":
        # Un bâtiment est toujours directement sous le site dans notre
        # modèle (SPACE_TYPES) : son parent IFC (le site) ne se traduit
        # jamais en espace, contrairement à l'étage ou la pièce.
        parent_id = _resolve_node_by_global_id(
            connection, batch_id=batch["id"], ifc_global_id=proposal["parent_ifc_global_id"]
        )
        if parent_id is None:
            raise ImportProposalInvalid("IFC_IMPORT_PARENT_NOT_ACCEPTED")

    # SpatialNotFound/SpatialConflict remontent telles quelles : le routeur
    # les traduit avec le même statut que la création manuelle d'un espace.
    return create_space(
        connection,
        tenant_id=tenant_id,
        site_id=batch["site_id"],
        parent_id=parent_id,
        space_type=proposal["space_type"],
        code=_slug(proposal["name"], suffix=proposal["ifc_global_id"][:6]),
        name=proposal["name"],
        valid_from=datetime.now(UTC),
    )


def _accept_equipment(
    connection: Connection, *, tenant_id: uuid.UUID, batch: dict, proposal: dict
) -> uuid.UUID:
    space_id = _resolve_node_by_global_id(
        connection,
        batch_id=batch["id"],
        ifc_global_id=proposal["containing_space_ifc_global_id"],
    )
    return create_functional_location(
        connection,
        tenant_id=tenant_id,
        site_id=batch["site_id"],
        parent_id=None,
        code=_slug(proposal["name"], suffix=proposal["ifc_global_id"][:6]),
        name=proposal["name"],
        kind="equipment",
        space_id=space_id,
        created_by="import:ifc",
    )


def reject_proposal(
    connection: Connection, *, proposal_id: uuid.UUID, decided_by: str, reason: str
) -> dict[str, Any]:
    proposal = get_proposal(connection, proposal_id)
    if proposal is None:
        raise ImportProposalNotFound("IFC_IMPORT_PROPOSAL_NOT_FOUND")
    if proposal["status"] != "proposed":
        raise ImportProposalConflict("IFC_IMPORT_PROPOSAL_ALREADY_DECIDED")

    connection.execute(
        text(
            "UPDATE ifc_import_proposals SET status = 'rejected', decided_by = :decided_by, "
            "decided_at = :decided_at, rejection_reason = :reason WHERE id = :id"
        ),
        {
            "decided_by": decided_by,
            "decided_at": datetime.now(UTC),
            "reason": reason,
            "id": proposal_id,
        },
    )
    return get_proposal(connection, proposal_id)
