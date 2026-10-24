"""Score de confiance d'un point (ADR 012, section 2.8), version 1.

Déterministe et explicable : chaque composante est renvoyée avec le score,
pour qu'un humain comprenne pourquoi une donnée est jugée peu fiable. Les
moteurs (règles aujourd'hui, automatisation un jour) doivent consulter ce
score avant d'utiliser une donnée : une donnée douteuse n'est jamais
utilisée aveuglément (addendum V2, point 3).

Calcul sur la fenêtre précédant l'instant évalué (et jamais après) :
- point non validé → 0 (pas encore fiable par principe) ;
- capteur figé (12 dernières valeurs identiques) → −60 ;
- donnée périmée (dernier relevé plus vieux que 3 intervalles attendus) → −40 ;
- complétude sur 24 h (ou depuis le premier relevé si plus récent) ;
- part des 50 derniers relevés portant un drapeau de qualité.
"""

import math
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

TRUST_ALGORITHM = "trust-v1"
MIN_TRUST_FOR_RULES = 50
FROZEN_WINDOW = 12
FLAG_WINDOW = 50
COMPLETENESS_WINDOW = timedelta(hours=24)
STALE_AFTER_INTERVALS = 3


def compute_trust(connection: Connection, point: dict[str, Any], at: datetime) -> dict[str, Any]:
    recent = (
        connection.execute(
            text(
                "SELECT value, measured_at, cardinality(quality_flags) AS flag_count "
                "FROM measurements WHERE point_id = :point_id AND measured_at <= :at "
                "ORDER BY measured_at DESC LIMIT :limit"
            ),
            {"point_id": point["id"], "at": at, "limit": FLAG_WINDOW},
        )
        .mappings()
        .all()
    )
    components: dict[str, Any] = {
        "validated": point["mapping_status"] == "validated",
        "measurement_count": len(recent),
        "last_measured_at": recent[0]["measured_at"].isoformat() if recent else None,
        "frozen": False,
        "stale": None,
        "completeness": None,
        "flagged_ratio": None,
    }
    reasons: list[str] = []

    if recent:
        flagged = sum(1 for row in recent if row["flag_count"])
        components["flagged_ratio"] = round(flagged / len(recent), 3)
        last_values = [row["value"] for row in recent[:FROZEN_WINDOW]]
        components["frozen"] = (
            point["value_type"] == "number"
            and point["kind"] == "sensor"
            and len(last_values) == FROZEN_WINDOW
            and len(set(last_values)) == 1
        )

    interval = point["expected_interval_seconds"]
    if interval and recent:
        step = timedelta(seconds=interval)
        components["stale"] = at - recent[0]["measured_at"] > STALE_AFTER_INTERVALS * step
        first_measured_at = connection.execute(
            text("SELECT min(measured_at) FROM measurements WHERE point_id = :point_id"),
            {"point_id": point["id"]},
        ).scalar()
        window_start = max(at - COMPLETENESS_WINDOW, first_measured_at)
        expected = math.floor((at - window_start) / step) + 1
        received = connection.execute(
            text(
                "SELECT count(*) FROM measurements WHERE point_id = :point_id "
                "AND measured_at >= :start AND measured_at <= :at"
            ),
            {"point_id": point["id"], "start": window_start, "at": at},
        ).scalar()
        components["completeness"] = round(min(1.0, received / expected), 3)

    if not components["validated"]:
        score = 0.0
        reasons.append("point non validé (mise en service non terminée)")
    else:
        score = 100.0
        if components["frozen"]:
            score -= 60
            reasons.append(f"capteur figé ({FROZEN_WINDOW} valeurs identiques)")
        if components["stale"]:
            score -= 40
            reasons.append("donnée périmée")
        if components["completeness"] is not None:
            score *= 0.5 + 0.5 * components["completeness"]
            if components["completeness"] < 1:
                reasons.append(f"complétude {components['completeness']:.0%}")
        if components["flagged_ratio"]:
            score *= 1 - components["flagged_ratio"]
            reasons.append(f"{components['flagged_ratio']:.0%} de relevés douteux")

    return {
        "point_id": point["id"],
        "evaluated_at": at,
        "algorithm": TRUST_ALGORITHM,
        "score": max(0, min(100, round(score))),
        "components": components,
        "reasons": reasons,
    }
