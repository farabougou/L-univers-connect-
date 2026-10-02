"""Command Policy Engine — autorisation/policies (V2, 02/10/2026, priorité 3
de la feuille de route : commande sécurisée → modes/consignes →
**autorisation/policies** → Dry Run/Shadow → ...).

Au-delà des rôles Keycloak globaux (`_COMMAND_ROLES`, identiques pour tout
le tenant), une policy restreint, pour un point commandable précis, quels
rôles et quelles valeurs sont acceptés. Une policy est une configuration
versionnée de plus (`config_type = command_point_policy`, `subject_key =
point_id`) : même mécanisme que `app.economics` et `app.energy.baseline` —
`app.config_versions` gère déjà création, activation, historique et retour
arrière, aucun nouvel endpoint, les routes génériques `/configs` suffisent.

Une policy ne peut que RESTREINDRE davantage un point déjà commandable,
jamais l'étendre à un point non simulé : la commandabilité elle-même
(`app.commands._assert_point_is_commandable`, règle non négociable 1,
exception scopée à `simulated_relay`) reste vérifiée avant toute policy et
n'est jamais affaiblie par ce module. Absence de policy active pour un
point = comportement inchangé (tous les rôles globaux acceptés, toute
valeur acceptée) : une policy est un renforcement optionnel, jamais une
condition bloquante par défaut.
"""

import uuid
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config_versions import ConfigInvalid, register_config_type
from app.errors import DomainError

COMMAND_POINT_POLICY = "command_point_policy"
COMMAND_POINT_POLICY_SCHEMA = "command_point_policy/1"

# Les mêmes rôles que _COMMAND_ROLES (app/routers/commands.py) : une policy
# ne peut citer qu'un sous-ensemble de ces rôles, jamais un rôle inconnu.
COMMAND_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


class PolicyViolation(DomainError, ValueError):
    status = 403


class CommandPointPolicyContent(BaseModel):
    model_config = {"extra": "forbid"}

    # Sous-ensemble des rôles globaux autorisés à commander ce point précis ;
    # None = aucune restriction de rôle au-delà de _COMMAND_ROLES.
    allowed_roles: list[str] | None = Field(default=None, min_length=1)
    # Valeurs acceptées pour ce point ; None = aucune restriction de valeur.
    allowed_values: list[float] | None = Field(default=None, min_length=1)


def _validate_command_point_policy(
    connection: Connection, content: dict[str, Any]
) -> dict[str, Any]:
    try:
        parsed = CommandPointPolicyContent(**content)
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise ConfigInvalid("COMMAND_POINT_POLICY_CONTENT_INVALID", fields=fields) from exc
    if parsed.allowed_roles is not None:
        unknown = sorted(set(parsed.allowed_roles) - set(COMMAND_ROLES))
        if unknown:
            raise ConfigInvalid(
                "COMMAND_POINT_POLICY_UNKNOWN_ROLE", roles=", ".join(unknown)
            )
    return parsed.model_dump(mode="json")


register_config_type(
    COMMAND_POINT_POLICY, COMMAND_POINT_POLICY_SCHEMA, _validate_command_point_policy
)


def get_active_policy(connection: Connection, point_id: uuid.UUID) -> dict[str, Any] | None:
    """Policy active du point, ou None si aucune n'a jamais été activée —
    une commande reste alors soumise aux seuls rôles globaux (comportement
    inchangé), jamais bloquée par défaut faute de policy."""
    row = connection.execute(
        text(
            "SELECT content FROM config_versions WHERE config_type = :type "
            "AND subject_key = :point_id AND status = 'active'"
        ),
        {"type": COMMAND_POINT_POLICY, "point_id": str(point_id)},
    ).scalar()
    return dict(row) if row else None


def enforce_policy(
    policy: dict[str, Any] | None, *, requested_value: float, roles: list[str]
) -> None:
    """Lève PolicyViolation si la policy active du point refuse la commande
    demandée. Aucune policy active = rien à vérifier ici (voir get_active_policy)."""
    if policy is None:
        return
    allowed_roles = policy.get("allowed_roles")
    if allowed_roles is not None and not set(roles) & set(allowed_roles):
        raise PolicyViolation(
            "COMMAND_POLICY_ROLE_NOT_ALLOWED", allowed_roles=", ".join(allowed_roles)
        )
    allowed_values = policy.get("allowed_values")
    if allowed_values is not None and requested_value not in allowed_values:
        raise PolicyViolation(
            "COMMAND_POLICY_VALUE_NOT_ALLOWED",
            allowed_values=", ".join(str(value) for value in allowed_values),
        )
