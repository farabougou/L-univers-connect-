"""Constats analytiques (ADR 012, section 2.15).

Un constat décrit un problème observé (qualité de donnée, mise en service,
anomalie, défaut, prédiction), avec ses preuves et la règle qui l'a produit.
Un même problème non traité n'ouvre qu'un seul constat : les répétitions
incrémentent son compteur au lieu d'inonder l'exploitant.

Un constat n'est jamais une action sur un équipement : au plus, il lève une
alarme ou crée un ordre de travail, que des humains traitent.
"""

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError

FINDING_STATUSES = ("open", "acknowledged", "resolved", "false_positive")

FINDING_COLUMNS = (
    "id, subject_node_id, point_id, kind, method, rule_config_version_id, dedup_key, severity, "
    "title, recommended_action, confidence, evidence, status, first_seen_at, last_seen_at, "
    "occurrence_count, alarm_id, work_order_id, created_at"
)


class FindingNotFound(DomainError, LookupError):
    status = 404


class FindingInvalid(DomainError, ValueError):
    pass


def raise_or_repeat_finding(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    dedup_key: str,
    subject_node_id: uuid.UUID,
    kind: str,
    method: str,
    severity: str,
    title: str,
    evidence: dict[str, Any],
    seen_at: datetime,
    changed_by: str,
    point_id: uuid.UUID | None = None,
    rule_config_version_id: uuid.UUID | None = None,
    recommended_action: str | None = None,
    confidence: float | None = None,
) -> tuple[uuid.UUID, bool]:
    """Ouvre un constat, ou incrémente celui déjà ouvert pour le même problème.

    Renvoie (identifiant, True si le constat vient d'être créé)."""
    existing = (
        connection.execute(
            text(
                "SELECT id, last_seen_at FROM findings WHERE dedup_key = :key "
                "AND status IN ('open', 'acknowledged')"
            ),
            {"key": dedup_key},
        )
        .mappings()
        .first()
    )
    if existing is not None:
        connection.execute(
            text(
                "UPDATE findings SET occurrence_count = occurrence_count + 1, "
                "last_seen_at = GREATEST(last_seen_at, :seen_at) WHERE id = :id"
            ),
            {"seen_at": seen_at, "id": existing["id"]},
        )
        return existing["id"], False

    finding_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO findings (id, tenant_id, subject_node_id, point_id, kind, method, "
            "rule_config_version_id, dedup_key, severity, title, recommended_action, confidence, "
            "evidence, first_seen_at, last_seen_at) VALUES (:id, :tenant_id, :subject_node_id, "
            ":point_id, :kind, :method, :rule_config_version_id, :dedup_key, :severity, :title, "
            ":recommended_action, :confidence, CAST(:evidence AS JSONB), :seen_at, :seen_at)"
        ),
        {
            "id": finding_id,
            "tenant_id": tenant_id,
            "subject_node_id": subject_node_id,
            "point_id": point_id,
            "kind": kind,
            "method": method,
            "rule_config_version_id": rule_config_version_id,
            "dedup_key": dedup_key,
            "severity": severity,
            "title": title,
            "recommended_action": recommended_action,
            "confidence": confidence,
            "evidence": json.dumps(evidence, sort_keys=True, default=str),
            "seen_at": seen_at,
        },
    )
    _insert_history(
        connection,
        tenant_id=tenant_id,
        finding_id=finding_id,
        status="open",
        changed_by=changed_by,
        note=None,
    )
    return finding_id, True


def link_finding(
    connection: Connection,
    *,
    finding_id: uuid.UUID,
    alarm_id: uuid.UUID | None = None,
    work_order_id: uuid.UUID | None = None,
) -> None:
    connection.execute(
        text(
            "UPDATE findings SET alarm_id = COALESCE(:alarm_id, alarm_id), "
            "work_order_id = COALESCE(:work_order_id, work_order_id) WHERE id = :id"
        ),
        {"alarm_id": alarm_id, "work_order_id": work_order_id, "id": finding_id},
    )


def change_finding_status(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    finding_id: uuid.UUID,
    status: str,
    changed_by: str,
    note: str | None = None,
) -> None:
    if status not in FINDING_STATUSES:
        raise FindingInvalid("FINDING_STATUS_UNKNOWN", status=status)
    if get_finding(connection, finding_id) is None:
        raise FindingNotFound("FINDING_NOT_FOUND")
    connection.execute(
        text("UPDATE findings SET status = :status WHERE id = :id"),
        {"status": status, "id": finding_id},
    )
    _insert_history(
        connection,
        tenant_id=tenant_id,
        finding_id=finding_id,
        status=status,
        changed_by=changed_by,
        note=note,
    )


def _insert_history(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    finding_id: uuid.UUID,
    status: str,
    changed_by: str,
    note: str | None,
) -> None:
    connection.execute(
        text(
            "INSERT INTO finding_status_history (id, tenant_id, finding_id, status, changed_by, "
            "note) VALUES (:id, :tenant_id, :finding_id, :status, :changed_by, :note)"
        ),
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "finding_id": finding_id,
            "status": status,
            "changed_by": changed_by,
            "note": note,
        },
    )


def get_finding(connection: Connection, finding_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {FINDING_COLUMNS} FROM findings WHERE id = :id"), {"id": finding_id}
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_findings(
    connection: Connection,
    *,
    status: str | None = None,
    kind: str | None = None,
    subject_node_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    query = f"SELECT {FINDING_COLUMNS} FROM findings WHERE true"
    params: dict[str, Any] = {}
    for column, value in (("status", status), ("kind", kind), ("subject_node_id", subject_node_id)):
        if value is not None:
            query += f" AND {column} = :{column}"
            params[column] = value
    query += " ORDER BY last_seen_at DESC"
    return [dict(row) for row in connection.execute(text(query), params).mappings()]


def finding_history(connection: Connection, finding_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(
                "SELECT id, finding_id, status, changed_by, note, changed_at "
                "FROM finding_status_history WHERE finding_id = :id ORDER BY changed_at"
            ),
            {"id": finding_id},
        ).mappings()
    ]
