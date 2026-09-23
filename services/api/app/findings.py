"""Constats analytiques (ADR 012, section 2.15 ; ADR 013, étape L3).

Un constat décrit un problème observé (qualité de donnée, mise en service,
anomalie, défaut, prédiction), avec ses preuves et la règle qui l'a produit.
Un même problème en cours de traitement n'ouvre qu'un seul constat : les
répétitions incrémentent son compteur au lieu d'inonder l'exploitant.

Ce qui est enregistré est un **code de raison + paramètres**, jamais une
phrase générée : la phrase est produite à l'affichage, dans la langue de la
personne (catalogue `findings`). Seul le titre écrit par l'auteur d'une règle
(contenu du client) est stocké tel quel.

Le niveau de certitude dit ce que le système sait vraiment : « détecté » par
défaut, « confirmé » seulement par une personne, jamais pour une prédiction.

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
from app.i18n import DEFAULT_LOCALE, load_catalog, render_text
from app.signal_vocabulary import HANDLING_OPEN
from app.signals import SignalConflict, clear_condition, reactivate, record_change

FINDING_COLUMNS = (
    "id, subject_node_id, point_id, kind, method, rule_config_version_id, dedup_key, severity, "
    "reason_code, reason_params, title, recommended_action, confidence, certainty, "
    "action_required, confirmed_by, confirmed_at, evidence, condition_state, ack_state, "
    "handling_status, first_seen_at, last_seen_at, occurrence_count, alarm_id, work_order_id, "
    "created_at"
)

_OPEN_SQL = "(" + ", ".join(f"'{status}'" for status in HANDLING_OPEN) + ")"

# Code de secours pour afficher un constat dont la raison n'est pas classée.
UNCLASSIFIED = "FINDING_UNCLASSIFIED"


class FindingNotFound(DomainError, LookupError):
    status = 404


class FindingInvalid(DomainError, ValueError):
    pass


def default_certainty(kind: str) -> str:
    return "prediction" if kind == "prediction" else "detected"


def raise_or_repeat_finding(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    dedup_key: str,
    subject_node_id: uuid.UUID,
    kind: str,
    method: str,
    severity: str,
    reason_code: str,
    reason_params: dict[str, Any],
    evidence: dict[str, Any],
    seen_at: datetime,
    changed_by: str,
    point_id: uuid.UUID | None = None,
    rule_config_version_id: uuid.UUID | None = None,
    title: str | None = None,
    recommended_action: str | None = None,
    confidence: float | None = None,
) -> tuple[uuid.UUID, bool]:
    """Ouvre un constat, ou incrémente celui encore en traitement pour le même
    problème (et le réactive si la condition était revenue à la normale).

    Renvoie (identifiant, True si le constat vient d'être créé)."""
    existing = (
        connection.execute(
            text(
                "SELECT id, condition_state, alarm_id FROM findings WHERE dedup_key = :key "
                f"AND handling_status IN {_OPEN_SQL}"
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
        if existing["condition_state"] == "cleared":
            reactivate(
                connection,
                kind="finding",
                tenant_id=tenant_id,
                signal_id=existing["id"],
                changed_by=changed_by,
            )
            if existing["alarm_id"] is not None:
                reactivate(
                    connection,
                    kind="alarm",
                    tenant_id=tenant_id,
                    signal_id=existing["alarm_id"],
                    changed_by=changed_by,
                )
        return existing["id"], False

    finding_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO findings (id, tenant_id, subject_node_id, point_id, kind, method, "
            "rule_config_version_id, dedup_key, severity, reason_code, reason_params, title, "
            "recommended_action, confidence, certainty, action_required, evidence, "
            "first_seen_at, last_seen_at) VALUES (:id, :tenant_id, :subject_node_id, "
            ":point_id, :kind, :method, :rule_config_version_id, :dedup_key, :severity, "
            ":reason_code, CAST(:reason_params AS JSONB), :title, :recommended_action, "
            ":confidence, :certainty, :action_required, CAST(:evidence AS JSONB), :seen_at, "
            ":seen_at)"
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
            "reason_code": reason_code,
            "reason_params": json.dumps(reason_params, sort_keys=True, default=str),
            "title": title,
            "recommended_action": recommended_action,
            "confidence": confidence,
            "certainty": default_certainty(kind),
            "action_required": severity != "info",
            "evidence": json.dumps(evidence, sort_keys=True, default=str),
            "seen_at": seen_at,
        },
    )
    record_change(
        connection,
        kind="finding",
        tenant_id=tenant_id,
        signal_id=finding_id,
        field="handling_status",
        value="open",
        changed_by=changed_by,
    )
    return finding_id, True


def clear_finding_by_key(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    dedup_key: str,
    changed_by: str,
) -> uuid.UUID | None:
    """Retour à la normale détecté automatiquement : le constat en traitement
    pour ce problème (et son alarme) passe à « revenu à la normale ». Il reste
    à traiter : seule une personne le clôt."""
    row = (
        connection.execute(
            text(
                "SELECT id, alarm_id FROM findings WHERE dedup_key = :key "
                f"AND handling_status IN {_OPEN_SQL} AND condition_state = 'active'"
            ),
            {"key": dedup_key},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    common = {"tenant_id": tenant_id, "changed_by": changed_by, "strict": False}
    clear_condition(connection, kind="finding", signal_id=row["id"], **common)
    if row["alarm_id"] is not None:
        clear_condition(connection, kind="alarm", signal_id=row["alarm_id"], **common)
    return row["id"]


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


def confirm_finding(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    finding_id: uuid.UUID,
    confirmed_by: str,
    confirmed_at: datetime,
    note: str,
) -> None:
    """« Défaut confirmé » : seulement par une personne, après vérification.
    Une prédiction porte sur l'avenir : elle n'est jamais confirmée."""
    finding = get_finding(connection, finding_id)
    if finding is None:
        raise FindingNotFound("FINDING_NOT_FOUND")
    if confirmed_by.startswith("systeme:"):
        raise FindingInvalid("FINDING_CONFIRMATION_REQUIRES_PERSON")
    if finding["kind"] == "prediction":
        raise SignalConflict("FINDING_PREDICTION_NOT_CONFIRMABLE")
    if finding["certainty"] == "confirmed":
        raise SignalConflict("FINDING_ALREADY_CONFIRMED")
    connection.execute(
        text(
            "UPDATE findings SET certainty = 'confirmed', confirmed_by = :by, "
            "confirmed_at = :at WHERE id = :id"
        ),
        {"by": confirmed_by, "at": confirmed_at, "id": finding_id},
    )
    record_change(
        connection,
        kind="finding",
        tenant_id=tenant_id,
        signal_id=finding_id,
        field="certainty",
        value="confirmed",
        changed_by=confirmed_by,
        note=note,
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


_FILTERS = ("handling_status", "condition_state", "ack_state", "kind", "subject_node_id")


def list_findings(connection: Connection, **filters: Any) -> list[dict[str, Any]]:
    query = f"SELECT {FINDING_COLUMNS} FROM findings WHERE true"
    params: dict[str, Any] = {}
    for column in _FILTERS:
        value = filters.get(column)
        if value is not None:
            query += f" AND {column} = :{column}"
            params[column] = value
    query += " ORDER BY last_seen_at DESC"
    return [dict(row) for row in connection.execute(text(query), params).mappings()]


def displayed(finding: dict[str, Any], locale: str = DEFAULT_LOCALE) -> dict[str, Any]:
    """Titre et action recommandée dans la langue demandée. Le titre écrit
    par l'auteur d'une règle est conservé tel quel ; celui d'un constat du
    système est produit depuis son code."""
    catalog = load_catalog(locale, "findings")
    code = finding["reason_code"]
    if code not in catalog["titles"]:
        code = UNCLASSIFIED
    params = finding.get("reason_params") or {}
    authored = code.startswith("RULE_") and finding.get("title")
    return {
        **finding,
        "title": finding["title"] if authored else render_text(catalog["titles"][code], params),
        "recommended_action": finding.get("recommended_action")
        if authored
        else render_text(catalog["actions"][code], params),
    }
