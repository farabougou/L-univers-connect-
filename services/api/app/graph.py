"""Registre d'identité commun et relations typées (ADR 012, étape F1).

Les nœuds sont créés par la base elle-même (déclencheurs) ; ce module ne fait
que les lire. Les relations transverses sont stockées ; les relations de
hiérarchie (site → position, position → sous-position) sont déduites des
colonnes existantes, jamais recopiées.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.graph_vocabulary import PREDICATES, VOCABULARY_VERSION, check_storable_relation


class NodeNotFound(LookupError):
    pass


class RelationNotFound(LookupError):
    pass


class RelationConflict(ValueError):
    pass


def get_node(connection: Connection, node_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text("SELECT id, node_type, created_at FROM graph_nodes WHERE id = :id"),
            {"id": node_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _require_node(connection: Connection, node_id: uuid.UUID) -> dict[str, Any]:
    node = get_node(connection, node_id)
    if node is None:
        raise NodeNotFound(str(node_id))
    return node


def _open_relation_exists(
    connection: Connection, subject_id: uuid.UUID, predicate: str, object_id: uuid.UUID
) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT 1 FROM relations WHERE subject_id = :s AND predicate = :p "
                "AND object_id = :o AND valid_to IS NULL AND status <> 'rejected'"
            ),
            {"s": subject_id, "p": predicate, "o": object_id},
        ).scalar()
    )


def create_relation(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    subject_id: uuid.UUID,
    predicate: str,
    object_id: uuid.UUID,
    created_by: str,
    valid_from: datetime,
    confidence: float | None = None,
    origin: str = "manual",
    status: str = "validated",
) -> uuid.UUID:
    """Crée une relation après avoir vérifié les deux nœuds et le vocabulaire.

    Les nœuds sont lus sous RLS : un nœud d'un autre tenant est « introuvable ».
    La base refuserait de toute façon le lien (clés composées avec le tenant).
    """
    subject = _require_node(connection, subject_id)
    obj = _require_node(connection, object_id)
    definition = check_storable_relation(predicate, subject["node_type"], obj["node_type"])

    if _open_relation_exists(connection, subject_id, predicate, object_id):
        raise RelationConflict("cette relation existe déjà")
    symmetric = definition.inverse == definition.name
    if symmetric and _open_relation_exists(connection, object_id, predicate, subject_id):
        raise RelationConflict("cette relation existe déjà dans l'autre sens")

    relation_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO relations (id, tenant_id, subject_id, predicate, object_id, "
            "valid_from, origin, confidence, status, vocabulary_version, created_by) "
            "VALUES (:id, :tenant_id, :subject_id, :predicate, :object_id, "
            ":valid_from, :origin, :confidence, :status, :vocabulary_version, :created_by)"
        ),
        {
            "id": relation_id,
            "tenant_id": tenant_id,
            "subject_id": subject_id,
            "predicate": predicate,
            "object_id": object_id,
            "valid_from": valid_from,
            "origin": origin,
            "confidence": confidence,
            "status": status,
            "vocabulary_version": VOCABULARY_VERSION,
            "created_by": created_by,
        },
    )
    return relation_id


def end_relation(
    connection: Connection, *, relation_id: uuid.UUID, valid_to: datetime
) -> uuid.UUID:
    """Clôt une relation : elle reste dans l'historique, jamais effacée.

    Renvoie l'identifiant du sujet de la relation."""
    row = (
        connection.execute(
            text("SELECT subject_id, valid_from, valid_to FROM relations WHERE id = :id"),
            {"id": relation_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise RelationNotFound(str(relation_id))
    if row["valid_to"] is not None:
        raise RelationConflict("cette relation est déjà close")
    if valid_to <= row["valid_from"]:
        raise ValueError("la date de fin doit être postérieure au début de la relation")

    connection.execute(
        text("UPDATE relations SET valid_to = :valid_to WHERE id = :id"),
        {"valid_to": valid_to, "id": relation_id},
    )
    return row["subject_id"]


def _edge(
    *,
    node_id: uuid.UUID,
    subject_id: uuid.UUID,
    subject_type: str,
    predicate: str,
    object_id: uuid.UUID,
    object_type: str,
    **extra: Any,
) -> dict[str, Any]:
    outgoing = subject_id == node_id
    # Une relation ancienne peut porter un prédicat retiré depuis du
    # vocabulaire : on l'affiche tel quel plutôt que de la masquer.
    definition = PREDICATES.get(predicate)
    inverse = definition.inverse if definition else predicate
    edge = {
        "id": None,
        "subject_id": subject_id,
        "subject_type": subject_type,
        "predicate": predicate,
        "object_id": object_id,
        "object_type": object_type,
        "direction": "outgoing" if outgoing else "incoming",
        "label": predicate if outgoing else inverse,
        "derived": True,
        "valid_from": None,
        "valid_to": None,
        "origin": None,
        "status": None,
        "confidence": None,
        "vocabulary_version": None,
    }
    edge.update(extra)
    return edge


def _derived_edges(connection: Connection, node: dict[str, Any]) -> list[dict[str, Any]]:
    node_id = node["id"]
    edges: list[dict[str, Any]] = []

    if node["node_type"] == "site":
        top_level = connection.execute(
            text(
                "SELECT id FROM functional_locations "
                "WHERE site_id = :id AND parent_id IS NULL ORDER BY code"
            ),
            {"id": node_id},
        ).scalars()
        for location_id in top_level:
            edges.append(
                _edge(
                    node_id=node_id,
                    subject_id=node_id,
                    subject_type="site",
                    predicate="contains",
                    object_id=location_id,
                    object_type="functional_location",
                )
            )

    elif node["node_type"] == "functional_location":
        location = (
            connection.execute(
                text("SELECT site_id, parent_id FROM functional_locations WHERE id = :id"),
                {"id": node_id},
            )
            .mappings()
            .one()
        )
        if location["parent_id"] is None:
            edges.append(
                _edge(
                    node_id=node_id,
                    subject_id=location["site_id"],
                    subject_type="site",
                    predicate="contains",
                    object_id=node_id,
                    object_type="functional_location",
                )
            )
        else:
            edges.append(
                _edge(
                    node_id=node_id,
                    subject_id=location["parent_id"],
                    subject_type="functional_location",
                    predicate="hasPart",
                    object_id=node_id,
                    object_type="functional_location",
                )
            )
        children = connection.execute(
            text("SELECT id FROM functional_locations WHERE parent_id = :id ORDER BY code"),
            {"id": node_id},
        ).scalars()
        for child_id in children:
            edges.append(
                _edge(
                    node_id=node_id,
                    subject_id=node_id,
                    subject_type="functional_location",
                    predicate="hasPart",
                    object_id=child_id,
                    object_type="functional_location",
                )
            )

    return edges


def list_node_relations(
    connection: Connection, node_id: uuid.UUID, *, include_ended: bool = False
) -> list[dict[str, Any]]:
    """Relations d'un nœud dans les deux sens : stockées puis déduites.

    Par défaut, seules les relations en cours et non rejetées ; avec
    include_ended, tout l'historique (closes et rejetées comprises).
    """
    node = _require_node(connection, node_id)

    query = (
        "SELECT r.id, r.subject_id, s.node_type AS subject_type, r.predicate, "
        "r.object_id, o.node_type AS object_type, r.valid_from, r.valid_to, r.origin, "
        "r.status, r.confidence, r.vocabulary_version "
        "FROM relations r "
        "JOIN graph_nodes s ON s.id = r.subject_id "
        "JOIN graph_nodes o ON o.id = r.object_id "
        "WHERE (r.subject_id = :id OR r.object_id = :id)"
    )
    if not include_ended:
        query += " AND r.valid_to IS NULL AND r.status <> 'rejected'"
    query += " ORDER BY r.valid_from, r.recorded_at"

    stored = []
    for row in connection.execute(text(query), {"id": node_id}).mappings():
        row = dict(row)
        edge = _edge(
            node_id=node_id,
            subject_id=row.pop("subject_id"),
            subject_type=row.pop("subject_type"),
            predicate=row.pop("predicate"),
            object_id=row.pop("object_id"),
            object_type=row.pop("object_type"),
            derived=False,
            **row,
        )
        stored.append(edge)

    return stored + _derived_edges(connection, node)
