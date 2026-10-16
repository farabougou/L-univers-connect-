"""Moteur d'automatisation (règle → commande) — V2, dernière priorité de la
feuille de route (commande sécurisée → modes/consignes → autorisation/
policies → Dry Run/Shadow → exécution simulée → vérification → audit →
planification → **automatisation**).

Décision architecturale (documentée ici, pas devinée dans le code) : un
module séparé de `app/rules.py`, jamais une nouvelle branche dans ce
fichier. `app/rules.py` porte une invariante explicite depuis sa création
(ligne 48 de son docstring) : « aucune règle ne commande quoi que ce soit »
— garde-fou direct de la règle non négociable 1. Ajouter une capacité de
commande dans ce même module aurait affaibli une garantie de sûreté déjà
documentée et déjà relue, pour un bénéfice de réutilisation de code
minime (la structure d'une règle d'automatisation est volontairement plus
simple qu'une règle FDD). La séparation rend aussi cette capacité
entièrement désactivable (ne jamais importer ce module) sans toucher au
moteur de diagnostic existant.

Garde-fous appliqués dans cet ordre pour CHAQUE évaluation, aucun n'est
sautable ni contournable par configuration :
1. Fiabilité de la donnée déclenchante : la dernière mesure du point
   observé doit être exempte de tout drapeau de qualité ET le score de
   confiance du point (`app.trust.compute_trust`) doit atteindre
   `app.trust.MIN_TRUST_FOR_RULES` — plus strict que `app.rules` (qui ne
   bloque que sur deux drapeaux précis) : ce moteur déclenche une action,
   pas seulement une alerte qu'une personne filtre.
2. Mode du point CIBLE = `automatic` (`app.point_control_mode`) — `manual`
   par défaut, bascule à deux personnes. Un point en mode `manual` ignore
   silencieusement toute règle qui le cible (`blocked_manual_mode`),
   jamais une erreur bruyante pour un état attendu et volontaire.
3. Commandabilité du point cible (`app.commands.validate_command` →
   `_assert_point_is_commandable`) — jamais un équipement réel, exception
   strictement scopée à `simulated_relay` (règle non négociable 1,
   totalement inchangée ici).
4. Policy active du point cible (`app.command_policies`), évaluée avec le
   rôle pseudo `"automation"` — une policy qui ne liste pas ce rôle dans
   `allowed_roles` bloque l'automatisation sur ce point précis, même déjà
   en mode automatique (défense en profondeur, un deuxième verrou
   indépendant du premier).
5. Anti-emballement : pas plus d'un déclenchement par règle sur
   `_MIN_INTERVAL_BETWEEN_FIRINGS`, relu depuis le journal d'événements
   (`AUTOMATION_RULE_FIRED`) — jamais un compteur en mémoire qui
   s'oublierait au redémarrage du processus de balayage.

Déclenchement : balayage périodique (`app.automation_rules_sweep`), jamais
synchrone sur l'arrivée d'une mesure comme `app.rules`. Choix volontaire :
découple la capacité de commander automatiquement du chemin critique
d'ingestion de télémétrie (une panne de ce moteur ne doit jamais retarder
l'enregistrement d'une mesure), et le délai introduit (au pire, l'intervalle
du balayage) est sans conséquence pour ce qui peut être automatisé ici —
toujours un relais simulé, jamais un contrôle qui exigerait le temps réel.

Configuration versionnée (config_type = automation_rule), approbation à
deux personnes obligatoire (comme alarm_rule) : l'auteur d'une règle qui
PEUT déclencher une commande ne peut jamais être celui qui l'active.

Volontairement simple (règle des trois) : une seule condition (un point,
un opérateur, un seuil) déclenche une seule commande sur un seul point
cible. Pas de combinaison de conditions, pas de cascade de règles — un
vrai besoin le justifiera avant d'être construit.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.command_policies import PolicyViolation
from app.commands import CommandNotAllowed, create_command, validate_command
from app.config_versions import ConfigInvalid, active_versions, register_config_type
from app.events import list_events_for_subject, record_event
from app.point_control_mode import get_control_mode
from app.points import get_point
from app.telemetry import list_measurements
from app.trust import MIN_TRUST_FOR_RULES, compute_trust

AUTOMATION_RULE = "automation_rule"
AUTOMATION_RULE_SCHEMA = "automation_rule/1"

# Un déclenchement par règle au maximum sur cette fenêtre, quelle que soit
# la fréquence du balayage — anti-emballement (voir docstring du module).
_MIN_INTERVAL_BETWEEN_FIRINGS = timedelta(minutes=5)

_AUTOMATION_ACTOR_ROLE = "automation"


class AutomationRuleContent(BaseModel):
    model_config = {"extra": "forbid"}

    title: str
    trigger_point_id: uuid.UUID
    operator: Literal[">", "<"]
    threshold: float
    target_point_id: uuid.UUID
    requested_value: float


def _validate_automation_rule(connection: Connection, content: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = AutomationRuleContent(**content)
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise ConfigInvalid("AUTOMATION_RULE_CONTENT_INVALID", fields=fields) from exc
    return parsed.model_dump(mode="json")


register_config_type(
    AUTOMATION_RULE, AUTOMATION_RULE_SCHEMA, _validate_automation_rule,
    requires_second_person=True,
)


def _breaches(operator: str, value: float, threshold: float) -> bool:
    return value > threshold if operator == ">" else value < threshold


def _last_fired_at(connection: Connection, rule_id: uuid.UUID) -> datetime | None:
    for event in list_events_for_subject(
        connection, subject_type="automation_rule", subject_id=rule_id, limit=10
    ):
        if event["event_type"] == "AUTOMATION_RULE_FIRED":
            return event["occurred_at"]
    return None


def evaluate_automation_rules(
    connection: Connection, *, tenant_id: uuid.UUID, at: datetime | None = None
) -> list[dict[str, Any]]:
    """Évalue toutes les règles d'automatisation actives du tenant. Ne lève
    jamais d'exception pour une règle en échec : les suivantes sont quand
    même évaluées, chaque résultat porte son propre statut (voir les
    constantes `blocked_*`/`condition_not_met`/`cooldown`/`fired` ci-dessus
    dans le docstring du module)."""
    at = at or datetime.now(UTC)
    results: list[dict[str, Any]] = []
    for rule in active_versions(connection, config_type=AUTOMATION_RULE, content_filter={}):
        results.append(_evaluate_one(connection, tenant_id=tenant_id, rule=rule, at=at))
    return results


def _evaluate_one(
    connection: Connection, *, tenant_id: uuid.UUID, rule: dict[str, Any], at: datetime
) -> dict[str, Any]:
    rule_id = rule["id"]
    content = rule["content"]
    base = {"rule_id": rule_id, "title": content["title"]}
    # Le contenu JSONB renvoie des identifiants en texte : reconvertis en
    # uuid.UUID une fois ici, jamais comparés tels quels (une chaîne et un
    # uuid.UUID ne sont jamais égaux en Python, même de même valeur).
    trigger_point_id = uuid.UUID(content["trigger_point_id"])
    target_point_id = uuid.UUID(content["target_point_id"])

    last_fired = _last_fired_at(connection, rule_id)
    if last_fired is not None and at - last_fired < _MIN_INTERVAL_BETWEEN_FIRINGS:
        return {**base, "status": "cooldown"}

    trigger_point = get_point(connection, trigger_point_id)
    if trigger_point is None:
        return {**base, "status": "blocked_trigger_point_missing"}

    recent = list_measurements(connection, point_id=trigger_point["id"], limit=1)
    if not recent:
        return {**base, "status": "no_data"}
    latest = recent[0]
    if latest["quality_flags"]:
        return {**base, "status": "blocked_untrusted_data", "detail": "quality_flag"}
    trust = compute_trust(connection, trigger_point, at)
    if trust["score"] < MIN_TRUST_FOR_RULES:
        return {**base, "status": "blocked_untrusted_data", "detail": f"trust={trust['score']}"}

    if not _breaches(content["operator"], latest["value"], content["threshold"]):
        return {**base, "status": "condition_not_met"}

    if get_control_mode(connection, target_point_id) != "automatic":
        return {**base, "status": "blocked_manual_mode"}

    requested_value = content["requested_value"]
    actor = f"automation:{rule_id}"
    try:
        validate_command(
            connection,
            point_id=target_point_id,
            requested_value=requested_value,
            requester_roles=[_AUTOMATION_ACTOR_ROLE],
        )
    except (CommandNotAllowed, PolicyViolation) as exc:
        record_event(
            connection,
            tenant_id=tenant_id,
            event_type="AUTOMATION_RULE_BLOCKED",
            subject_type="automation_rule",
            subject_id=rule_id,
            payload={"reason": exc.code},
            occurred_at=at,
        )
        return {**base, "status": "blocked", "detail": exc.code}

    command_id = create_command(
        connection,
        tenant_id=tenant_id,
        point_id=target_point_id,
        requested_value=requested_value,
        requested_by=actor,
        requester_roles=[_AUTOMATION_ACTOR_ROLE],
        at=at,
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=actor,
        action="command.created",
        entity_type="command",
        entity_id=str(command_id),
        payload={
            "point_id": str(target_point_id),
            "requested_value": requested_value,
            "automation_rule_id": str(rule_id),
            "trigger_value": latest["value"],
        },
    )
    record_event(
        connection,
        tenant_id=tenant_id,
        event_type="AUTOMATION_RULE_FIRED",
        subject_type="automation_rule",
        subject_id=rule_id,
        payload={"command_id": str(command_id), "trigger_value": latest["value"]},
        occurred_at=at,
    )
    return {**base, "status": "fired", "command_id": command_id}
