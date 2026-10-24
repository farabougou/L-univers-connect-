"""Comparaison d'équipements (07/10/2026, V3 — priorité « Compare » de la
feuille de route : Compare → Drift → Diagnose → Explain → Optimize).

Compare la dernière valeur d'un point à celle de ses pairs : les autres
points validés de la même `point_class` (même grandeur physique, même unité)
dans tout le portefeuille du client — entre équipements, entre sites, sans
distinction, puisque c'est justement ce qu'une comparaison de parc doit
pouvoir traverser. Jamais entre deux grandeurs différentes : comparer une
température de départ à une pression n'aurait aucun sens, même si les deux
appartiennent au même équipement.

Même calcul que `app.rules._evaluate_statistical_anomaly` (moyenne,
écart-type, z-score, confiance jamais à 1.0) — pas un deuxième moteur,
seulement une population différente : les pairs au même instant plutôt que
l'historique d'un seul point dans le temps. Différence déterminante : ceci
est une lecture pure, consultée à la demande, qui n'ouvre jamais de constat,
d'alarme ni d'ordre de travail — contrairement à `statistical_anomaly`, qui
reste la seule détection automatique. Comparer n'est pas détecter.

Jamais de performance, d'économie ou de causalité affirmée à partir de cet
écart (CLAUDE.md, section 7 ; ADR 013) : seulement une position statistique
observée dans le parc, avec sa confiance.
"""

import statistics
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.equipment_status import latest_usable_bulk
from app.points import PointInvalid, PointNotFound, get_point, list_points

# Sous ce nombre de pairs avec une valeur récente, une moyenne/écart-type
# resterait un artefact d'échantillon, jamais une population comparable.
MIN_PEERS_FOR_COMPARISON = 2
DEVIATION_THRESHOLD = 2.0


def _location_label(connection: Connection, point: dict[str, Any]) -> dict[str, Any] | None:
    """Site et équipement d'affichage d'un point, jamais devinés : `None`
    quand le point n'est rattaché à aucun équipement (ex. point d'espace)."""
    if point["functional_location_id"] is None:
        return None
    row = (
        connection.execute(
            text(
                "SELECT fl.code, fl.name, s.id AS site_id, s.name AS site_name "
                "FROM functional_locations fl JOIN sites s ON s.id = fl.site_id "
                "WHERE fl.id = :id"
            ),
            {"id": point["functional_location_id"]},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _entry(
    connection: Connection, point: dict[str, Any], latest: dict[str, Any] | None
) -> dict[str, Any]:
    location = _location_label(connection, point)
    return {
        "point_id": point["id"],
        "point_code": point["code"],
        "functional_location_code": location["code"] if location else None,
        "functional_location_name": location["name"] if location else None,
        "site_id": location["site_id"] if location else None,
        "site_name": location["site_name"] if location else None,
        "value": latest["value"] if latest else None,
        "measured_at": latest["measured_at"] if latest else None,
    }


def compare_point_to_peers(
    connection: Connection, point_id: uuid.UUID, at: datetime
) -> dict[str, Any]:
    """Position du point `point_id` par rapport à ses pairs de parc, au plus
    proche de l'instant `at`. Ne modifie rien : purement une lecture."""
    point = get_point(connection, point_id)
    if point is None:
        raise PointNotFound("POINT_NOT_FOUND")
    if point["value_type"] != "number":
        raise PointInvalid("POINT_COMPARISON_REQUIRES_NUMBER")

    peers = [
        candidate
        for candidate in list_points(
            connection, point_class=point["point_class"], mapping_status="validated"
        )
        if candidate["id"] != point["id"]
    ]
    latest = latest_usable_bulk(connection, [point["id"], *(p["id"] for p in peers)], at)

    self_latest = latest.get(point["id"])
    peer_entries = [
        _entry(connection, candidate, latest.get(candidate["id"])) for candidate in peers
    ]
    peer_values = [entry["value"] for entry in peer_entries if entry["value"] is not None]

    result: dict[str, Any] = {
        **_entry(connection, point, self_latest),
        "point_class": point["point_class"],
        "peer_count": len(peer_values),
        "peers": peer_entries,
        "comparable": False,
        "mean": None,
        "std_dev": None,
        "z_score": None,
        "deviation_threshold": DEVIATION_THRESHOLD,
        "is_outlier": False,
        "confidence": None,
    }
    if self_latest is None or len(peer_values) < MIN_PEERS_FOR_COMPARISON:
        return result

    mean = statistics.fmean(peer_values)
    std_dev = statistics.stdev(peer_values)
    result["comparable"] = True
    result["mean"] = round(mean, 4)
    result["std_dev"] = round(std_dev, 4)
    if std_dev == 0:
        # Tous les pairs partagent exactement la même valeur : aucune
        # variation pour estimer un écart, jamais une division par zéro
        # déguisée en conclusion.
        return result

    z_score = (self_latest["value"] - mean) / std_dev
    result["z_score"] = round(z_score, 2)
    result["is_outlier"] = abs(z_score) > DEVIATION_THRESHOLD
    if result["is_outlier"]:
        magnitude_factor = min(1.0, (abs(z_score) - DEVIATION_THRESHOLD) / DEVIATION_THRESHOLD)
        sample_factor = min(1.0, len(peer_values) / (MIN_PEERS_FOR_COMPARISON * 3))
        result["confidence"] = round(0.5 + 0.45 * magnitude_factor * sample_factor, 2)
    return result
