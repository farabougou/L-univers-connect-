"""Connexion Modbus d'un équipement, en configuration versionnée (ADR 012
§2.11-2.12) : sujet = l'équipement (functional_location_id).

Avant ce module, l'adresse de l'appareil et l'association point ↔ registre
n'existaient qu'en arguments de ligne de commande, tapés à la main à chaque
lancement — inutilisable en dehors du développement. Le même mécanisme que
les règles de détection (app/rules.py) s'applique ici : brouillon → actif →
retiré, une nouvelle version à chaque changement, rien écrasé.

Le device_type choisit son catalogue de registres (DEVICE_REGISTER_CATALOGS) :
rien n'est câblé en dur pour un fabricant précis dans la validation
elle-même (règle non négociable 8).
"""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.engine import Connection

from app.config_versions import ConfigInvalid, list_versions, register_config_type
from app.connectors.ingest import PointModbusMapping
from app.connectors.modbus import find_register_by_name
from app.connectors.sdm120 import SDM120_POINTS
from app.connectors.simulated_relay import SIMULATED_RELAY_POINTS
from app.points import get_point

MODBUS_DEVICE_MAPPING = "modbus_device_mapping"
MODBUS_DEVICE_MAPPING_SCHEMA = "modbus_device_mapping/1"

DEVICE_REGISTER_CATALOGS = {"sdm120": SDM120_POINTS, "simulated_relay": SIMULATED_RELAY_POINTS}

# Les seuls device_type autorisés à recevoir une commande (app/commands.py) :
# jamais le sdm120, jamais un futur type qui représenterait un vrai appareil
# (CLAUDE.md, exception à la règle non négociable 1).
SIMULATED_DEVICE_TYPES = frozenset({"simulated_relay"})


class PointMapping(BaseModel):
    model_config = {"extra": "forbid"}

    point_id: uuid.UUID
    # Pas "register" : ce nom est déjà pris par BaseModel (avertissement Pydantic).
    register_name: str = Field(min_length=1)


class ModbusDeviceMappingContent(BaseModel):
    model_config = {"extra": "forbid"}

    device_type: Literal["sdm120", "simulated_relay"]
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=502, ge=1, le=65535)
    points: list[PointMapping] = Field(min_length=1)


def _validate_modbus_device_mapping(
    connection: Connection, content: dict[str, Any]
) -> dict[str, Any]:
    try:
        mapping = ModbusDeviceMappingContent(**content)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in error["loc"]) for error in exc.errors()})
        raise ConfigInvalid("MODBUS_MAPPING_CONTENT_INVALID", fields=fields) from exc

    known_registers = {point.name for point in DEVICE_REGISTER_CATALOGS[mapping.device_type]}
    seen_registers: set[str] = set()
    seen_points: set[uuid.UUID] = set()
    for entry in mapping.points:
        if entry.register_name not in known_registers:
            raise ConfigInvalid("MODBUS_REGISTER_UNKNOWN", register=entry.register_name)
        if entry.register_name in seen_registers:
            raise ConfigInvalid("MODBUS_REGISTER_DUPLICATED", register=entry.register_name)
        seen_registers.add(entry.register_name)
        if entry.point_id in seen_points:
            raise ConfigInvalid("MODBUS_POINT_DUPLICATED", point_id=str(entry.point_id))
        seen_points.add(entry.point_id)

        point = get_point(connection, entry.point_id)
        if point is None:
            raise ConfigInvalid("MODBUS_POINT_NOT_FOUND", point_id=str(entry.point_id))
        if point["mapping_status"] != "validated":
            raise ConfigInvalid("MODBUS_POINT_NOT_VALIDATED", point_id=str(entry.point_id))

    return mapping.model_dump(mode="json")


register_config_type(
    MODBUS_DEVICE_MAPPING, MODBUS_DEVICE_MAPPING_SCHEMA, _validate_modbus_device_mapping
)


BACNET_DEVICE_MAPPING = "bacnet_device_mapping"
BACNET_DEVICE_MAPPING_SCHEMA = "bacnet_device_mapping/1"


