"""Règles déterministes (ADR 012, étape F4) : premier maillon du FDD.

Trois types de règles, stockées comme configurations versionnées
(`alarm_rule`) :
- `threshold` : une valeur dépasse un seuil → constat de nature « fault » ;
- `desired_state_divergence` : l'état réel s'écarte de l'état souhaité
  déclaré → constat de nature « commissioning » (l'installation ne se
  comporte plus comme attendu) ;
- `simultaneous_heating_cooling` : chauffage et refroidissement actifs en
  même temps sur le même équipement → constat de nature « fault ». Un
  FDD (Fault Detection and Diagnostics) standard du secteur — Honeywell,
  Siemens, Johnson Controls le proposent tous, et la Californie l'impose par
  réglementation (Title 24) sur les économiseurs — jamais du machine
  learning : une comparaison physique immédiate entre deux points, sans
  historique, donc jamais concerné par le blocage de la maintenance
  prédictive (feature-benchmark-matrix.md : aucune donnée réelle
  disponible). Premier type de règle qui porte sur deux points à la fois au
  lieu d'un seul (voir `evaluate_after_measurement` et
  `_evaluate_simultaneous_heating_cooling`).
- `short_cycling` (01/10/2026) : trop de démarrages d'un équipement
  (transition arrêt → marche d'un point `run_status` booléen) sur une
  fenêtre de temps glissante → constat de nature « fault ». Deuxième AFDD
  standard du secteur (ASHRAE Guideline 36, protection moteur/compresseur) et
  premier type de règle qui porte sur un historique de mesures plutôt que sur
  l'instant présent seul (voir `_evaluate_short_cycling`) : la valeur qui
  vient d'être enregistrée n'est comptée comme un nouveau démarrage que si le
  relevé immédiatement antérieur n'était pas déjà à « marche », jamais à
  chaque relevé « marche » répété pendant qu'un cycle est déjà en cours.
- `trend_projection` (02/10/2026, décision de Mohamed : le pipeline logiciel
  de maintenance prédictive avance en simulation, seule l'annonce d'une
  performance réelle reste `DEFERRED_PHYSICAL_VALIDATION`) : premier type de
  règle qui porte sur l'avenir plutôt que sur le présent ou le passé →
  constat de nature « prediction ». Projection linéaire déterministe
  (`method="statistical"`, jamais `"ml"` : aucun modèle entraîné, une
  extrapolation explicable à partir de deux points de l'historique récent) —
  si la tendance actuelle atteindrait le seuil donné dans l'horizon donné,
  et seulement si ce seuil n'est pas déjà franchi maintenant (ce cas relève
  de `threshold`, qui constate, pas de `trend_projection`, qui prédit). Voir
  `_evaluate_trend_projection`.

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
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.config_versions import ConfigInvalid, active_versions, register_config_type
from app.desired_states import desired_state_at
from app.equipment_status import latest_usable_bulk
from app.findings import clear_finding_by_key, link_finding, raise_or_repeat_finding
from app.maintenance import create_work_order, raise_alarm
from app.points import get_point
from app.quality_flags import FLAG_CLOCK_SUSPECT, FLAG_OUT_OF_RANGE
from app.signal_vocabulary import WORK_ORDER_PRIORITY
from app.trust import MIN_TRUST_FOR_RULES, STALE_AFTER_INTERVALS, compute_trust

ALARM_RULE = "alarm_rule"
ALARM_RULE_SCHEMA = "alarm_rule/1"
SYSTEM_ACTOR = "systeme:regles"

# Drapeaux qui rendent une valeur inutilisable pour un diagnostic, avec le
# code de raison du constat de qualité correspondant.
_BLOCKING_FLAGS = {
    FLAG_OUT_OF_RANGE: "DATA_QUALITY_OUT_OF_RANGE",
    FLAG_CLOCK_SUSPECT: "DATA_QUALITY_CLOCK_SUSPECT",
}
_RULE_REASONS = {
    "threshold": "RULE_THRESHOLD_EXCEEDED",
    "desired_state_divergence": "RULE_DESIRED_STATE_DIVERGENCE",
    "simultaneous_heating_cooling": "RULE_SIMULTANEOUS_HEATING_COOLING",
    "short_cycling": "RULE_SHORT_CYCLING",
    "trend_projection": "RULE_TREND_PROJECTION",
}
# Nature du constat ouvert par chaque type de règle (voir app/findings.py,
# ck_findings_kind) : un écart à la consigne reste un sujet de mise en
# service, tout le reste est une panne constatée — sauf trend_projection,
# qui porte sur l'avenir, jamais sur le présent ou le passé.
_FINDING_KIND = {
    "threshold": "fault",
    "desired_state_divergence": "commissioning",
    "simultaneous_heating_cooling": "fault",
    "short_cycling": "fault",
    "trend_projection": "prediction",
}
# Méthode enregistrée pour le constat (ck_findings_method) : une projection
# est un calcul statistique explicable, jamais un modèle entraîné (`"ml"`
# resterait un mensonge tant qu'aucun modèle n'existe réellement).
_RULE_METHOD = {
    "trend_projection": "statistical",
}


class _RuleBase(BaseModel):
    model_config = {"extra": "forbid"}

    point_id: uuid.UUID
    severity: Literal["info", "warning", "major", "critical"]
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


class ShortCyclingRule(_RuleBase):
    """Porte sur un point `run_status` booléen : trop de démarrages sur la
    fenêtre glissante `window_minutes` (voir `_evaluate_short_cycling`)."""

    kind: Literal["short_cycling"]
    max_starts: int = Field(gt=0)
    window_minutes: int = Field(gt=0)


class TrendProjectionRule(_RuleBase):
    """Projection linéaire déterministe d'un point numérique : si la pente
    des `window_minutes` dernières minutes atteindrait `threshold` dans les
    `horizon_minutes` à venir, ouvre un constat de prédiction (voir
    `_evaluate_trend_projection`). Jamais déclenchée si le seuil est déjà
    franchi maintenant — ce cas relève de `ThresholdRule`, qui constate,
    jamais d'une règle qui prédit."""

    kind: Literal["trend_projection"]
    operator: Literal[">", "<"]
    threshold: float = Field(allow_inf_nan=False)
    window_minutes: int = Field(gt=0)
    horizon_minutes: int = Field(gt=0)


