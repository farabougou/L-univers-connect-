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
- timed_out : envoyée à l'Edge depuis plus de `UNCONFIRMED_AFTER` sans
  accusé de réception — transition persistée par `mark_command_timed_out`
  (voir app/monitoring.py), jamais depuis une simple lecture qui ne
  changerait rien d'elle-même.
- unconfirmed (calculé à la lecture, jamais stocké — même principe que
  app/devices.py, `communication_status`) : utilisé uniquement par le
  passeport (app/passport.py), qui reste une vue pure sans jamais écrire ;
  partout ailleurs, `mark_command_timed_out` rend ce même constat durable.

Chaque étape franchie par une commande produit un événement persistant
(app/events.py) — État → Événement → Politique → Alerte, directive de
Mohamed du 24/09/2026 : COMMAND_REQUESTED, COMMAND_DISPATCHED,
COMMAND_VERIFIED, COMMAND_FAILED, COMMAND_TIMED_OUT.

V2 (02/10/2026) : `validate_command` regroupe les vérifications qu'une
commande doit passer (commandabilité puis policy active du point, voir
app/command_policies.py) sans rien créer — appelée par `create_command`
avant insertion, et seule à s'exécuter pour un essai à blanc (dry-run,
POST /commands?dry_run=true côté routeur) : un essai à blanc ne saute
jamais une vérification que la création réelle ferait.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.command_policies import PolicyViolation, enforce_policy, get_active_policy
from app.connectors.device_mapping import SIMULATED_DEVICE_TYPES, get_active_mapping
from app.errors import DomainError
from app.events import record_event

_COLUMNS = (
    "id, tenant_id, point_id, requested_value, requested_by, status, actual_value, "
    "failure_reason, created_at, sent_at, acknowledged_at, verified_at, edge_device_id, "
    "requester_roles"
)

# Au-delà de ce délai sans accusé de réception, une commande envoyée est
# considérée non confirmée plutôt que silencieusement "en cours" pour
# toujours : l'Edge a pu ne jamais la recevoir.
UNCONFIRMED_AFTER = timedelta(minutes=5)

# Au-delà de ce délai sans avoir été réclamée par l'Edge (jamais envoyée),
# une commande en attente n'est plus exécutée telle quelle (audit sécurité
# du 16/10/2026, pistes Siemens SSA-333035) : l'intention qu'elle portait
# peut ne plus être pertinente après une coupure prolongée de l'automate,
# et la policy active du point a pu changer entre-temps sans que cette
# commande déjà créée en tienne compte. Même tolérance que UNCONFIRMED_AFTER
# (mesurée depuis la création plutôt que l'envoi, puisqu'ici rien n'a
# encore été envoyé) — deux constantes distinctes malgré la même valeur :
# elles répondent à deux questions différentes (« trop vieille pour partir »
# vs « trop vieille pour rester sans réponse »).
PENDING_EXPIRY = timedelta(minutes=5)


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


def validate_command(
    connection: Connection,
    *,
    point_id: uuid.UUID,
    requested_value: float,
    requester_roles: list[str],
) -> None:
    """Les vérifications qu'une commande doit passer, sans rien créer :
    commandabilité (règle non négociable 1) puis policy active du point
    (app.command_policies), si elle existe. Utilisée par create_command
    avant insertion, et seule à s'exécuter en mode dry-run (POST
    /commands?dry_run) — le dry-run ne doit jamais sauter une vérification
    que la création réelle ferait, ni en faire une de plus."""
    _assert_point_is_commandable(connection, point_id)
    policy = get_active_policy(connection, point_id)
    enforce_policy(policy, requested_value=requested_value, roles=requester_roles)


