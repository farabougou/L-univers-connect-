"""Vue d'ensemble télémétrie pour tout le portefeuille (directive UI/
dashboard, section 36 point 9 — page Telemetry) : la dernière valeur de
chaque point validé du tenant, en une poignée de requêtes plutôt qu'une par
point (même principe que
`app/equipment_status.py::compute_portfolio_equipment_status`, directive
section 29).

Lecture pure, jamais le calcul de confiance complet
(`app/trust.py::compute_trust`, plusieurs requêtes par point à lui seul) :
seulement la fraîcheur simple déjà utilisée pour le statut d'un équipement
(dernier relevé plus vieux que `STALE_AFTER_INTERVALS` intervalles
attendus). Le score de confiance détaillé reste la responsabilité de
`GET /points/{id}/trust`, pour un seul point à la fois — jamais reconstruit
ici pour tout le portefeuille, ce qui réintroduirait le problème d'échelle
que ce module évite justement.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.engine import Connection

from app.equipment_status import latest_usable_bulk
from app.points import list_points

STALE_AFTER_INTERVALS = 3


def portfolio_telemetry(connection: Connection, *, at: datetime) -> list[dict[str, Any]]:
    """Un point sans relevé exploitable est rapporté avec `value`/
    `measured_at`/`stale` à `None` — jamais omis : l'absence de donnée fait
    partie de la vérité du portefeuille (même principe que le bloc « Santé
    des actifs » pour un équipement sans point d'état)."""
    points = list_points(connection, mapping_status="validated")
    latest_by_point = latest_usable_bulk(connection, [point["id"] for point in points], at)

    entries: list[dict[str, Any]] = []
    for point in points:
        latest = latest_by_point.get(point["id"])
        entry: dict[str, Any] = {
            "point_id": point["id"],
            "functional_location_id": point["functional_location_id"],
            "code": point["code"],
            "name": point["name"],
            "point_class": point["point_class"],
            "unit": point["unit"],
            "value": latest["value"] if latest else None,
            "measured_at": latest["measured_at"] if latest else None,
            "stale": None,
        }
        interval = point["expected_interval_seconds"]
        if latest and interval:
            limit = STALE_AFTER_INTERVALS * timedelta(seconds=interval)
            entry["stale"] = (at - latest["measured_at"]) > limit
        entries.append(entry)
    return entries