class CorrelationRule(BaseModel):
    """Compare deux points du même équipement au même instant (FDD) — jamais
    un seul point comme les deux règles ci-dessus, voir le docstring du
    module."""

    model_config = {"extra": "forbid"}

    kind: Literal["simultaneous_heating_cooling"]
    heating_point_id: uuid.UUID
    cooling_point_id: uuid.UUID
    heating_threshold: float = Field(default=0, ge=0, allow_inf_nan=False)
    cooling_threshold: float = Field(default=0, ge=0, allow_inf_nan=False)
    severity: Literal["info", "warning", "major", "critical"]
    title: str = Field(min_length=1, max_length=300)
    recommended_action: str | None = Field(default=None, max_length=1000)
    create_work_order: bool = False


class _RuleContent(BaseModel):
    rule: Annotated[
        ThresholdRule | DivergenceRule | ShortCyclingRule | CorrelationRule | TrendProjectionRule,
        Field(discriminator="kind"),
    ]


def _validate_point_for_rule(connection: Connection, point_id: uuid.UUID) -> dict[str, Any]:
    point = get_point(connection, point_id)
    if point is None:
        raise ConfigInvalid("RULE_POINT_NOT_FOUND")
    if point["mapping_status"] != "validated":
        raise ConfigInvalid("RULE_POINT_NOT_VALIDATED")
    return point


def _validate_alarm_rule(connection: Connection, content: dict[str, Any]) -> dict[str, Any]:
    try:
        rule = _RuleContent(rule=content).rule
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in error["loc"][1:]) for error in exc.errors()})
        raise ConfigInvalid("RULE_CONTENT_INVALID", fields=fields) from exc

    if isinstance(rule, CorrelationRule):
        if rule.heating_point_id == rule.cooling_point_id:
            raise ConfigInvalid("RULE_CORRELATION_SAME_POINT")
        heating_point = _validate_point_for_rule(connection, rule.heating_point_id)
        cooling_point = _validate_point_for_rule(connection, rule.cooling_point_id)
        if heating_point["value_type"] != "number" or cooling_point["value_type"] != "number":
            raise ConfigInvalid("RULE_CORRELATION_REQUIRES_NUMBER")
        if heating_point["functional_location_id"] != cooling_point["functional_location_id"]:
            raise ConfigInvalid("RULE_CORRELATION_DIFFERENT_EQUIPMENT")
        return rule.model_dump(mode="json", exclude_none=True)

    point = _validate_point_for_rule(connection, rule.point_id)
    if isinstance(rule, ThresholdRule) and point["value_type"] != "number":
        raise ConfigInvalid("RULE_THRESHOLD_REQUIRES_NUMBER")
    if isinstance(rule, ShortCyclingRule) and point["value_type"] != "boolean":
        raise ConfigInvalid("RULE_SHORT_CYCLING_REQUIRES_BOOLEAN")
    if isinstance(rule, TrendProjectionRule) and point["value_type"] != "number":
        raise ConfigInvalid("RULE_TREND_PROJECTION_REQUIRES_NUMBER")
    return rule.model_dump(mode="json", exclude_none=True)


