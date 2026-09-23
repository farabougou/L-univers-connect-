"""Propriétés techniques datées d'un actif (ADR 012, section 2.3).

Exemples : fluide frigorigène et sa charge (obligation F-Gas), puissances
nominales, année de fabrication. Une propriété appartient à l'exemplaire
physique (c'est la plaque signalétique de la machine), pas à sa position.

Bitemporel et jamais réécrit : une nouvelle valeur clôt l'ancienne à sa date
d'effet (ex. recharge de fluide qui change la charge) ; l'historique permet de
savoir ce qui était vrai à n'importe quelle date. Les unités sont contrôlées
comme pour les points (codes UCUM, grandeur physique vérifiée).

Le calcul d'équivalent CO₂ (tonnes éq. CO₂) pour les documents F-Gas est
volontairement reporté : il exige une table officielle de PRG vérifiée, pas
des valeurs recopiées de mémoire.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import DomainError
from app.point_vocabulary import UNITS

PROPERTY_VOCABULARY_VERSION = "2026-09-23.1"

REFRIGERANTS = (
    "R22",
    "R32",
    "R134a",
    "R290",
    "R404A",
    "R407C",
    "R410A",
    "R452B",
    "R454B",
    "R454C",
    "R513A",
    "R717",
    "R744",
    "R1234yf",
    "R1234ze(E)",
)


@dataclass(frozen=True)
class PropertyDefinition:
    key: str
    label: str
    value_type: str  # number, text
    node_types: tuple[str, ...]
    quantity: str | None = None
    allowed_values: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None


_UNIT = ("physical_unit",)

PROPERTIES: dict[str, PropertyDefinition] = {
    d.key: d
    for d in (
        PropertyDefinition(
            "refrigerant_type", "Fluide frigorigène", "text", _UNIT, allowed_values=REFRIGERANTS
        ),
        PropertyDefinition(
            "refrigerant_charge", "Charge en fluide", "number", _UNIT, quantity="mass", minimum=0
        ),
        PropertyDefinition(
            "nominal_cooling_capacity",
            "Puissance frigorifique nominale",
            "number",
            _UNIT,
            quantity="power",
            minimum=0,
        ),
        PropertyDefinition(
            "nominal_heating_capacity",
            "Puissance calorifique nominale",
            "number",
            _UNIT,
            quantity="power",
            minimum=0,
        ),
        PropertyDefinition(
            "nominal_electrical_power",
            "Puissance électrique nominale",
            "number",
            _UNIT,
            quantity="power",
            minimum=0,
        ),
        PropertyDefinition(
            "manufacture_year",
            "Année de fabrication",
            "number",
            _UNIT,
            minimum=1900,
            maximum=2100,
        ),
    )
}

SOURCES = ("nameplate", "document", "measurement", "manual")


class PropertyError(DomainError, ValueError):
    pass


class PropertyNotFound(DomainError, LookupError):
    status = 404


def check_property(
    *, key: str, node_type: str, value: float | str, unit: str | None
) -> PropertyDefinition:
    definition = PROPERTIES.get(key)
    if definition is None:
        raise PropertyError("PROPERTY_UNKNOWN", key=key)
    if node_type not in definition.node_types:
        raise PropertyError("PROPERTY_NODE_TYPE_INVALID", key=key, node_type=node_type)

    if definition.value_type == "text":
        if not isinstance(value, str):
            raise PropertyError("PROPERTY_TEXT_EXPECTED", key=key)
        if unit is not None:
            raise PropertyError("PROPERTY_UNIT_NOT_ALLOWED", key=key)
        if definition.allowed_values and value not in definition.allowed_values:
            raise PropertyError("PROPERTY_VALUE_NOT_ALLOWED", key=key, value=value)
        return definition

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise PropertyError("PROPERTY_NUMBER_EXPECTED", key=key)
    if definition.minimum is not None and value < definition.minimum:
        raise PropertyError("PROPERTY_BELOW_MINIMUM", key=key, minimum=definition.minimum)
    if definition.maximum is not None and value > definition.maximum:
        raise PropertyError("PROPERTY_ABOVE_MAXIMUM", key=key, maximum=definition.maximum)
    if definition.quantity is None:
        if unit is not None:
            raise PropertyError("PROPERTY_UNIT_NOT_ALLOWED", key=key)
        return definition
    if unit is None:
        raise PropertyError("PROPERTY_UNIT_MISSING", key=key)
    if unit not in UNITS:
        raise PropertyError("UNIT_UNKNOWN", unit=unit)
    if UNITS[unit][1] != definition.quantity:
        raise PropertyError(
            "PROPERTY_UNIT_QUANTITY_MISMATCH", unit=unit, quantity=definition.quantity
        )
    return definition


_COLUMNS = (
    "id, node_id, property_key, value_number, value_text, unit, source, valid_from, valid_to, "
    "recorded_at, reason, created_by"
)


def set_property(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    node_id: uuid.UUID,
    key: str,
    value: float | str,
    unit: str | None,
    source: str,
    valid_from: datetime,
    reason: str,
    created_by: str,
) -> uuid.UUID:
    node_type = connection.execute(
        text("SELECT node_type FROM graph_nodes WHERE id = :id"), {"id": node_id}
    ).scalar()
    if node_type is None:
        raise PropertyNotFound("NODE_NOT_FOUND")
    if source not in SOURCES:
        raise PropertyError("PROPERTY_SOURCE_UNKNOWN", source=source)
    definition = check_property(key=key, node_type=node_type, value=value, unit=unit)

    current = (
        connection.execute(
            text(
                "SELECT id, valid_from FROM node_properties WHERE node_id = :node_id "
                "AND property_key = :key AND valid_to IS NULL"
            ),
            {"node_id": node_id, "key": key},
        )
        .mappings()
        .first()
    )
    if current is not None:
        if valid_from <= current["valid_from"]:
            raise PropertyError("PROPERTY_EFFECTIVE_DATE_NOT_LATER")
        connection.execute(
            text("UPDATE node_properties SET valid_to = :valid_to WHERE id = :id"),
            {"valid_to": valid_from, "id": current["id"]},
        )

    property_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO node_properties (id, tenant_id, node_id, property_key, value_number, "
            "value_text, unit, source, valid_from, reason, created_by) VALUES (:id, :tenant_id, "
            ":node_id, :key, :value_number, :value_text, :unit, :source, :valid_from, :reason, "
            ":created_by)"
        ),
        {
            "id": property_id,
            "tenant_id": tenant_id,
            "node_id": node_id,
            "key": key,
            "value_number": value if definition.value_type == "number" else None,
            "value_text": value if definition.value_type == "text" else None,
            "unit": unit,
            "source": source,
            "valid_from": valid_from,
            "reason": reason,
            "created_by": created_by,
        },
    )
    return property_id


def list_properties(
    connection: Connection, node_id: uuid.UUID, *, include_history: bool = False
) -> list[dict[str, Any]]:
    query = f"SELECT {_COLUMNS} FROM node_properties WHERE node_id = :node_id"
    if not include_history:
        query += " AND valid_to IS NULL"
    query += " ORDER BY property_key, valid_from"
    rows = connection.execute(text(query), {"node_id": node_id}).mappings()
    return [
        {
            **row,
            "value": row["value_number"] if row["value_number"] is not None else row["value_text"],
        }
        for row in rows
    ]
