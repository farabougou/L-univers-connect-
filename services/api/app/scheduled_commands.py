"""Planification de commande (V2, 02/10/2026, priorité « planification » de
la feuille de route : ... Dry Run/Shadow → exécution simulée → vérification
→ audit → **planification** → automatisation).

Une commande planifiée est une déclaration : « exécuter cette valeur sur ce
point à cet instant futur ». Elle n'étend jamais la règle non négociable 1 :
la commandabilité du point et sa policy active (app.command_policies) sont
revérifiées à la planification ET au déclenchement — un point qui cesse
d'être commandable, ou une policy qui change entre les deux, bloque le
déclenchement (`status = 'failed'`), jamais un contournement par
anticipation. Rien n'est non plus exécuté avant l'heure : une commande
planifiée reste `pending` jusqu'à ce qu'un balayage périodique
(`app.scheduled_commands_sweep`, même mécanisme que `app.supervision_sweep`)
la trouve due.

Volontairement simple (règle des trois) : un instant unique, jamais une
récurrence (cron). Une récurrence réelle attendra un premier cas d'usage
concret plutôt que d'être devinée ici.

Déclenchée, une commande planifiée crée une commande ordinaire
(`app.commands.create_command`) : aucune deuxième logique d'exécution ni de
vérification — ce module ne fait qu'amener au bon moment un appel que
l'API humaine ferait, rien de plus. L'audit de cette création (acteur
`scheduler:{id de la planification}`, traçable jusqu'à la personne qui a
programmé l'envoi via `requested_by`) reste nécessaire : le déclenchement
n'a lieu dans aucune requête HTTP, donc aucun routeur ne l'auditerait à sa
place (voir app/routers/commands.py pour l'audit de la création immédiate
et de l'annulation, elles bien dans une requête humaine).
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.command_policies import PolicyViolation
from app.commands import CommandNotAllowed, create_command, validate_command
from app.errors import DomainError
from app.events import record_event

_COLUMNS = (
    "id, tenant_id, point_id, requested_value, scheduled_for, requested_by, requester_roles, "
    "status, command_id, failure_reason, created_at, dispatched_at, cancelled_at, cancelled_by"
)


class ScheduledCommandNotFound(DomainError, ValueError):
    status = 404


class ScheduledCommandConflict(DomainError, ValueError):
    status = 409


class ScheduledCommandInThePast(DomainError, ValueError):
    status = 422


def schedule_command(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    point_id: uuid.UUID,
    requested_value: float,
    scheduled_for: datetime,
    requested_by: str,
    requester_roles: list[str],
    at: datetime | None = None,
) -> uuid.UUID:
    """Planifie une commande. Échoue immédiatement si elle serait déjà
    refusée aujourd'hui (point non commandable, policy active violée) —
    jamais une planification qu'on sait d'avance vouée à l'échec — mais le
    déclenchement revérifiera quand même tout au bon moment, pour le cas où
    la situation change d'ici là."""
    at = at or datetime.now(UTC)
    if scheduled_for <= at:
        raise ScheduledCommandInThePast("SCHEDULED_COMMAND_IN_THE_PAST")
    validate_command(
        connection,
        point_id=point_id,
        requested_value=requested_value,
        requester_roles=requester_roles,
    )

    new_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO scheduled_commands "
            "(id, tenant_id, point_id, requested_value, scheduled_for, requested_by, "
            "requester_roles) "
            "VALUES (:id, :tenant_id, :point_id, :requested_value, :scheduled_for, "
            ":requested_by, CAST(:requester_roles AS JSONB))"
        ),
        {
            "id": new_id,
            "tenant_id": tenant_id,
            "point_id": point_id,
            "requested_value": requested_value,
            "scheduled_for": scheduled_for,
            "requested_by": requested_by,
            "requester_roles": json.dumps(requester_roles),
        },
    )
    record_event(
        connection,
        tenant_id=tenant_id,
        event_type="SCHEDULED_COMMAND_CREATED",
        subject_type="scheduled_command",
        subject_id=new_id,
        payload={
            "point_id": str(point_id),
            "requested_value": requested_value,
            "scheduled_for": scheduled_for.isoformat(),
        },
        occurred_at=at,
    )
    return new_id