register_config_type(
    ALARM_RULE, ALARM_RULE_SCHEMA, _validate_alarm_rule, requires_second_person=True
)


def simulate_rule(
    connection: Connection, *, content: dict[str, Any], sample_size: int = 200
) -> dict[str, Any]:
    """Simule une règle contre l'historique récent de son point, sans rien
    créer (aucun constat, aucune alarme, aucun ordre de travail) :
    « simulation préalable » (feature-benchmark-matrix.md, ligne « Gestion
    des changements »), pour évaluer une règle avant de l'activer. Réutilise
    `_evaluate()` tel quel : aucune nouvelle logique de règle, seulement une
    lecture. Pour une règle à deux points (CorrelationRule), l'historique
    rejoué est celui du point `heating_point_id` — un choix arbitraire de
    point « principal », la valeur de l'autre point restant toujours lue à
    l'instant de chaque mesure historique, comme en production."""
    from app.telemetry import list_measurements  # import tardif : évite un cycle avec ce module

    primary_point_id = content.get("point_id") or content["heating_point_id"]
    point = get_point(connection, uuid.UUID(primary_point_id))
    if point is None:
        raise ConfigInvalid("RULE_POINT_NOT_FOUND")

    measurements = list_measurements(connection, point_id=point["id"], limit=sample_size)
    breaches = []
    for measurement in measurements:
        evidence = _evaluate(
            connection, content, point, measurement["value"], measurement["measured_at"]
        )
        if evidence is not None:
            breaches.append(
                {
                    "measured_at": measurement["measured_at"],
                    "value": measurement["value"],
                    "evidence": evidence,
                }
            )
    return {
        "sample_size": len(measurements),
        "breach_count": len(breaches),
        # Bornée : cette réponse est une aide au diagnostic, pas un export.
        "breaches": breaches[:20],
    }


def _subject(point: dict[str, Any]) -> uuid.UUID:
    """Le constat porte sur l'équipement du point, à défaut son espace."""
    return point["functional_location_id"] or point["space_id"] or point["id"]


def _counterpart_value_now(
    connection: Connection, point_id: uuid.UUID, at: datetime
) -> tuple[dict[str, Any], float] | None:
    """Point et valeur actuelle d'un point, pour une règle qui en compare
    deux : `None` si le point n'a jamais été mesuré ou si son dernier relevé
    est trop ancien pour affirmer qu'il reflète l'instant `at` (même seuil de
    péremption que app/telemetry_overview.py) — jamais une simultanéité
    supposée faute de mieux (règle non négociable : aucune donnée inventée)."""
    point = get_point(connection, point_id)
    if point is None:
        return None
    latest = latest_usable_bulk(connection, [point_id], at).get(point_id)
    if latest is None:
        return None
    interval = point["expected_interval_seconds"]
    if interval and (at - latest["measured_at"]) > STALE_AFTER_INTERVALS * timedelta(
        seconds=interval
    ):
        return None
    return point, latest["value"]


def _evaluate_simultaneous_heating_cooling(
    connection: Connection, rule: dict[str, Any], point: dict[str, Any], value: float, at: datetime
) -> dict[str, Any] | None:
    is_heating = str(point["id"]) == rule["heating_point_id"]
    other_id = uuid.UUID(rule["cooling_point_id"] if is_heating else rule["heating_point_id"])
    other = _counterpart_value_now(connection, other_id, at)
    if other is None:
        return None
    other_point, other_value = other

    heating_value = value if is_heating else other_value
    cooling_value = other_value if is_heating else value
    if heating_value <= rule["heating_threshold"] or cooling_value <= rule["cooling_threshold"]:
        return None
    return {
        "heating_point_code": point["code"] if is_heating else other_point["code"],
        "heating_value": heating_value,
        "cooling_point_code": other_point["code"] if is_heating else point["code"],
        "cooling_value": cooling_value,
    }


