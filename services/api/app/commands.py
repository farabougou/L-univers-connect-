"""Pipeline de commande — exception strictement limitée à un appareil
explicitement simulé (CLAUDE.md, exception à la règle non négociable 1,
décision de Mohamed du 24/09/2026).

Une commande n'est acceptée que si le point ciblé est actuellement servi
par une configuration Modbus active dont le device_type figure dans
`SIMULATED_DEVICE_TYPES` (app/connectors/device_mapping.py) — jamais le
sdm120, jamais un futur type représentant un vrai appareil. C'est la seule
porte d'entrée : aucune autre fonction de ce fichier n'écrit vers un
équipement, cette écriture elle-même n'a lieu que dans
app/connectors/simulated_actuator.py, appelée par l'Edge après avoir
récupéré une commande via GET /edge/commands.

Le point lui-même reste un point ordinaire, en lecture (`is_writable` vaut
toujours false, `ck_points_read_only_c0`) : la valeur demandée par la
commande vit dans cette table, la valeur réelle s'observe via la
télémétrie déjà existante (measurements), jamais un point rendu
inscriptible.

À ne pas confondre avec app/desired_states.py (« état souhaité ») : ce
module-là est une attente déclarative pour détecter une dérive ou un
gaspillage, toujours en lecture seule, sans lien avec une commande précise
envoyée à un instant donné. Les deux notions sont volontairement séparées.

Statuts :
- pending : créée, pas encore récupérée par l'Edge.
- sent : récupérée par l'Edge, exécution en cours.
- acknowledged : l'Edge a confirmé l'écriture, sans qu'elle corresponde
  forcément à la valeur demandée (voir `acknowledge_command`).
- verified : la valeur relue par l'Edge après écriture correspond à la
  valeur demandée.
- failed : écriture refusée par l'appareil simulé, ou valeur relue
  différente de la valeur demandée.
- unconfirmed (calculé à la lecture, jamais stocké — même principe que
  app/devices.py, `communication_status`) : envoyée à l'Edge depuis plus de
  `UNCONFIRMED_AFTER` sans accusé de réception.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.connectors.device_mapping import SIMULATED_DEVICE_TYPES, get_active_mapping
from app.errors import DomainError

_COLUMNS = (
    "id, tenant_id, point_id, requested_value, requested_by, status, actual_value, "
    "failure_reason, created_at, sent_at, acknowledged_at, verified_at, edge_device_id"
)

# Au-delà de ce délai sans accusé de réception, une commande envoyée est
# considérée non confirmée plutôt que silencieusement "en cours" pour
# toujours : l'Edge a pu ne jamais la recevoir.
UNCONFIRMED_AFTER = timedelta(minutes=5)


class CommandNotAllowed(DomainError, ValueError):
    status = 422


class CommandNotFound(DomainError, ValueError):
    status = 404


class CommandConflict(DomainError, ValueError):
    status = 409


def _point_functional_location(connection: Connection, point_id: uuid.UUID) -> uuid.UUID | None:
    return connection.execute(
        text("SELECT functional_location_id FROM points WHERE id = :id"), {"id": point_id}
    ).scalar()


def _assert_point_is_commandable(connection: Connection, point_id: uuid.UUID) -> None:
    """Lève CommandNotAllowed si le point n'est pas actuellement servi par un
    appareil explicitement simulé — la seule vérification qui autorise une
    commande (voir le docstring du module)."""
    equipment_id = _point_functional_location(connection, point_id)
    if equipment_id is None:
        raise CommandNotAllowed("COMMAND_POINT_NOT_CONTROLLABLE", point_id=str(point_id))

    content = get_active_mapping(connection, equipment_id=equipment_id)
    if content is None or content["device_type"] not in SIMULATED_DEVICE_TYPES:
        raise CommandNotAllowed("COMMAND_POINT_NOT_CONTROLLABLE", point_id=str(point_id))
    if not any(uuid.UUID(entry["point_id"]) == point_id for entry in content["points"]):
        raise CommandNotAllowed("COMMAND_POINT_NOT_CONTROLLABLE", point_id=str(point_id))


def create_command(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    point_id: uuid.UUID,
    requested_value: float,
    requested_by: str,
) -> uuid.UUID:
    _assert_point_is_commandable(connection, point_id)

    new_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO commands (id, tenant_id, point_id, requested_value, requested_by) "
            "VALUES (:id, :tenant_id, :point_id, :requested_value, :requested_by)"
        ),
        {
            "id": new_id,
            "tenant_id": tenant_id,
            "point_id": point_id,
            "requested_value": requested_value,
            "requested_by": requested_by,
        },
    )
    return new_id


def get_command(connection: Connection, command_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM commands WHERE id = :id"), {"id": command_id}
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_commands_for_point(
    connection: Connection, *, point_id: uuid.UUID, limit: int = 20
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(
                f"SELECT {_COLUMNS} FROM commands WHERE point_id = :point_id "
                "ORDER BY created_at DESC LIMIT :limit"
            ),
            {"point_id": point_id, "limit": limit},
        ).mappings()
    ]


def claim_pending_commands(
    connection: Connection, *, equipment_id: uuid.UUID, edge_device_id: uuid.UUID, at: datetime
) -> list[dict[str, Any]]:
    """Marque « sent » toutes les commandes en attente pour les points de cet
    équipement, et les renvoie. Une seule requête UPDATE ... RETURNING :
    aucune commande ne peut être récupérée deux fois."""
    rows = connection.execute(
        text(
            f"""
            UPDATE commands SET status = 'sent', sent_at = :at, edge_device_id = :edge_device_id
            WHERE status = 'pending' AND point_id IN (
                SELECT id FROM points WHERE functional_location_id = :equipment_id
            )
            RETURNING {_COLUMNS}
            """
        ),
        {"at": at, "edge_device_id": edge_device_id, "equipment_id": equipment_id},
    ).mappings()
    return [dict(row) for row in rows]


def acknowledge_command(
    connection: Connection,
    *,
    command_id: uuid.UUID,
    success: bool,
    actual_value: float | None,
    failure_reason: str | None,
    at: datetime,
) -> dict[str, Any]:
    command = get_command(connection, command_id)
    if command is None:
        raise CommandNotFound("COMMAND_NOT_FOUND", command_id=str(command_id))
    if command["status"] != "sent":
        raise CommandConflict("COMMAND_ALREADY_ACKNOWLEDGED", command_id=str(command_id))

    if not success:
        status, verified_at = "failed", None
    elif actual_value == command["requested_value"]:
        status, verified_at = "verified", at
    else:
        status, verified_at = "failed", None
        failure_reason = failure_reason or "ACTUAL_STATE_MISMATCH"

    connection.execute(
        text(
            "UPDATE commands SET status = :status, actual_value = :actual_value, "
            "failure_reason = :failure_reason, acknowledged_at = :at, verified_at = :verified_at "
            "WHERE id = :id"
        ),
        {
            "status": status,
            "actual_value": actual_value,
            "failure_reason": None if status == "verified" else failure_reason,
            "at": at,
            "verified_at": verified_at,
            "id": command_id,
        },
    )
    return get_command(connection, command_id)


def effective_status(command: dict[str, Any], *, now: datetime) -> str:
    """Le statut stocké, sauf « sent » depuis trop longtemps : dans ce cas
    « unconfirmed », calculé ici et jamais écrit (même principe que
    app/devices.py, `communication_status`)."""
    if command["status"] == "sent" and now - command["sent_at"] > UNCONFIRMED_AFTER:
        return "unconfirmed"
    return command["status"]