def create_command(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    point_id: uuid.UUID,
    requested_value: float,
    requested_by: str,
    requester_roles: list[str],
    at: datetime | None = None,
) -> uuid.UUID:
    validate_command(
        connection,
        point_id=point_id,
        requested_value=requested_value,
        requester_roles=requester_roles,
    )
    at = at or datetime.now(UTC)

    new_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO commands "
            "(id, tenant_id, point_id, requested_value, requested_by, requester_roles) "
            "VALUES (:id, :tenant_id, :point_id, :requested_value, :requested_by, "
            "CAST(:requester_roles AS JSONB))"
        ),
        {
            "id": new_id,
            "tenant_id": tenant_id,
            "point_id": point_id,
            "requested_value": requested_value,
            "requested_by": requested_by,
            "requester_roles": json.dumps(requester_roles),
        },
    )
    record_event(
        connection,
        tenant_id=tenant_id,
        event_type="COMMAND_REQUESTED",
        subject_type="command",
        subject_id=new_id,
        payload={"point_id": str(point_id), "requested_value": requested_value},
        occurred_at=at,
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


def _expire_stale_pending_commands(
    connection: Connection, *, equipment_id: uuid.UUID, at: datetime
) -> None:
    """Fait transiter vers « failed » (COMMAND_EXPIRED) toute commande encore
    « pending » pour cet équipement depuis plus de PENDING_EXPIRY, avant
    toute tentative de réclamation : une commande expirée n'est jamais
    envoyée à l'appareil, jamais rejouée après une coupure prolongée. Une
    seule requête UPDATE ... RETURNING, même garantie d'unicité que
    claim_pending_commands : une commande expirée ne peut pas aussi être
    réclamée par le même appel."""
    rows = connection.execute(
        text(
            """
            UPDATE commands SET status = 'failed', failure_reason = 'COMMAND_EXPIRED'
            WHERE status = 'pending' AND created_at <= :deadline AND point_id IN (
                SELECT id FROM points WHERE functional_location_id = :equipment_id
            )
            RETURNING id, tenant_id
            """
        ),
        {"deadline": at - PENDING_EXPIRY, "equipment_id": equipment_id},
    ).mappings()
    for row in rows:
        record_event(
            connection,
            tenant_id=row["tenant_id"],
            event_type="COMMAND_FAILED",
            subject_type="command",
            subject_id=row["id"],
            payload={"failure_reason": "COMMAND_EXPIRED"},
            occurred_at=at,
        )


def claim_pending_commands(
    connection: Connection, *, equipment_id: uuid.UUID, edge_device_id: uuid.UUID, at: datetime
) -> list[dict[str, Any]]:
    """Marque « sent » les commandes en attente pour les points de cet
    équipement, et les renvoie — après avoir expiré les plus anciennes
    (voir _expire_stale_pending_commands) et revérifié, pour chacune des
    restantes, la commandabilité du point et sa policy active : ni l'une ni
    l'autre ne sont supposées inchangées depuis la création de la commande
    (audit sécurité du 16/10/2026, pistes Siemens SSA-333035 — même
    discipline que app.scheduled_commands.dispatch_due_scheduled_commands,
    jusqu'ici absente de ce chemin-ci). Une commande qui échoue cette
    revérification devient « failed », jamais silencieusement oubliée ni
    envoyée malgré l'échec.

    Chaque transition (vers « sent » ou vers « failed ») est une requête
    UPDATE ... RETURNING gardée par `WHERE status = 'pending'` : si une
    autre réclamation concurrente a déjà transitionné la même ligne entre
    temps, celle-ci n'affecte aucune ligne et est simplement ignorée —
    aucune commande ne peut être récupérée, ni échouée, deux fois."""
    _expire_stale_pending_commands(connection, equipment_id=equipment_id, at=at)

    candidates = connection.execute(
        text(
            f"""
            SELECT {_COLUMNS} FROM commands
            WHERE status = 'pending' AND point_id IN (
                SELECT id FROM points WHERE functional_location_id = :equipment_id
            )
            """
        ),
        {"equipment_id": equipment_id},
    ).mappings()

    claimed: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            _assert_point_is_commandable(connection, candidate["point_id"])
            policy = get_active_policy(connection, candidate["point_id"])
            enforce_policy(
                policy,
                requested_value=candidate["requested_value"],
                roles=candidate["requester_roles"],
            )
        except (CommandNotAllowed, PolicyViolation) as exc:
            failed_id = connection.execute(
                text(
                    "UPDATE commands SET status = 'failed', failure_reason = :reason "
                    "WHERE id = :id AND status = 'pending' RETURNING id"
                ),
                {"reason": exc.code, "id": candidate["id"]},
            ).scalar()
            if failed_id is None:
                continue
            record_event(
                connection,
                tenant_id=candidate["tenant_id"],
                event_type="COMMAND_FAILED",
                subject_type="command",
                subject_id=candidate["id"],
                payload={"failure_reason": exc.code},
                occurred_at=at,
            )
            continue

        sent_id = connection.execute(
            text(
                "UPDATE commands SET status = 'sent', sent_at = :at, "
                "edge_device_id = :edge_device_id "
                "WHERE id = :id AND status = 'pending' RETURNING id"
            ),
            {"at": at, "edge_device_id": edge_device_id, "id": candidate["id"]},
        ).scalar()
        if sent_id is None:
            continue
        command = get_command(connection, candidate["id"])
        record_event(
            connection,
            tenant_id=command["tenant_id"],
            event_type="COMMAND_DISPATCHED",
            subject_type="command",
            subject_id=command["id"],
            payload={"edge_device_id": str(edge_device_id)},
            occurred_at=at,
        )
        claimed.append(command)
    return claimed


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
    updated = get_command(connection, command_id)
    record_event(
        connection,
        tenant_id=updated["tenant_id"],
        event_type="COMMAND_VERIFIED" if status == "verified" else "COMMAND_FAILED",
        subject_type="command",
        subject_id=command_id,
        payload={"actual_value": actual_value, "failure_reason": updated["failure_reason"]},
        occurred_at=at,
    )
    return updated


def mark_command_timed_out(
    connection: Connection, *, command_id: uuid.UUID, at: datetime
) -> dict[str, Any] | None:
    """Transition persistée sent → timed_out (voir app/monitoring.py, appelée
    depuis les points de lecture dédiés à une commande — jamais depuis le
    passeport, qui reste une vue pure sans effet de bord).

    Idempotente : renvoie None si la commande n'était pas dans l'état
    « sent » depuis plus de UNCONFIRMED_AFTER, sans lever d'erreur — un
    appel « pour rien » (commande déjà vérifiée entre-temps, ou pas encore
    au-delà du délai) est normal, pas une anomalie."""
    updated_id = connection.execute(
        text(
            "UPDATE commands SET status = 'timed_out', failure_reason = 'COMMAND_TIMED_OUT' "
            "WHERE id = :id AND status = 'sent' AND sent_at <= :deadline RETURNING id"
        ),
        {"id": command_id, "deadline": at - UNCONFIRMED_AFTER},
    ).scalar()
    if updated_id is None:
        return None
    command = get_command(connection, command_id)
    record_event(
        connection,
        tenant_id=command["tenant_id"],
        event_type="COMMAND_TIMED_OUT",
        subject_type="command",
        subject_id=command_id,
        occurred_at=at,
    )
    return command


def effective_status(command: dict[str, Any], *, now: datetime) -> str:
    """Le statut stocké, sauf « sent » depuis trop longtemps : dans ce cas
    « unconfirmed », calculé ici et jamais écrit (même principe que
    app/devices.py, `communication_status`). Réservé au passeport
    (app/passport.py) : partout ailleurs, `mark_command_timed_out` rend ce
    même constat durable plutôt que de le recalculer à chaque lecture."""
    if command["status"] == "sent" and now - command["sent_at"] > UNCONFIRMED_AFTER:
        return "unconfirmed"
    return command["status"]
