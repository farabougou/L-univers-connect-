"""Changements d'état communs aux alarmes et aux constats (ADR 013, 4.2).

Chaque axe change indépendamment et chaque changement ajoute une ligne à
l'historique (jamais modifié) : champ concerné, nouvelle valeur, auteur,
note. Rien n'est écrasé.

Règles :
- acquitter signifie « j'ai pris connaissance », jamais « c'est réglé » ;
- un signalement ne peut être clos que si sa condition est revenue à la
  normale ; le déclarer faux positif est toujours possible ;
- clore ou déclarer faux positif vaut acquittement s'il n'a pas eu lieu.
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError
from app.signal_vocabulary import HANDLING_STATUSES

# genre → (table, table d'historique, colonne de rattachement)
_TABLES = {
    "finding": ("findings", "finding_status_history", "finding_id"),
    "alarm": ("alarms", "alarm_status_history", "alarm_id"),
}


class SignalNotFound(DomainError, LookupError):
    status = 404


class SignalConflict(DomainError, ValueError):
    status = 409


class SignalInvalid(DomainError, ValueError):
    pass


def _not_found(kind: str) -> SignalNotFound:
    return SignalNotFound("FINDING_NOT_FOUND" if kind == "finding" else "ALARM_NOT_FOUND")


def get_axes(connection: Connection, kind: str, signal_id: uuid.UUID) -> dict[str, Any]:
    table, _, _ = _TABLES[kind]
    row = (
        connection.execute(
            text(f"SELECT condition_state, ack_state, handling_status FROM {table} WHERE id = :id"),
            {"id": signal_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise _not_found(kind)
    return dict(row)


def record_change(
    connection: Connection,
    *,
    kind: str,
    tenant_id: uuid.UUID,
    signal_id: uuid.UUID,
    field: str,
    value: str,
    changed_by: str,
    note: str | None = None,
) -> None:
    _, history, link = _TABLES[kind]
    connection.execute(
        text(
            f"INSERT INTO {history} (id, tenant_id, {link}, field, status, changed_by, note, "
            "changed_at) VALUES (:id, :tenant_id, :signal_id, :field, :value, :changed_by, "
            # clock_timestamp() avance à chaque ligne : plusieurs changements
            # d'une même transaction gardent leur ordre dans l'historique.
            ":note, clock_timestamp())"
        ),
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "signal_id": signal_id,
            "field": field,
            "value": value,
            "changed_by": changed_by,
            "note": note,
        },
    )


def set_axis(
    connection: Connection,
    *,
    kind: str,
    tenant_id: uuid.UUID,
    signal_id: uuid.UUID,
    field: str,
    value: str,
    changed_by: str,
    note: str | None = None,
) -> bool:
    """Change un axe s'il n'a pas déjà cette valeur ; renvoie True si changé."""
    table, _, _ = _TABLES[kind]
    changed = connection.execute(
        text(
            f"UPDATE {table} SET {field} = :value WHERE id = :id "
            f"AND {field} IS DISTINCT FROM :value RETURNING id"
        ),
        {"value": value, "id": signal_id},
    ).scalar()
    if changed is None:
        return False
    record_change(
        connection,
        kind=kind,
        tenant_id=tenant_id,
        signal_id=signal_id,
        field=field,
        value=value,
        changed_by=changed_by,
        note=note,
    )
    return True


def acknowledge(
    connection: Connection,
    *,
    kind: str,
    tenant_id: uuid.UUID,
    signal_id: uuid.UUID,
    changed_by: str,
    note: str | None = None,
) -> None:
    get_axes(connection, kind, signal_id)
    set_axis(
        connection,
        kind=kind,
        tenant_id=tenant_id,
        signal_id=signal_id,
        field="ack_state",
        value="acknowledged",
        changed_by=changed_by,
        note=note,
    )


def set_handling(
    connection: Connection,
    *,
    kind: str,
    tenant_id: uuid.UUID,
    signal_id: uuid.UUID,
    handling_status: str,
    changed_by: str,
    note: str | None = None,
) -> None:
    if handling_status not in HANDLING_STATUSES:
        raise SignalInvalid("SIGNAL_HANDLING_UNKNOWN", value=handling_status)
    axes = get_axes(connection, kind, signal_id)
    if handling_status == "closed" and axes["condition_state"] == "active":
        raise SignalConflict("SIGNAL_CONDITION_STILL_ACTIVE")
    common = {"kind": kind, "tenant_id": tenant_id, "signal_id": signal_id}
    if handling_status in ("closed", "false_positive"):
        set_axis(
            connection, **common, field="ack_state", value="acknowledged", changed_by=changed_by
        )
    set_axis(
        connection,
        **common,
        field="handling_status",
        value=handling_status,
        changed_by=changed_by,
        note=note,
    )


def clear_condition(
    connection: Connection,
    *,
    kind: str,
    tenant_id: uuid.UUID,
    signal_id: uuid.UUID,
    changed_by: str,
    note: str | None = None,
    strict: bool = True,
) -> bool:
    """Retour à la normale. `strict` : refuser si c'est déjà le cas (action
    humaine) ; sinon ne rien faire (détection automatique)."""
    axes = get_axes(connection, kind, signal_id)
    if axes["condition_state"] == "cleared":
        if strict:
            raise SignalConflict("SIGNAL_ALREADY_CLEARED")
        return False
    return set_axis(
        connection,
        kind=kind,
        tenant_id=tenant_id,
        signal_id=signal_id,
        field="condition_state",
        value="cleared",
        changed_by=changed_by,
        note=note,
    )


def reactivate(
    connection: Connection,
    *,
    kind: str,
    tenant_id: uuid.UUID,
    signal_id: uuid.UUID,
    changed_by: str,
) -> None:
    """La condition réapparaît avant la clôture : de nouveau active et à
    acquitter, puisque c'est une nouvelle occurrence."""
    common = {"kind": kind, "tenant_id": tenant_id, "signal_id": signal_id}
    set_axis(connection, **common, field="condition_state", value="active", changed_by=changed_by)
    set_axis(connection, **common, field="ack_state", value="unacknowledged", changed_by=changed_by)


def history(connection: Connection, kind: str, signal_id: uuid.UUID) -> list[dict[str, Any]]:
    _, table, link = _TABLES[kind]
    return [
        dict(row)
        for row in connection.execute(
            text(
                f"SELECT id, {link} AS signal_id, field, status AS value, changed_by, note, "
                f"changed_at FROM {table} WHERE {link} = :id ORDER BY changed_at, id"
            ),
            {"id": signal_id},
        ).mappings()
    ]