def _evaluate_short_cycling(
    connection: Connection, rule: dict[str, Any], point: dict[str, Any], value: float, at: datetime
) -> dict[str, Any] | None:
    """Compte les démarrages (transitions arrêt → marche) sur la fenêtre
    glissante `window_minutes` qui se termine à `at`, évalué à chaque relevé
    (à l'arrêt comme en marche) — jamais seulement au moment d'un démarrage :
    le constat doit rester actif tant que la fenêtre contient trop de
    démarrages, pas seulement l'instant du dernier, sans quoi il
    apparaîtrait et disparaîtrait à chaque arrêt puis redémarrage. L'état
    (marche/arrêt) juste avant le début de la fenêtre sert d'amorce, pour ne
    jamais compter comme un « démarrage » un équipement déjà en marche avant
    que la fenêtre ne commence."""
    from app.telemetry import list_measurements  # import tardif : évite un cycle avec ce module

    window_start = at - timedelta(minutes=rule["window_minutes"])
    seed = connection.execute(
        text(
            "SELECT value FROM measurements WHERE point_id = :point_id "
            "AND measured_at < :window_start ORDER BY measured_at DESC LIMIT 1"
        ),
        {"point_id": point["id"], "window_start": window_start},
    ).scalar()
    history = sorted(
        list_measurements(connection, point_id=point["id"], since=window_start, limit=1000),
        key=lambda row: row["measured_at"],
    )
    start_count = 0
    running = seed == 1
    for row in history:
        is_on = row["value"] == 1
        if is_on and not running:
            start_count += 1
        running = is_on

    if start_count <= rule["max_starts"]:
        return None
    return {
        "start_count": start_count,
        "window_minutes": rule["window_minutes"],
        "max_starts": rule["max_starts"],
    }


