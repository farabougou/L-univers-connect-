"""Politiques de supervision : État → Événement → Politique → Alerte si
nécessaire (directive de Mohamed du 24/09/2026 sur la gestion des états,
événements, alertes, incidents et commandes).

Pas de nouveau processus permanent pour la V1 (CLAUDE.md, règle de décision
correspondante — vérifier d'abord si les mécanismes actuels suffisent) :
ces fonctions s'appellent depuis les points de lecture dédiés qui calculent
déjà l'état concerné (GET /functional-locations/{id}/status, GET
/commands..., GET /points/{id}/trust), jamais depuis le passeport
(app/passport.py), qui reste une vue pure sans effet de bord par choix
architectural explicite. Un futur processus de tâches de fond pourra
appeler ces mêmes fonctions sur toute la flotte pour rendre la détection
proactive plutôt qu'à la prochaine lecture — sans rien changer ici (portée
à long terme, point 17 de la directive).

Le seuil « depuis combien de temps » est déjà intégré au calcul de l'état
lui-même (STALE_AFTER_INTERVALS pour la communication et pour la donnée
périmée, UNCONFIRMED_AFTER pour une commande) : la politique elle-même
reste donc volontairement simple pour la V1 — toute transition confirmée
déclenche une alerte de sévérité "warning", sans hiérarchie de criticité
par type d'actif (backlog, point 9 de la directive).

La déduplication (point 10) ne coûte rien de plus : une seule alerte
ouverte par clé, jamais dupliquée à chaque nouvelle lecture (voir
app/findings.py, raise_or_repeat_finding/clear_finding_by_key).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.commands import mark_command_timed_out
from app.events import record_event
from app.findings import clear_finding_by_key, raise_or_repeat_finding

SYSTEM_ACTOR = "systeme:supervision"


def evaluate_communication_status(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    functional_location_id: uuid.UUID,
    location_code: str,
    status: dict[str, Any],
    at: datetime,
) -> None:
    """À appeler chaque fois que le statut d'un équipement est calculé
    (compute_equipment_status) : transforme une transition de communication
    en événement persistant et, si nécessaire, en alerte. « unknown »
    (jamais de donnée, ou aucun point d'état configuré) ne déclenche rien :
    on ne sait pas encore si l'équipement est en ligne ou non."""
    dedup_key = f"communication_offline:{functional_location_id}"
    as_of = status["as_of"].isoformat() if status["as_of"] else None

    if status["communication_status"] == "offline":
        _, created = raise_or_repeat_finding(
            connection,
            tenant_id=tenant_id,
            dedup_key=dedup_key,
            subject_node_id=functional_location_id,
            kind="anomaly",
            method="deterministic_rule",
            severity="warning",
            reason_code="COMMUNICATION_OFFLINE",
            reason_params={"location_code": location_code},
            evidence={"as_of": as_of},
            seen_at=at,
            changed_by=SYSTEM_ACTOR,
        )
        if created:
            record_event(
                connection,
                tenant_id=tenant_id,
                event_type="DEVICE_WENT_OFFLINE",
                subject_type="functional_location",
                subject_id=functional_location_id,
                payload={"as_of": as_of},
                occurred_at=at,
            )
    elif status["communication_status"] == "online":
        cleared = clear_finding_by_key(
            connection, tenant_id=tenant_id, dedup_key=dedup_key, changed_by=SYSTEM_ACTOR
        )
        if cleared is not None:
            record_event(
                connection,
                tenant_id=tenant_id,
                event_type="DEVICE_CAME_ONLINE",
                subject_type="functional_location",
                subject_id=functional_location_id,
                payload={"as_of": as_of},
                occurred_at=at,
            )


def _point_subject(connection: Connection, point_id: uuid.UUID) -> uuid.UUID:
    """Le constat porte sur l'équipement du point, à défaut son espace —
    même règle que app/rules.py, `_subject`."""
    row = (
        connection.execute(
            text("SELECT functional_location_id, space_id FROM points WHERE id = :id"),
            {"id": point_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return point_id
    return row["functional_location_id"] or row["space_id"] or point_id


def evaluate_command_timeout(
    connection: Connection, *, tenant_id: uuid.UUID, command: dict[str, Any], at: datetime
) -> dict[str, Any]:
    """Transition sent → timed_out si le délai est dépassé (voir
    app/commands.py, `mark_command_timed_out`), avec l'alerte associée.
    Renvoie la commande, éventuellement mise à jour."""
    timed_out = mark_command_timed_out(connection, command_id=command["id"], at=at)
    if timed_out is None:
        return command

    point = (
        connection.execute(
            text("SELECT code FROM points WHERE id = :id"), {"id": timed_out["point_id"]}
        )
        .mappings()
        .first()
    )
    raise_or_repeat_finding(
        connection,
        tenant_id=tenant_id,
        dedup_key=f"command_timeout:{timed_out['id']}",
        subject_node_id=_point_subject(connection, timed_out["point_id"]),
        point_id=timed_out["point_id"],
        kind="anomaly",
        method="deterministic_rule",
        severity="warning",
        reason_code="COMMAND_UNCONFIRMED",
        reason_params={"point_code": point["code"] if point else str(timed_out["point_id"])},
        evidence={
            "command_id": str(timed_out["id"]),
            "requested_value": timed_out["requested_value"],
        },
        seen_at=at,
        changed_by=SYSTEM_ACTOR,
    )
    return timed_out


def evaluate_data_freshness(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    point: dict[str, Any],
    trust: dict[str, Any],
    at: datetime,
) -> None:
    """À appeler chaque fois que la confiance d'un point est calculée (voir
    app/trust.py, `compute_trust`, point de lecture GET /points/{id}/trust) :
    une donnée périmée (`components.stale`) devient un événement persistant
    et, si nécessaire, une alerte. `stale` vaut `None` sans intervalle
    attendu ou sans aucun relevé : on ne sait pas encore si la donnée est
    périmée, donc rien ne se déclenche (même principe que la communication
    « inconnue »)."""
    stale = trust["components"]["stale"]
    if stale is None:
        return

    dedup_key = f"data_stale:{point['id']}"
    last_measured_at = trust["components"]["last_measured_at"]

    if stale:
        _, created = raise_or_repeat_finding(
            connection,
            tenant_id=tenant_id,
            dedup_key=dedup_key,
            subject_node_id=_point_subject(connection, point["id"]),
            point_id=point["id"],
            kind="data_quality",
            method="deterministic_rule",
            severity="warning",
            reason_code="DATA_QUALITY_STALE",
            reason_params={"point_code": point["code"]},
            evidence={"last_measured_at": last_measured_at},
            seen_at=at,
            changed_by=SYSTEM_ACTOR,
        )
        if created:
            record_event(
                connection,
                tenant_id=tenant_id,
                event_type="DATA_BECAME_STALE",
                subject_type="point",
                subject_id=point["id"],
                payload={"last_measured_at": last_measured_at},
                occurred_at=at,
            )
    else:
        cleared = clear_finding_by_key(
            connection, tenant_id=tenant_id, dedup_key=dedup_key, changed_by=SYSTEM_ACTOR
        )
        if cleared is not None:
            record_event(
                connection,
                tenant_id=tenant_id,
                event_type="DATA_FRESHNESS_RESTORED",
                subject_type="point",
                subject_id=point["id"],
                payload={"last_measured_at": last_measured_at},
                occurred_at=at,
            )
