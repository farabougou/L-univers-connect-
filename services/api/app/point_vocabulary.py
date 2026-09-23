"""Vocabulaire des points de télémétrie et des unités (ADR 012, section 2.7).

- Unités stockées en codes UCUM (norme d'écriture des unités, utilisée aussi
  par QUDT/Brick), avec leur grandeur physique : une sonde de température ne
  peut pas être déclarée en bar.
- Classes de points alignées sur Brick Schema (correspondance indiquée),
  limitées aux besoins réels du wedge CVC : on en ajoute avec un cas réel,
  jamais « au cas où ».

Texte contrôlé côté application : ajouter une classe ou une unité ne demande
pas de migration, seulement une nouvelle version de ce fichier.
"""

import math
from dataclasses import dataclass

from app.errors import DomainError

POINT_VOCABULARY_VERSION = "2026-09-23.1"

VALUE_TYPES = ("number", "boolean", "multistate")

# Code UCUM → (symbole affiché, grandeur physique).
UNITS: dict[str, tuple[str, str]] = {
    "Cel": ("°C", "temperature"),
    "K": ("K", "temperature"),
    "Pa": ("Pa", "pressure"),
    "kPa": ("kPa", "pressure"),
    "bar": ("bar", "pressure"),
    "%": ("%", "ratio"),
    "W": ("W", "power"),
    "kW": ("kW", "power"),
    "kW.h": ("kWh", "energy"),
    "[ppm]": ("ppm", "concentration"),
    "m3/h": ("m³/h", "volume_flow"),
    "kg": ("kg", "mass"),
}


@dataclass(frozen=True)
class PointClass:
    name: str
    kind: str  # sensor, setpoint, command, status, alarm, meter
    value_type: str
    quantity: str | None
    brick: str | None = None


POINT_CLASSES: dict[str, PointClass] = {
    c.name: c
    for c in (
        PointClass(
            "temperature_sensor", "sensor", "number", "temperature", "brick:Temperature_Sensor"
        ),
        PointClass(
            "supply_water_temperature_sensor",
            "sensor",
            "number",
            "temperature",
            "brick:Supply_Water_Temperature_Sensor",
        ),
        PointClass(
            "return_water_temperature_sensor",
            "sensor",
            "number",
            "temperature",
            "brick:Return_Water_Temperature_Sensor",
        ),
        PointClass(
            "supply_air_temperature_sensor",
            "sensor",
            "number",
            "temperature",
            "brick:Supply_Air_Temperature_Sensor",
        ),
        PointClass("pressure_sensor", "sensor", "number", "pressure", "brick:Pressure_Sensor"),
        PointClass("humidity_sensor", "sensor", "number", "ratio", "brick:Humidity_Sensor"),
        PointClass("co2_sensor", "sensor", "number", "concentration", "brick:CO2_Sensor"),
        PointClass(
            "electric_power_sensor", "sensor", "number", "power", "brick:Electric_Power_Sensor"
        ),
        PointClass("energy_meter_reading", "meter", "number", "energy", "brick:Energy_Sensor"),
        PointClass("run_status", "status", "boolean", None, "brick:Run_Status"),
        PointClass("fault_status", "alarm", "boolean", None, "brick:Fault_Status"),
        PointClass(
            "temperature_setpoint",
            "setpoint",
            "number",
            "temperature",
            "brick:Temperature_Setpoint",
        ),
        # Déclarable pour documenter une installation, jamais inscriptible tant
        # que la règle non négociable 1 s'applique (contrainte en base).
        PointClass("on_off_command", "command", "boolean", None, "brick:On_Off_Command"),
    )
}


class PointVocabularyError(DomainError, ValueError):
    pass


def check_point_definition(
    *,
    point_class: str | None,
    value_type: str,
    unit: str | None,
    states: dict[str, str] | None,
) -> PointClass | None:
    """Vérifie la cohérence classe / type de valeur / unité / états.

    Un point sans classe est un point découvert mais pas encore identifié
    (mise en service) : il est accepté, mais ne pourra être validé qu'une fois
    sa classe connue (voir check_point_ready_for_validation).
    """
    if value_type not in VALUE_TYPES:
        raise PointVocabularyError("POINT_VALUE_TYPE_UNKNOWN", value_type=value_type)
    if unit is not None and unit not in UNITS:
        raise PointVocabularyError("UNIT_UNKNOWN", unit=unit)

    if value_type == "number":
        if states:
            raise PointVocabularyError("POINT_NUMBER_HAS_NO_STATES")
    else:
        if unit is not None:
            raise PointVocabularyError("POINT_UNIT_NOT_ALLOWED", value_type=value_type)
    if value_type == "multistate":
        if not states:
            raise PointVocabularyError("POINT_MULTISTATE_REQUIRES_STATES")
        if not all(key.lstrip("-").isdigit() for key in states):
            raise PointVocabularyError("POINT_STATE_CODES_NOT_INTEGER")
    elif value_type == "boolean" and states:
        raise PointVocabularyError("POINT_BOOLEAN_HAS_NO_STATES")

    if point_class is None:
        return None
    definition = POINT_CLASSES.get(point_class)
    if definition is None:
        raise PointVocabularyError("POINT_CLASS_UNKNOWN", point_class=point_class)
    if value_type != definition.value_type:
        raise PointVocabularyError(
            "POINT_CLASS_VALUE_TYPE_MISMATCH",
            point_class=point_class,
            expected=definition.value_type,
            value_type=value_type,
        )
    if definition.quantity is not None and unit is not None:
        unit_quantity = UNITS[unit][1]
        if unit_quantity != definition.quantity:
            raise PointVocabularyError(
                "UNIT_QUANTITY_MISMATCH",
                unit=unit,
                unit_quantity=unit_quantity,
                point_class=point_class,
                quantity=definition.quantity,
            )
    return definition


def check_point_ready_for_validation(
    *,
    point_class: str | None,
    value_type: str,
    unit: str | None,
    states: dict[str, str] | None,
    has_anchor: bool,
) -> None:
    """Un point n'est validé (considéré fiable) que complètement décrit :
    classe connue, unité pour un nombre, rattaché à un équipement ou un espace."""
    if point_class is None:
        raise PointVocabularyError("POINT_CLASS_MISSING")
    if value_type == "number" and unit is None:
        raise PointVocabularyError("POINT_UNIT_MISSING")
    if not has_anchor:
        raise PointVocabularyError("POINT_NOT_ANCHORED")
    check_point_definition(point_class=point_class, value_type=value_type, unit=unit, states=states)


def check_value(value: float, *, value_type: str, states: dict[str, str] | None) -> None:
    """Refuse une valeur impossible pour le type du point (jamais stockée)."""
    if not math.isfinite(value):
        raise PointVocabularyError("VALUE_NOT_FINITE")
    if value_type == "boolean" and value not in (0, 1):
        raise PointVocabularyError("VALUE_BOOLEAN_INVALID")
    if value_type == "multistate":
        if value != int(value) or str(int(value)) not in (states or {}):
            raise PointVocabularyError("VALUE_STATE_UNKNOWN", value=value)