def get_scheduled_command(
    connection: Connection, scheduled_command_id: uuid.UUID
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM scheduled_commands WHERE id = :id"),
            {"id": scheduled_command_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_scheduled_commands_for_point(
    connection: Connection, *, point_id: uuid.UUID, limit: int = 20
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(
                f"SELECT {_COLUMNS} FROM scheduled_commands WHERE point_id = :point_id "
                "ORDER BY scheduled_for DESC LIMIT :limit"
            ),
            {"point_id": point_id, "limit": limit},
        ).mappings()
    ]


def cancel_scheduled_command(
    connection: Connection,
    *,
    scheduled_command_id: uuid.UUID,
    cancelled_by: str,
    at: datetime,
) -> dict[str, Any]:
    scheduled = get_scheduled_command(connection, scheduled_command_id)
    if scheduled is None:
        raise ScheduledCommandNotFound(
            "SCHEDULED_COMMAND_NOT_FOUND", scheduled_command_id=str(scheduled_command_id)
        )
    if scheduled["status"] != "pending":
        raise ScheduledCommandConflict(
            "SCHEDULED_COMMAND_NOT_CANCELLABLE", status=scheduled["status"]
        )

    connection.execute(
        text(
            "UPDATE scheduled_commands SET status = 'cancelled', cancelled_at = :at, "
            "cancelled_by = :cancelled_by WHERE id = :id"
        ),
        {"at": at, "cancelled_by": cancelled_by, "id": scheduled_command_id},
    )
    updated = get_scheduled_command(connection, scheduled_command_id)
    record_event(
        connection,
        tenant_id=updated["tenant_id"],
        event_type="SCHEDULED_COMMAND_CANCELLED",
        subject_type="scheduled_command",
        subject_id=scheduled_command_id,
        occurred_at=at,
    )
    return updated


def dispatch_due_scheduled_commands(
    connection: Connection, *, tenant_id: uuid.UUID, at: datetime
) -> list[dict[str, Any]]:
    """Déclenche toutes les commandes planifiées dues (`scheduled_for <= at`,
    encore `pending`) pour ce tenant. Revérifie tout (commandabilité, policy)
    au moment du déclenchement, jamais seulement à la planification — une
    commande qui échoue maintenant devient `failed`, jamais silencieusement
    oubliée ni forcée malgré l'échec."""
    due = (
        connection.execute(
            text(
                f"SELECT {_COLUMNS} FROM scheduled_commands "
                "WHERE status = 'pending' AND scheduled_for <= :at"
            ),
            {"at": at},
        )
        .mappings()
        .all()
    )
    results = []
    for scheduled in due:
        try:
            command_id = create_command(
                connection,
                tenant_id=tenant_id,
                point_id=scheduled["point_id"],
                requested_value=scheduled["requested_value"],
                requested_by=scheduled["requested_by"],
                requester_roles=scheduled["requester_roles"],
                at=at,
            )
        except (CommandNotAllowed, PolicyViolation) as exc:
            connection.execute(
                text(
                    "UPDATE scheduled_commands SET status = 'failed', failure_reason = :reason "
                    "WHERE id = :id"
                ),
                {"reason": exc.code, "id": scheduled["id"]},
            )
            append_audit_entry(
                connection,
                tenant_id=tenant_id,
                actor=f"scheduler:{scheduled['id']}",
                action="scheduled_command.failed",
                entity_type="scheduled_command",
                entity_id=str(scheduled["id"]),
                payload={"reason": exc.code},
            )
            record_event(
                connection,
                tenant_id=tenant_id,
                event_type="SCHEDULED_COMMAND_FAILED",
                subject_type="scheduled_command",
                subject_id=scheduled["id"],
                payload={"reason": exc.code},
                occurred_at=at,
            )
            results.append(get_scheduled_command(connection, scheduled["id"]))
            continue

        connection.execute(
            text(
                "UPDATE scheduled_commands SET status = 'dispatched', command_id = :command_id, "
                "dispatched_at = :at WHERE id = :id"
            ),
            {"command_id": command_id, "at": at, "id": scheduled["id"]},
        )
        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor=f"scheduler:{scheduled['id']}",
            action="command.created",
            entity_type="command",
            entity_id=str(command_id),
            payload={
                "point_id": str(scheduled["point_id"]),
                "requested_value": scheduled["requested_value"],
                "scheduled_command_id": str(scheduled["id"]),
                "requested_by": scheduled["requested_by"],
            },
        )
        record_event(
            connection,
            tenant_id=tenant_id,
            event_type="SCHEDULED_COMMAND_DISPATCHED",
            subject_type="scheduled_command",
            subject_id=scheduled["id"],
            payload={"command_id": str(command_id)},
            occurred_at=at,
        )
        results.append(get_scheduled_command(connection, scheduled["id"]))
    return results
