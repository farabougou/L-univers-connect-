"""Registre d'identité commun et relations typées (ADR 012, étape F1).

Les nœuds sont créés par la base elle-même (déclencheurs) ; ce module ne fait
que les lire. Les relations transverses sont stockées ; les relations de
hiérarchie (site → espace ou position, espace → sous-espace, position →
sous-position, position → espace où elle se trouve) sont déduites des
colonnes existantes, jamais recopiées.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.graph_vocabulary import (
    EXTERNAL_ID_SCHEMES,
    PREDICATES,
    VOCABULARY_VERSION,
    VocabularyError,
    check_storable_relation,
)


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


# Arbres stricts exposés comme relations déduites : table → type de nœud.
# Pour les espaces, seuls les espaces ouverts apparaissent dans la structure
# courante (un espace clos reste consultable, mais n'a plus d'enfant actif).
_TREES = {
    "functional_location": ("functional_locations", ""),
    "space": ("spaces", " AND valid_to IS NULL"),
}


def _tree_edges(connection: Connection, node_id: uuid.UUID, node_type: str) -> list[dict]:
    """Parent (le site pour une racine, sinon le nœud parent) et enfants."""
    table, open_filter = _TREES[node_type]
    row = (
        connection.execute(
            text(f"SELECT site_id, parent_id FROM {table} WHERE id = :id"), {"id": node_id}
        )
        .mappings()
        .one()
    )
    if row["parent_id"] is None:
        parent_edge = _edge(
            node_id=node_id,
            subject_id=row["site_id"],
            subject_type="site",
            predicate="contains",
            object_id=node_id,
            object_type=node_type,
        )
    else:
        parent_edge = _edge(
            node_id=node_id,
            subject_id=row["parent_id"],
            subject_type=node_type,
            predicate="hasPart",
            object_id=node_id,
            object_type=node_type,
        )

    children = connection.execute(
        text(f"SELECT id FROM {table} WHERE parent_id = :id{open_filter} ORDER BY code"),
        {"id": node_id},
    ).scalars()
    return [parent_edge] + [
        _edge(
            node_id=node_id,
            subject_id=node_id,
            subject_type=node_type,
            predicate="hasPart",
            object_id=child_id,
            object_type=node_type,
        )
        for child_id in children
    ]


def _derived_edges(connection: Connection, node: dict[str, Any]) -> list[dict[str, Any]]:
    node_id = node["id"]
    node_type = node["node_type"]
    edges: list[dict[str, Any]] = []

    if node_type == "site":
        for child_type, (table, open_filter) in (
            ("space", _TREES["space"]),
            ("functional_location", _TREES["functional_location"]),
        ):
            roots = connection.execute(
                text(
                    f"SELECT id FROM {table} "
                    f"WHERE site_id = :id AND parent_id IS NULL{open_filter} ORDER BY code"
                ),
                {"id": node_id},
            ).scalars()
            edges.extend(
                _edge(
                    node_id=node_id,
                    subject_id=node_id,
                    subject_type="site",
                    predicate="contains",
                    object_id=root_id,
                    object_type=child_type,
                )
                for root_id in roots
            )

    elif node_type == "point":
        anchors = (
            connection.execute(
                text("SELECT functional_location_id, space_id FROM points WHERE id = :id"),
                {"id": node_id},
            )
            .mappings()
            .one()
        )
        for anchor_type, anchor_id in (
            ("functional_location", anchors["functional_location_id"]),
            ("space", anchors["space_id"]),
        ):
            if anchor_id is not None:
                edges.append(
                    _edge(
                        node_id=node_id,
                        subject_id=anchor_id,
                        subject_type=anchor_type,
                        predicate="hasPoint",
                        object_id=node_id,
                        object_type="point",
                    )
                )

    elif node_type == "space":
        edges.extend(_tree_edges(connection, node_id, "space"))
        located = connection.execute(
            text("SELECT id FROM functional_locations WHERE space_id = :id ORDER BY code"),
            {"id": node_id},
        ).scalars()
        edges.extend(
            _edge(
                node_id=node_id,
                subject_id=location_id,
                subject_type="functional_location",
                predicate="locatedIn",
                object_id=node_id,
                object_type="space",
            )
            for location_id in located
        )

    elif node_type == "functional_location":
        edges.extend(_tree_edges(connection, node_id, "functional_location"))
        space_id = connection.execute(
            text("SELECT space_id FROM functional_locations WHERE id = :id"), {"id": node_id}
        ).scalar()
        if space_id is not None:
            edges.append(
                _edge(
                    node_id=node_id,
                    subject_id=node_id,
                    subject_type="functional_location",
                    predicate="locatedIn",
                    object_id=space_id,
                    object_type="space",
                )
            )

    if node_type in ("space", "functional_location"):
        column = "space_id" if node_type == "space" else "functional_location_id"
        points = connection.execute(
            text(f"SELECT id FROM points WHERE {column} = :id ORDER BY code"), {"id": node_id}
        ).scalars()
        edges.extend(
            _edge(
                node_id=node_id,
                subject_id=node_id,
                subject_type=node_type,
                predicate="hasPoint",
                object_id=point_id,
                object_type="point",
            )
            for point_id in points
        )

    return edges


def add_external_identifier(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    node_id: uuid.UUID,
    scheme: str,
    external_id: str,
    created_by: str,
) -> uuid.UUID:
    """Relie un identifiant d'un autre système (code client, GlobalId IFC…)
    à un nœud existant. Un même identifiant ne désigne qu'un seul nœud."""
    if scheme not in EXTERNAL_ID_SCHEMES:
        raise VocabularyError(f"système d'identifiants inconnu : {scheme}")
    _require_node(connection, node_id)
    taken = connection.execute(
        text(
            "SELECT 1 FROM external_identifiers WHERE scheme = :scheme "
            "AND external_id = :external_id"
        ),
        {"scheme": scheme, "external_id": external_id},
    ).scalar()
    if taken:
        raise RelationConflict("cet identifiant externe est déjà utilisé")

    identifier_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO external_identifiers "
            "(id, tenant_id, node_id, scheme, external_id, created_by) "
            "VALUES (:id, :tenant_id, :node_id, :scheme, :external_id, :created_by)"
        ),
        {
            "id": identifier_id,
            "tenant_id": tenant_id,
            "node_id": node_id,
            "scheme": scheme,
            "external_id": external_id,
            "created_by": created_by,
        },
    )
    return identifier_id


def list_external_identifiers(connection: Connection, node_id: uuid.UUID) -> list[dict]:
    _require_node(connection, node_id)
    return [
        dict(row)
        for row in connection.execute(
            text(
                "SELECT id, node_id, scheme, external_id, created_by, created_at "
                "FROM external_identifiers WHERE node_id = :id ORDER BY scheme, external_id"
            ),
            {"id": node_id},
        ).mappings()
    ]


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
