"""Journal des événements : faits horodatés, séparés de l'état courant et
des alertes (directive de Mohamed du 24/09/2026 — État ≠ Événement ≠ Alerte).

Un événement raconte ce qui s'est passé (« cet appareil est passé hors
ligne à 14h03 ») ; il ne signifie pas forcément qu'une alerte a été levée
(voir app/monitoring.py, qui décide de la politique). Séparé de
app/audit.py (actions humaines/appareil sensibles, chaîné par hachage) :
un événement est un constat du système, pas une action qu'on impute à
quelqu'un.

Append-only par construction : aucune fonction de modification ou de
suppression n'existe ici.
"""

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

_COLUMNS = "id, tenant_id, event_type, subject_type, subject_id, payload, occurred_at, created_at"

# Vocabulaire fermé des types d'événements (même principe que
# app/point_vocabulary.py) : un type d'événement de plus se décide ici,
# jamais en texte libre à l'appel — et ce n'est ni un code d'erreur ni un
# code de constat (voir tests/test_errors.py).
EVENT_TYPES = frozenset(
    {
        "DEVICE_WENT_OFFLINE",
        "DEVICE_CAME_ONLINE",
        "COMMAND_REQUESTED",
        "COMMAND_DISPATCHED",
        "COMMAND_VERIFIED",
        "COMMAND_FAILED",
        "COMMAND_TIMED_OUT",
    }
)


def record_event(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    event_type: str,
    subject_type: str,
    subject_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime,
) -> uuid.UUID:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Type d'événement inconnu : {event_type}")
    event_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO events (id, tenant_id, event_type, subject_type, subject_id, "
            "payload, occurred_at) VALUES (:id, :tenant_id, :event_type, :subject_type, "
            ":subject_id, CAST(:payload AS JSONB), :occurred_at)"
        ),
        {
            "id": event_id,
            "tenant_id": tenant_id,
            "event_type": event_type,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "payload": json.dumps(payload or {}, sort_keys=True, separators=(",", ":")),
            "occurred_at": occurred_at,
        },
    )
    return event_id


def list_events_for_subject(
    connection: Connection, *, subject_type: str, subject_id: uuid.UUID, limit: int = 50
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(
                f"SELECT {_COLUMNS} FROM events WHERE subject_type = :subject_type "
                "AND subject_id = :subject_id ORDER BY occurred_at DESC, created_at DESC "
                "LIMIT :limit"
            ),
            {"subject_type": subject_type, "subject_id": subject_id, "limit": limit},
        ).mappings()
    ]
