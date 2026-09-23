"""Règles déterministes (ADR 012, étape F4) : premier maillon du FDD.

Deux types de règles, stockées comme configurations versionnées
(`alarm_rule`) :
- `threshold` : une valeur dépasse un seuil → constat de nature « fault » ;
- `desired_state_divergence` : l'état réel s'écarte de l'état souhaité
  déclaré → constat de nature « commissioning » (l'installation ne se
  comporte plus comme attendu).

Chaîne complète, synchrone à la réception d'une mesure (squelette de bout en
bout M2) : mesure → contrôle de qualité → règle → constat → alarme → ordre de
travail. Garde-fous :
- une valeur marquée douteuse à la réception ouvre un constat de qualité et
  n'est jamais évaluée par les règles ;
- un point dont le score de confiance est insuffisant n'est pas évalué, et le
  constat de qualité le dit ;
- aucune règle ne commande quoi que ce soit (règle non négociable 1).
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.config_versions import ConfigInvalid, active_versions, register_config_type
from app.desired_states import desired_state_at
from app.findings import link_finding, raise_or_repeat_finding
from app.maintenance import create_work_order, raise_alarm
from app.points import get_point
from app.quality_flags import FLAG_CLOCK_SUSPECT, FLAG_OUT_OF_RANGE
from app.trust import MIN_TRUST_FOR_RULES, compute_trust

ALARM_RULE = "alarm_rule"
ALARM_RULE_SCHEMA = "alarm_rule/1"
SYSTEM_ACTOR = "systeme:regles"

# Drapeaux qui rendent une valeur inutilisable pour un diagnostic.
_BLOCKING_FLAGS = {
    FLAG_OUT_OF_RANGE: "valeur hors de la plage physique du capteur",
    FLAG_CLOCK_SUSPECT: "horloge suspecte (relevé daté dans le futur)",
}


class _RuleBase(BaseModel):
    model_config = {"extra": "forbid"}

    point_id: uuid.UUID
    severity: Literal["info", "warning", "critical"]
    title: str = Field(min_length=1, max_length=300)
    recommended_action: str | None = Field(default=None, max_length=1000)
    create_work_order: bool = False


class ThresholdRule(_RuleBase):
    kind: Literal["threshold"]
    operator: Literal[">", "<"]
    threshold: float = Field(allow_inf_nan=False)


class DivergenceRule(_RuleBase):
    kind: Literal["desired_state_divergence"]
    tolerance: float = Field(default=0, ge=0, allow_inf_nan=False)


class _RuleContent(BaseModel):
    rule: Annotated[ThresholdRule | DivergenceRule, Field(discriminator="kind")]


def _validate_alarm_rule(connection: Connection, content: dict[str, Any]) -> dict[str, Any]:
    try:
        rule = _RuleContent(rule=content).rule
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in error["loc"][1:]) for error in exc.errors()})
        raise ConfigInvalid("RULE_CONTENT_INVALID", fields=fields) from exc
    point = get_point(connection, rule.point_id)
    if point is None:
        raise ConfigInvalid("RULE_POINT_NOT_FOUND")
    if point["mapping_status"] != "validated":
        raise ConfigInvalid("RULE_POINT_NOT_VALIDATED")
    if isinstance(rule, ThresholdRule) and point["value_type"] != "number":
        raise ConfigInvalid("RULE_THRESHOLD_REQUIRES_NUMBER")
    return rule.model_dump(mode="json", exclude_none=True)


register_config_type(ALARM_RULE, ALARM_RULE_SCHEMA, _validate_alarm_rule)


def _subject(point: dict[str, Any]) -> uuid.UUID:
    """Le constat porte sur l'équipement du point, à défaut son espace."""
    return point["functional_location_id"] or point["space_id"] or point["id"]


def _evaluate(
    connection: Connection, rule: dict[str, Any], point: dict[str, Any], value: float, at: datetime
) -> dict[str, Any] | None:
    """Renvoie les preuves si la règle est enfreinte, sinon None."""
    if rule["kind"] == "threshold":
        breached = (
            value > rule["threshold"] if rule["operator"] == ">" else value < rule["threshold"]
        )
        if breached:
            return {"value": value, "operator": rule["operator"], "threshold": rule["threshold"]}
        return None

    desired = desired_state_at(connection, point["id"], at)
    if desired is None:
        return None
    gap = abs(value - desired["value"])
    if gap > rule["tolerance"]:
        return {
            "actual": value,
            "desired": desired["value"],
            "tolerance": rule["tolerance"],
            "desired_state_id": str(desired["id"]),
        }
    return None


