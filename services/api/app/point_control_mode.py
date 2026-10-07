"""Mode de point — manuel/automatique (V2, priorité « modes/consignes » de
la feuille de route : ... autorisation/policies → Dry Run/Shadow → ... →
planification → **modes/consignes** → automatisation).

Un point commandable reste en mode `manual` tant que personne ne l'a
explicitement basculé en `automatic` — c'est le verrou qui permet à
l'automatisation (app.automation_rules) d'exister sans jamais s'activer
par défaut sur un point. Un point sans mode jamais activé est `manual`
(valeur par défaut de `get_control_mode`, jamais stockée tant que personne
ne l'a choisie) : l'absence de configuration n'ouvre jamais la porte,
contrairement à `app.command_policies` où l'absence de policy laisse
passer (les deux mécanismes ont des rôles différents — l'un restreint des
points déjà ouverts aux commandes humaines, l'autre ouvre la porte à des
commandes sans humain, et un défaut permissif n'aurait pas le même sens).

Basculer un point en `automatic` exige une deuxième personne
(`requires_second_person`, même mécanisme que `alarm_rule`) : c'est le
moment où une commande peut partir sans clic humain direct sur CE point,
jamais un réglage anodin décidé seul.

Un mode n'autorise rien à lui seul : il s'ajoute à la commandabilité
(`app.commands._assert_point_is_commandable`, règle non négociable 1) et à
la policy active du point (`app.command_policies`), jamais à la place de
l'une ou l'autre.
"""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config_versions import ConfigInvalid, register_config_type

POINT_CONTROL_MODE = "point_control_mode"
POINT_CONTROL_MODE_SCHEMA = "point_control_mode/1"


class PointControlModeContent(BaseModel):
    model_config = {"extra": "forbid"}

    mode: Literal["manual", "automatic"]


def _validate_point_control_mode(
    connection: Connection, content: dict[str, Any]
) -> dict[str, Any]:
    try:
        parsed = PointControlModeContent(**content)
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise ConfigInvalid("POINT_CONTROL_MODE_CONTENT_INVALID", fields=fields) from exc
    return parsed.model_dump(mode="json")


register_config_type(
    POINT_CONTROL_MODE, POINT_CONTROL_MODE_SCHEMA, _validate_point_control_mode,
    requires_second_person=True,
)


def get_control_mode(connection: Connection, point_id: uuid.UUID) -> Literal["manual", "automatic"]:
    """`manual` tant qu'aucune version n'a jamais été activée pour ce point —
    jamais `automatic` par défaut."""
    row = connection.execute(
        text(
            "SELECT content FROM config_versions WHERE config_type = :type "
            "AND subject_key = :point_id AND status = 'active'"
        ),
        {"type": POINT_CONTROL_MODE, "point_id": str(point_id)},
    ).scalar()
    return dict(row)["mode"] if row else "manual"
