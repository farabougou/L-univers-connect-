"""Clôture structurée d'une intervention (cahier des charges, section 36).

Une clôture est une preuve : enregistrée une fois, jamais modifiée ni
supprimée (déclencheurs en base). Les codes viennent d'un vocabulaire fermé
(app.closure_vocabulary) pour pouvoir être comptés, comparés et, plus tard,
servir d'étiquettes au diagnostic automatique.
"""

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.closure_vocabulary import ACTIONS, CAUSES, SYMPTOMS, VERIFICATION_RESULTS


class ClosureError(ValueError):
    pass


class ClosureNotFound(LookupError):
    pass


class ClosureConflict(ValueError):
    pass


_COLUMNS = (
    "id, intervention_id, symptom_code, cause_code, action_code, parts, labor_minutes, "
    "verification_result, note, closed_by, closed_at"
)


def close_intervention(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    intervention_id: uuid.UUID,
    symptom_code: str,
    cause_code: str,
    action_code: str,
    parts: list[dict[str, Any]],
    labor_minutes: int,
    verification_result: str,
    closed_by: str,
    note: str | None = None,
) -> uuid.UUID:
    for code, vocabulary, label in (
        (symptom_code, SYMPTOMS, "symptôme"),
        (cause_code, CAUSES, "cause"),
        (action_code, ACTIONS, "action"),
        (verification_result, VERIFICATION_RESULTS, "résultat de vérification"),
    ):
        if code not in vocabulary:
            raise ClosureError(f"code de {label} inconnu : {code}")
    if action_code == "replacement" and not parts:
        raise ClosureError("un remplacement doit indiquer la ou les pièces remplacées")

    exists = connection.execute(
        text("SELECT 1 FROM interventions WHERE id = :id"), {"id": intervention_id}
    ).scalar()
    if not exists:
        raise ClosureNotFound("intervention introuvable")
    already = connection.execute(
        text("SELECT 1 FROM intervention_closures WHERE intervention_id = :id"),
        {"id": intervention_id},
    ).scalar()
    if already:
        raise ClosureConflict("cette intervention est déjà clôturée")

    closure_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO intervention_closures (id, tenant_id, intervention_id, symptom_code, "
            "cause_code, action_code, parts, labor_minutes, verification_result, note, "
            "closed_by) VALUES (:id, :tenant_id, :intervention_id, :symptom_code, :cause_code, "
            ":action_code, CAST(:parts AS JSONB), :labor_minutes, :verification_result, :note, "
            ":closed_by)"
        ),
        {
            "id": closure_id,
            "tenant_id": tenant_id,
            "intervention_id": intervention_id,
            "symptom_code": symptom_code,
            "cause_code": cause_code,
            "action_code": action_code,
            "parts": json.dumps(parts, ensure_ascii=False),
            "labor_minutes": labor_minutes,
            "verification_result": verification_result,
            "note": note,
            "closed_by": closed_by,
        },
    )
    return closure_id


def get_closure(connection: Connection, intervention_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM intervention_closures WHERE intervention_id = :id"),
            {"id": intervention_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None