def evaluate_after_measurement(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    point: dict[str, Any],
    value: float,
    measured_at: datetime,
    quality_flags: list[str],
) -> list[uuid.UUID]:
    """Évalue qualité puis règles pour un relevé qui vient d'être enregistré.
    Renvoie les constats ouverts ou répétés."""
    touched: list[uuid.UUID] = []
    subject = _subject(point)
    base_evidence = {
        "point_id": str(point["id"]),
        "measured_at": measured_at.isoformat(),
        "value": value,
    }

    blocking = [flag for flag in quality_flags if flag in _BLOCKING_FLAGS]
    for flag in blocking:
        finding_id, _ = raise_or_repeat_finding(
            connection,
            tenant_id=tenant_id,
            dedup_key=f"quality:{point['id']}:{flag}",
            subject_node_id=subject,
            point_id=point["id"],
            kind="data_quality",
            method="deterministic_rule",
            severity="warning",
            title=f"Donnée douteuse sur {point['code']} : {_BLOCKING_FLAGS[flag]}",
            recommended_action="Vérifier le capteur, son câblage et son horloge.",
            evidence={**base_evidence, "flag": flag},
            seen_at=measured_at,
            changed_by=SYSTEM_ACTOR,
        )
        touched.append(finding_id)
    if blocking:
        return touched

    rules = active_versions(
        connection, config_type=ALARM_RULE, content_filter={"point_id": str(point["id"])}
    )
    if not rules:
        return touched

    trust = compute_trust(connection, point, measured_at)
    if trust["score"] < MIN_TRUST_FOR_RULES:
        finding_id, _ = raise_or_repeat_finding(
            connection,
            tenant_id=tenant_id,
            dedup_key=f"quality:{point['id']}:low_trust",
            subject_node_id=subject,
            point_id=point["id"],
            kind="data_quality",
            method="deterministic_rule",
            severity="warning",
            title=f"Règles non évaluées sur {point['code']} : confiance insuffisante",
            recommended_action="Contrôler le capteur avant de se fier aux alarmes de ce point.",
            evidence={**base_evidence, "trust": trust},
            seen_at=measured_at,
            changed_by=SYSTEM_ACTOR,
        )
        return touched + [finding_id]

    for version in rules:
        rule = version["content"]
        evidence = _evaluate(connection, rule, point, value, measured_at)
        if evidence is None:
            continue
        finding_id, created = raise_or_repeat_finding(
            connection,
            tenant_id=tenant_id,
            dedup_key=f"rule:{ALARM_RULE}:{version['subject_key']}",
            subject_node_id=subject,
            point_id=point["id"],
            kind="fault" if rule["kind"] == "threshold" else "commissioning",
            method="deterministic_rule",
            rule_config_version_id=version["id"],
            severity=rule["severity"],
            title=rule["title"],
            recommended_action=rule.get("recommended_action"),
            confidence=1.0,
            evidence={**base_evidence, **evidence, "trust_score": trust["score"]},
            seen_at=measured_at,
            changed_by=SYSTEM_ACTOR,
        )
        touched.append(finding_id)
        if created:
            _escalate(
                connection, tenant_id=tenant_id, finding_id=finding_id, rule=rule, point=point
            )
    return touched


def _escalate(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    finding_id: uuid.UUID,
    rule: dict[str, Any],
    point: dict[str, Any],
) -> None:
    """Nouveau constat : alarme pour prévenir, et ordre de travail si la règle
    le demande. Chaque création automatique est tracée dans le journal
    d'audit, comme une action humaine."""
    alarm_id = raise_alarm(
        connection,
        tenant_id=tenant_id,
        raised_by=SYSTEM_ACTOR,
        severity=rule["severity"],
        message=rule["title"][:500],
        functional_location_id=point["functional_location_id"],
    )
    work_order_id = None
    if rule.get("create_work_order"):
        work_order_id = create_work_order(
            connection,
            tenant_id=tenant_id,
            created_by=SYSTEM_ACTOR,
            title=rule["title"][:200],
            description=rule.get("recommended_action"),
            work_order_type="corrective",
            priority="high" if rule["severity"] == "critical" else "medium",
            functional_location_id=point["functional_location_id"],
        )
    link_finding(connection, finding_id=finding_id, alarm_id=alarm_id, work_order_id=work_order_id)
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=SYSTEM_ACTOR,
        action="finding.raised",
        entity_type="finding",
        entity_id=str(finding_id),
        payload={
            "alarm_id": str(alarm_id),
            "work_order_id": str(work_order_id) if work_order_id else None,
        },
    )
