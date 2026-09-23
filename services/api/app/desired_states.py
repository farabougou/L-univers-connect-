"""État souhaité d'un point (ADR 012, section 2.4).

En lecture seule (règle non négociable 1), l'état souhaité est une **attente
déclarée** par un humain : « éclairage éteint de 20 h à 7 h », « départ d'eau
à 45 °C ». Comparé à l'état réel (les mesures), il permet de détecter une
dérive ou un gaspillage sans jamais rien commander.

Les plages horaires sont interprétées dans le fuseau déclaré (heure légale,
changements d'heure compris) ; une plage dont le début est après la fin
passe minuit (20:00 → 07:00).
"""

import uuid
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.point_vocabulary import PointVocabularyError, check_value
from app.points import get_point

_COLUMNS = (
    "id, point_id, value, daily_start, daily_end, timezone, source, valid_from, valid_to, "
    "reason, created_by, recorded_at"
)


class DesiredStateNotFound(LookupError):
    pass


class DesiredStateInvalid(ValueError):
    pass


def check_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise DesiredStateInvalid(
            f"fuseau horaire inconnu : {name} (ex. « Europe/Paris »)"
        ) from exc


def in_daily_window(at: datetime, *, start: time, end: time, timezone: str) -> bool:
    """`at` (date avec fuseau) tombe-t-il dans la plage quotidienne [start, end)
    exprimée en heure locale du fuseau ?"""
    local = at.astimezone(check_timezone(timezone)).time()
    if start < end:
        return start <= local < end
    return local >= start or local < end


def declare_desired_state(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    point_id: uuid.UUID,
    value: float,
    valid_from: datetime,
    reason: str,
    created_by: str,
    daily_start: time | None = None,
    daily_end: time | None = None,
    timezone: str | None = None,
) -> uuid.UUID:
    point = get_point(connection, point_id)
    if point is None:
        raise DesiredStateNotFound("point introuvable")
    if point["mapping_status"] == "rejected":
        raise DesiredStateInvalid("ce point a été rejeté lors de la mise en service")
    try:
        check_value(value, value_type=point["value_type"], states=point["states"])
    except PointVocabularyError as exc:
        raise DesiredStateInvalid(str(exc)) from exc
    if (daily_start is None) != (daily_end is None):
        raise DesiredStateInvalid("une plage horaire exige un début et une fin")
    if daily_start is not None:
        if timezone is None:
            raise DesiredStateInvalid("une plage horaire exige son fuseau horaire")
        if daily_start == daily_end:
            raise DesiredStateInvalid("le début et la fin de la plage sont identiques")
    if timezone is not None:
        check_timezone(timezone)

    desired_state_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO desired_states (id, tenant_id, point_id, value, daily_start, daily_end, "
            "timezone, valid_from, reason, created_by) VALUES (:id, :tenant_id, :point_id, "
            ":value, :daily_start, :daily_end, :timezone, :valid_from, :reason, :created_by)"
        ),
        {
            "id": desired_state_id,
            "tenant_id": tenant_id,
            "point_id": point_id,
            "value": value,
            "daily_start": daily_start,
            "daily_end": daily_end,
            "timezone": timezone,
            "valid_from": valid_from,
            "reason": reason,
            "created_by": created_by,
        },
    )
    return desired_state_id


def end_desired_state(
    connection: Connection, *, desired_state_id: uuid.UUID, valid_to: datetime
) -> None:
    row = (
        connection.execute(
            text("SELECT valid_from, valid_to FROM desired_states WHERE id = :id"),
            {"id": desired_state_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise DesiredStateNotFound("état souhaité introuvable")
    if row["valid_to"] is not None:
        raise DesiredStateInvalid("cet état souhaité est déjà clos")
    if valid_to <= row["valid_from"]:
        raise DesiredStateInvalid("la date de fin doit suivre la date de début")
    connection.execute(
        text("UPDATE desired_states SET valid_to = :valid_to WHERE id = :id"),
        {"valid_to": valid_to, "id": desired_state_id},
    )


def get_desired_state(connection: Connection, desired_state_id: uuid.UUID) -> dict | None:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM desired_states WHERE id = :id"),
            {"id": desired_state_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_desired_states(
    connection: Connection, point_id: uuid.UUID, *, include_ended: bool = False
) -> list[dict[str, Any]]:
    query = f"SELECT {_COLUMNS} FROM desired_states WHERE point_id = :point_id"
    if not include_ended:
        query += " AND valid_to IS NULL"
    query += " ORDER BY valid_from"
    return [dict(row) for row in connection.execute(text(query), {"point_id": point_id}).mappings()]


def desired_state_at(
    connection: Connection, point_id: uuid.UUID, at: datetime
) -> dict[str, Any] | None:
    """L'attente qui s'applique à un instant donné : valide à cette date et,
    si elle a une plage horaire, dans cette plage. Si plusieurs s'appliquent,
    la déclaration la plus récente l'emporte."""
    candidates = connection.execute(
        text(
            f"SELECT {_COLUMNS} FROM desired_states WHERE point_id = :point_id "
            "AND valid_from <= :at AND (valid_to IS NULL OR valid_to > :at) "
            "ORDER BY valid_from DESC, recorded_at DESC"
        ),
        {"point_id": point_id, "at": at},
    ).mappings()
    for candidate in candidates:
        if candidate["daily_start"] is None or in_daily_window(
            at,
            start=candidate["daily_start"],
            end=candidate["daily_end"],
            timezone=candidate["timezone"],
        ):
            return dict(candidate)
    return None
