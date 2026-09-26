"""Référence énergétique (Baseline) : une configuration versionnée de plus
(`config_type = "energy_baseline"`, ADR 012 §2.11) — réutilise l'audit,
l'activation, l'historique et le retour arrière déjà en place pour toute
configuration, aucun mécanisme nouveau à construire ni à tester.

Une fois activée, une référence est figée : ses paramètres (méthode,
période de référence, température de base) ne changent jamais après coup.
Un ajustement crée une nouvelle version (voir app/config_versions.py,
`create_version`/`activate_version`), l'ancienne restant lisible pour
toujours — condition pour pouvoir expliquer un résultat déjà calculé des
années plus tard.
"""

import uuid
from datetime import date
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.engine import Connection

from app.config_versions import ConfigInvalid, register_config_type
from app.energy.methods import is_known_method
from app.points import get_point

ENERGY_BASELINE = "energy_baseline"
ENERGY_BASELINE_SCHEMA = "energy_baseline/1"


class ReferencePeriod(BaseModel):
    model_config = {"extra": "forbid"}

    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.start >= self.end:
            raise ValueError("reference_period.start must be before reference_period.end")
        return self


class EnergyBaselineContent(BaseModel):
    model_config = {"extra": "forbid"}

    point_id: uuid.UUID
    method: str
    method_version: str
    reference_period: ReferencePeriod
    degree_day_base_temperature_celsius: float = Field(ge=-30, le=40)
    degree_day_kind: Literal["heating", "cooling"]


def _validate_energy_baseline(connection: Connection, content: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = EnergyBaselineContent(**content)
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise ConfigInvalid("ENERGY_BASELINE_CONTENT_INVALID", fields=fields) from exc
    if not is_known_method(parsed.method, parsed.method_version):
        raise ConfigInvalid(
            "ENERGY_BASELINE_METHOD_UNKNOWN", method=f"{parsed.method}/{parsed.method_version}"
        )
    point = get_point(connection, parsed.point_id)
    if point is None:
        raise ConfigInvalid("ENERGY_BASELINE_POINT_NOT_FOUND")
    if point["point_class"] != "energy_meter_reading":
        raise ConfigInvalid("ENERGY_BASELINE_POINT_NOT_ENERGY_METER")
    if point["mapping_status"] != "validated":
        raise ConfigInvalid("ENERGY_BASELINE_POINT_NOT_VALIDATED")
    return parsed.model_dump(mode="json")


register_config_type(ENERGY_BASELINE, ENERGY_BASELINE_SCHEMA, _validate_energy_baseline)