def _evaluate_trend_projection(
    connection: Connection, rule: dict[str, Any], point: dict[str, Any], value: float, at: datetime
) -> dict[str, Any] | None:
    """Projection linéaire déterministe (deux points : le début de la fenêtre
    `window_minutes` et le relevé courant), jamais une régression statistique
    complète — une sécante simple reste explicable, comme le reste du FDD de
    ce module. Jamais déclenchée si le seuil est déjà franchi maintenant (ce
    cas relève de `ThresholdRule`, qui constate, pas de cette règle, qui
    prédit) ni sans assez d'historique dans la fenêtre pour estimer une
    tendance (jamais une pente inventée à partir d'un seul point)."""
    already_breached = (
        value > rule["threshold"] if rule["operator"] == ">" else value < rule["threshold"]
    )
    if already_breached:
        return None

    from app.telemetry import list_measurements  # import tardif : évite un cycle avec ce module

    window_start = at - timedelta(minutes=rule["window_minutes"])
    history = list_measurements(connection, point_id=point["id"], since=window_start, limit=1000)
    earliest = min(history, key=lambda row: row["measured_at"], default=None)
    if earliest is None or earliest["measured_at"] >= at:
        return None

    elapsed_minutes = (at - earliest["measured_at"]).total_seconds() / 60
    slope_per_minute = (value - earliest["value"]) / elapsed_minutes

    moving_toward_threshold = (
        slope_per_minute > 0 if rule["operator"] == ">" else slope_per_minute < 0
    )
    if not moving_toward_threshold:
        return None

    projected_minutes = (rule["threshold"] - value) / slope_per_minute
    if projected_minutes < 0 or projected_minutes > rule["horizon_minutes"]:
        return None

    return {
        "current_value": value,
        "threshold": rule["threshold"],
        "operator": rule["operator"],
        # Arrondis pour l'affichage : une fausse précision (plusieurs
        # décimales) affirmerait plus que ce qu'une sécante à deux points
        # peut réellement garantir (ADR 013 — jamais plus que ce que le
        # système sait).
        "slope_per_minute": round(slope_per_minute, 4),
        "projected_minutes": round(projected_minutes),
        "window_minutes": rule["window_minutes"],
        "horizon_minutes": rule["horizon_minutes"],
    }


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

    if rule["kind"] == "simultaneous_heating_cooling":
        return _evaluate_simultaneous_heating_cooling(connection, rule, point, value, at)

    if rule["kind"] == "short_cycling":
        return _evaluate_short_cycling(connection, rule, point, value, at)

    if rule["kind"] == "trend_projection":
        return _evaluate_trend_projection(connection, rule, point, value, at)

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

    point_code = {"point_code": point["code"]}
    common = {"tenant_id": tenant_id, "changed_by": SYSTEM_ACTOR}

    blocking = [flag for flag in quality_flags if flag in _BLOCKING_FLAGS]
    for flag, reason_code in _BLOCKING_FLAGS.items():
        dedup_key = f"quality:{point['id']}:{flag}"
        if flag not in blocking:
            # Relevé propre : le problème de qualité est revenu à la normale.
            clear_finding_by_key(connection, dedup_key=dedup_key, **common)
            continue
        finding_id, _ = raise_or_repeat_finding(
            connection,
            dedup_key=dedup_key,
            subject_node_id=subject,
            point_id=point["id"],
            kind="data_quality",
            method="deterministic_rule",
            severity="warning",
            reason_code=reason_code,
            reason_params=point_code,
            evidence={**base_evidence, "flag": flag},
            seen_at=measured_at,
            **common,
        )
        touched.append(finding_id)
    if blocking:
        return touched

    # Trois appels plutôt qu'un : une règle à un point (`point_id`) ou une
    # règle à deux points (`heating_point_id`/`cooling_point_id`, voir
    # CorrelationRule) ne sont pas stockées sous la même clé — ce point peut
    # apparaître dans l'une ou l'autre des trois.
    rules = active_versions(
        connection, config_type=ALARM_RULE, content_filter={"point_id": str(point["id"])}
    )
    rules += active_versions(
        connection, config_type=ALARM_RULE, content_filter={"heating_point_id": str(point["id"])}
    )
    rules += active_versions(
        connection, config_type=ALARM_RULE, content_filter={"cooling_point_id": str(point["id"])}
    )
    if not rules:
        return touched

    trust = compute_trust(connection, point, measured_at)
    trust_key = f"quality:{point['id']}:low_trust"
    if trust["score"] < MIN_TRUST_FOR_RULES:
        finding_id, _ = raise_or_repeat_finding(
            connection,
            dedup_key=trust_key,
            subject_node_id=subject,
            point_id=point["id"],
            kind="data_quality",
            method="deterministic_rule",
            severity="warning",
            reason_code="DATA_QUALITY_LOW_TRUST",
            reason_params={**point_code, "score": trust["score"]},
            evidence={**base_evidence, "trust": trust},
            seen_at=measured_at,
            **common,
        )
        return touched + [finding_id]
    clear_finding_by_key(connection, dedup_key=trust_key, **common)

    for version in rules:
        rule = version["content"]
        dedup_key = f"rule:{ALARM_RULE}:{version['subject_key']}"
        evidence = _evaluate(connection, rule, point, value, measured_at)
        if evidence is None:
            # Règle respectée : retour à la normale du constat et de son alarme.
            clear_finding_by_key(connection, dedup_key=dedup_key, **common)
            continue
        finding_id, created = raise_or_repeat_finding(
            connection,
            dedup_key=dedup_key,
            subject_node_id=subject,
            point_id=point["id"],
            kind=_FINDING_KIND[rule["kind"]],
            method=_RULE_METHOD.get(rule["kind"], "deterministic_rule"),
            rule_config_version_id=version["id"],
            severity=rule["severity"],
            reason_code=_RULE_REASONS[rule["kind"]],
            reason_params={
                **point_code,
                **{k: v for k, v in evidence.items() if k != "desired_state_id"},
            },
            title=rule["title"],
            recommended_action=rule.get("recommended_action"),
            # Une règle instantanée compare, elle ne se trompe jamais sur ce
            # qu'elle observe : confiance totale. Une prédiction extrapole —
            # jamais une certitude affirmée à sa place (ADR 013).
            confidence=None if _FINDING_KIND[rule["kind"]] == "prediction" else 1.0,
            evidence={**base_evidence, **evidence, "trust_score": trust["score"]},
            seen_at=measured_at,
            **common,
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
            priority=WORK_ORDER_PRIORITY[rule["severity"]],
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
