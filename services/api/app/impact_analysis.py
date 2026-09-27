"""Analyse d'impact d'une panne (feature-benchmark-matrix.md, ligne « Graphe
de connaissances » : « permet l'analyse d'impact d'une panne » ; ligne
« Observabilité » : « distinguer équipement, capteur, passerelle, connecteur
et cloud en panne grâce aux relations connectedTo, pour éviter les
avalanches d'alarmes »).

Le prédicat « dependsOn » (app/graph_vocabulary.py) existe depuis F1 mais
n'était utilisé par aucun code : ce module comble cet écart. Pas de nouvelle
base ni de nouveau concept stocké : un parcours, au moment de la
consultation, des relations « dependsOn » déjà existantes — une vue pure,
comme la chronologie (app/timeline.py) ou le passeport (app/passport.py).

Principe : si un nœud A dépend d'un nœud B (A dependsOn B) et que B tombe en
panne, A est potentiellement impacté. Ce module répond à « qu'est-ce qui
dépend de ce nœud, et combien de ces éléments ont un constat ouvert en ce
moment ? » — jamais une affirmation de cause, seulement un regroupement à
vérifier par une personne (aucune corrélation n'est présentée comme
certaine).
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.findings import list_findings
from app.graph import NodeNotFound, get_node
from app.signal_vocabulary import HANDLING_OPEN


def find_dependents(connection: Connection, node_id: uuid.UUID) -> list[uuid.UUID]:
    """Tous les nœuds qui dépendent, directement ou transitivement, de
    `node_id` par des relations « dependsOn » actives (jamais rejetées ni
    closes). Parcours en largeur, nœud par nœud : à l'échelle d'un site ou
    d'un petit portefeuille, pas besoin d'une requête récursive."""
    visited: set[uuid.UUID] = set()
    frontier = [node_id]
    while frontier:
        next_frontier: list[uuid.UUID] = []
        for current in frontier:
            rows = connection.execute(
                text(
                    "SELECT subject_id FROM relations "
                    "WHERE object_id = :id AND predicate = 'dependsOn' "
                    "AND valid_to IS NULL AND status <> 'rejected'"
                ),
                {"id": current},
            ).scalars()
            for subject_id in rows:
                if subject_id not in visited:
                    visited.add(subject_id)
                    next_frontier.append(subject_id)
        frontier = next_frontier
    return list(visited)


def _open_finding_count(connection: Connection, node_id: uuid.UUID) -> int:
    return sum(
        1
        for finding in list_findings(connection, subject_node_id=node_id)
        if finding["handling_status"] in HANDLING_OPEN
    )


def impact_report(connection: Connection, node_id: uuid.UUID) -> dict[str, Any]:
    """Le nœud demandé, son nombre de constats ouverts, et pour chaque nœud
    qui en dépend, le sien. Un nombre élevé et partagé suggère une cause
    commune — à vérifier, jamais à affirmer automatiquement."""
    if get_node(connection, node_id) is None:
        raise NodeNotFound("NODE_NOT_FOUND")

    dependents = find_dependents(connection, node_id)
    impacted = []
    for dependent_id in dependents:
        node = get_node(connection, dependent_id)
        if node is None:
            continue
        impacted.append(
            {
                "node_id": dependent_id,
                "node_type": node["node_type"],
                "open_finding_count": _open_finding_count(connection, dependent_id),
            }
        )

    return {
        "node_id": node_id,
        "open_finding_count": _open_finding_count(connection, node_id),
        "impacted": impacted,
    }