class BacnetPointMapping(BaseModel):
    model_config = {"extra": "forbid"}

    point_id: uuid.UUID
    object_type: str = Field(min_length=1)
    object_instance: int = Field(ge=0)
    property_identifier: str = Field(default="present-value", min_length=1)


class BacnetDeviceMappingContent(BaseModel):
    """Contrairement à Modbus, aucun `device_type` ici : BACnet normalise
    déjà l'adressage d'un point (type d'objet + instance + propriété), donc
    aucun catalogue de registres propre à un fabricant n'est nécessaire — la
    carte de points est directement le contenu de cette configuration."""

    model_config = {"extra": "forbid"}

    address: str = Field(min_length=1, max_length=255)
    points: list[BacnetPointMapping] = Field(min_length=1)


def _validate_bacnet_device_mapping(
    connection: Connection, content: dict[str, Any]
) -> dict[str, Any]:
    try:
        mapping = BacnetDeviceMappingContent(**content)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in error["loc"]) for error in exc.errors()})
        raise ConfigInvalid("BACNET_MAPPING_CONTENT_INVALID", fields=fields) from exc

    seen_objects: set[tuple[str, int, str]] = set()
    seen_points: set[uuid.UUID] = set()
    for entry in mapping.points:
        object_key = (entry.object_type, entry.object_instance, entry.property_identifier)
        if object_key in seen_objects:
            raise ConfigInvalid(
                "BACNET_OBJECT_DUPLICATED",
                object_type=entry.object_type,
                object_instance=entry.object_instance,
            )
        seen_objects.add(object_key)
        if entry.point_id in seen_points:
            raise ConfigInvalid("BACNET_POINT_DUPLICATED", point_id=str(entry.point_id))
        seen_points.add(entry.point_id)

        point = get_point(connection, entry.point_id)
        if point is None:
            raise ConfigInvalid("BACNET_POINT_NOT_FOUND", point_id=str(entry.point_id))
        if point["mapping_status"] != "validated":
            raise ConfigInvalid("BACNET_POINT_NOT_VALIDATED", point_id=str(entry.point_id))

    return mapping.model_dump(mode="json")


register_config_type(
    BACNET_DEVICE_MAPPING, BACNET_DEVICE_MAPPING_SCHEMA, _validate_bacnet_device_mapping
)


def get_active_bacnet_mapping(
    connection: Connection, *, equipment_id: uuid.UUID
) -> dict[str, Any] | None:
    """Le contenu de la version active pour cet équipement, ou None (aucune
    connexion BACnet configurée, ou seulement un brouillon)."""
    for version in list_versions(
        connection, config_type=BACNET_DEVICE_MAPPING, subject_key=str(equipment_id)
    ):
        if version["status"] == "active":
            return version["content"]
    return None


def get_active_mapping(connection: Connection, *, equipment_id: uuid.UUID) -> dict[str, Any] | None:
    """Le contenu de la version active pour cet équipement, ou None (aucune
    connexion Modbus configurée, ou seulement un brouillon)."""
    for version in list_versions(
        connection, config_type=MODBUS_DEVICE_MAPPING, subject_key=str(equipment_id)
    ):
        if version["status"] == "active":
            return version["content"]
    return None


def resolve_active_mapping(
    connection: Connection, *, equipment_id: uuid.UUID
) -> tuple[str, int, list[PointModbusMapping]] | None:
    """Connexion et points prêts pour app.connectors.modbus, à partir de la
    version active. None si aucune n'est active (voir get_active_mapping)."""
    content = get_active_mapping(connection, equipment_id=equipment_id)
    if content is None:
        return None
    catalog = DEVICE_REGISTER_CATALOGS[content["device_type"]]
    mappings = [
        PointModbusMapping(
            point_id=uuid.UUID(entry["point_id"]),
            register=find_register_by_name(catalog, entry["register_name"]),
        )
        for entry in content["points"]
    ]
    return content["host"], content["port"], mappings
