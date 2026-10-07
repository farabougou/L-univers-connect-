"""Devineur sémantique BACnet → vocabulaire universel des points
(`app.point_vocabulary`), pour la découverte automatique BACnet V1
(directive de Mohamed, 27/09/2026 : « Semantic Discovery / Auto-Mapping »).

Aucune correspondance n'est jamais affirmée : seulement proposée, avec un
niveau de confiance et un code de raison stable (ADR 013 : jamais une
phrase générée stockée). Sans indice suffisant — ni unité BACnet connue,
ni mot-clé reconnu dans le nom — la proposition reste `point_class=None`,
`confidence=None` (NEEDS_REVIEW dans `app.bacnet_discovery`), jamais une
correspondance inventée pour « obtenir une démonstration impressionnante »
(consigne explicite de Mohamed).

Module pur, sans aucun appel réseau ni base de données : entièrement
UNIT_TESTED (voir tests/test_bacnet_semantics.py), séparément de la
découverte elle-même (SIMULATOR_TESTED) et de sa future validation terrain
(FIELD_TESTED) — distinction demandée explicitement par Mohamed.
"""

from dataclasses import dataclass

# BACnet (ASHRAE 135, EngineeringUnits) -> UCUM (app.point_vocabulary.UNITS).
# Seules les unités que nous savons vraiment interpréter ; toute autre
# unité BACnet reste non traduite (montrée en texte brut, jamais forcée
# dans un code UCUM incertain).
_BACNET_UNIT_TO_UCUM: dict[str, str] = {
    "degrees-celsius": "Cel",
    "degrees-kelvin": "K",
    "pascals": "Pa",
    "kilopascals": "kPa",
    "bars": "bar",
    "percent": "%",
    "percent-relative-humidity": "%",
    "watts": "W",
    "kilowatts": "kW",
    "kilowatt-hours": "kW.h",
    "parts-per-million": "[ppm]",
    "cubic-meters-per-hour": "m3/h",
    "kilograms": "kg",
}

_TEMPERATURE_UNITS = ("degrees-celsius", "degrees-kelvin")
_PRESSURE_UNITS = ("pascals", "kilopascals", "bars")
_POWER_UNITS = ("watts", "kilowatts")

_TEMPERATURE_KEYWORDS = ("temp", "température", "temperature", "t°", "tdep", "tamb", "tret")
_PRESSURE_KEYWORDS = ("pression", "pressure", "press")
_FAULT_KEYWORDS = ("defaut", "défaut", "fault", "alarme", "alarm", "panne")
_RUN_KEYWORDS = ("marche", "run", "fonctionnement")
_ENABLE_KEYWORDS = ("autorisation", "enable", "validation marche")
_SETPOINT_KEYWORDS = ("consigne", "setpoint", "sp ")


def map_bacnet_unit(bacnet_unit: str | None) -> str | None:
    """None si l'unité BACnet est absente ou non reconnue — jamais un code
    UCUM approximatif."""
    if bacnet_unit is None:
        return None
    return _BACNET_UNIT_TO_UCUM.get(bacnet_unit)


@dataclass(frozen=True)
class SemanticGuess:
    point_class: str | None
    unit: str | None
    confidence: float | None
    reason_code: str


def _matches(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def guess_point_class(
    *,
    object_type: str,
    value_type: str,
    units: str | None,
    object_name: str | None,
    description: str | None,
) -> SemanticGuess:
    """Propose une classe de point (`app.point_vocabulary.POINT_CLASSES`),
    jamais au-delà de ce que l'unité ou le nom permettent vraiment
    d'affirmer. Une unité BACnet présente et reconnue est toujours un
    signal plus fiable qu'un mot-clé dans un nom (confiance plus haute)."""
    unit = map_bacnet_unit(units)
    text = " ".join(filter(None, (object_name, description)))
    is_output_or_setpoint_named = object_type == "analog-output" or _matches(
        text, _SETPOINT_KEYWORDS
    )

    if value_type == "number":
        if units in _TEMPERATURE_UNITS:
            if is_output_or_setpoint_named:
                return SemanticGuess(
                    "temperature_setpoint", unit, 0.8, "BACNET_UNITS_TEMPERATURE_SETPOINT"
                )
            return SemanticGuess("temperature_sensor", unit, 0.9, "BACNET_UNITS_TEMPERATURE")
        if units in _PRESSURE_UNITS:
            return SemanticGuess("pressure_sensor", unit, 0.9, "BACNET_UNITS_PRESSURE")
        if units == "percent-relative-humidity":
            return SemanticGuess("humidity_sensor", unit, 0.9, "BACNET_UNITS_HUMIDITY")
        if units == "parts-per-million":
            return SemanticGuess("co2_sensor", unit, 0.85, "BACNET_UNITS_CONCENTRATION")
        if units in _POWER_UNITS:
            return SemanticGuess("electric_power_sensor", unit, 0.85, "BACNET_UNITS_POWER")
        if units == "kilowatt-hours":
            return SemanticGuess("energy_meter_reading", unit, 0.85, "BACNET_UNITS_ENERGY")

        # Pas d'unité utilisable : seul le nom peut encore donner un indice,
        # toujours avec une confiance plus faible qu'une unité connue.
        if _matches(text, _TEMPERATURE_KEYWORDS):
            point_class = (
                "temperature_setpoint" if is_output_or_setpoint_named else "temperature_sensor"
            )
            return SemanticGuess(point_class, unit, 0.5, "NAME_KEYWORD_TEMPERATURE")
        if _matches(text, _PRESSURE_KEYWORDS):
            return SemanticGuess("pressure_sensor", unit, 0.5, "NAME_KEYWORD_PRESSURE")
        return SemanticGuess(None, unit, None, "NO_RELIABLE_SIGNAL")

    if value_type == "boolean":
        if _matches(text, _FAULT_KEYWORDS):
            return SemanticGuess("fault_status", None, 0.8, "NAME_KEYWORD_FAULT")
        # Vérifié avant « marche » seul : « autorisation marche » est un
        # signal plus spécifique qu'un simple état de fonctionnement.
        if _matches(text, _ENABLE_KEYWORDS):
            return SemanticGuess("enable_status", None, 0.6, "NAME_KEYWORD_ENABLE")
        if object_type == "binary-output" and _matches(text, _RUN_KEYWORDS):
            return SemanticGuess("on_off_command", None, 0.5, "NAME_KEYWORD_COMMAND")
        if _matches(text, _RUN_KEYWORDS):
            return SemanticGuess("run_status", None, 0.7, "NAME_KEYWORD_RUN")
        return SemanticGuess(None, None, None, "NO_RELIABLE_SIGNAL")

    # multi-état : aucune classe de notre vocabulaire ne couvre encore un
    # mode multi-état générique (règle des trois, app.point_vocabulary :
    # pas de classe ajoutée sans cas réel) — toujours à revoir par une
    # personne, jamais une classe inventée pour ce type de valeur.
    return SemanticGuess(None, None, None, "MULTISTATE_NOT_YET_MAPPED")
