"""Catalogue des connecteurs (ADR 012 §2.12 : contrat du SDK de connecteur,
différé au F1 — « DEFER (M3), contrat fixé maintenant » — repris ici en V4,
« Connector SDK stable / modèle de connecteurs extensible / versioning /
lifecycle / catalogue / compatibilité » : rendre explicite et consultable
ce qui existait déjà en code et en docstrings, jamais une réécriture des
quatre connecteurs existants (Modbus, BACnet, OPC UA, MQTT) ni un nouveau
moteur.

Manifeste déclaratif par connecteur, jamais déduit dynamiquement du code :
protocole, capacités réellement implémentées, niveau de certification
(Experimental → Verified → Certified, ADR 012 §2.12). Dire qu'un
connecteur « déclare » une capacité ne la lui donne pas — ce module décrit
ce qui existe déjà dans app/connectors/{modbus,bacnet,opcua,mqtt}.py,
jamais l'inverse.

Écriture toujours désactivée (`write_enabled` fige à `False` partout,
règle non négociable 1) : aucun connecteur ne peut se déclarer capable
d'écrire depuis ce catalogue — l'activer exigerait une nouvelle décision
explicite de Mohamed, écrite dans CLAUDE.md, jamais une simple modification
de ce fichier.

« Verified » signifie ici : une suite de tests automatisés contre le
protocole réel (un serveur/courtier réel, jamais un simple mock) avec
injection de pannes (hôte injoignable, identifiant inconnu, valeur
invalide) — jamais contre un équipement physique réel, ce qui resterait
`DEFERRED_PHYSICAL_VALIDATION` jusqu'à un essai terrain. « Certified »
(ADR 012 §2.12) exigerait cet essai terrain et ne peut donc être déclaré
pour aucun connecteur aujourd'hui.
"""

from typing import Any, Literal, TypedDict

from sqlalchemy.engine import Connection

from app.config_versions import list_versions

ConnectorCapability = Literal["read", "discover", "subscribe"]
CertificationLevel = Literal["experimental", "verified", "certified"]


class ConnectorManifest(TypedDict):
    protocol: str
    display_name: str
    schema_version: str
    capabilities: list[ConnectorCapability]
    write_enabled: Literal[False]
    certification_level: CertificationLevel
    certification_basis: str
    module: str
    daemon_script: str
    device_mapping_config_type: str


CONNECTOR_CATALOG: dict[str, ConnectorManifest] = {
    "modbus": {
        "protocol": "modbus",
        "display_name": "Modbus TCP",
        "schema_version": "1",
        "capabilities": ["read"],
        "write_enabled": False,
        "certification_level": "verified",
        "certification_basis": (
            "tests/test_modbus_connector.py : précision flottante, facteur "
            "d'échelle, hôte injoignable — contre un serveur Modbus réel "
            "(pymodbus), jamais un équipement physique."
        ),
        "module": "app.connectors.modbus",
        "daemon_script": "scripts/modbus_daemon.py",
        "device_mapping_config_type": "modbus_device_mapping",
    },
    "bacnet": {
        "protocol": "bacnet",
        "display_name": "BACnet/IP",
        "schema_version": "1",
        "capabilities": ["read", "discover"],
        "write_enabled": False,
        "certification_level": "verified",
        "certification_basis": (
            "tests/test_bacnet_connector.py : hôte injoignable, objet "
            "inconnu — contre une pile BACnet réelle (bacpypes3), jamais "
            "un équipement physique. Découverte (Who-Is) vérifiée "
            "séparément (tests/test_bacnet_discovery*.py)."
        ),
        "module": "app.connectors.bacnet",
        "daemon_script": "scripts/bacnet_daemon.py",
        "device_mapping_config_type": "bacnet_device_mapping",
    },
    "opcua": {
        "protocol": "opcua",
        "display_name": "OPC UA",
        "schema_version": "1",
        "capabilities": ["read"],
        "write_enabled": False,
        "certification_level": "verified",
        "certification_basis": (
            "tests/test_opcua_connector.py : serveur injoignable, NodeId "
            "inconnu ou invalide — contre un serveur OPC UA réel (asyncua), "
            "jamais un équipement physique."
        ),
        "module": "app.connectors.opcua",
        "daemon_script": "scripts/opcua_daemon.py",
        "device_mapping_config_type": "opcua_device_mapping",
    },
    "mqtt": {
        "protocol": "mqtt",
        "display_name": "MQTT",
        "schema_version": "1",
        "capabilities": ["read", "subscribe"],
        "write_enabled": False,
        "certification_level": "verified",
        "certification_basis": (
            "tests/test_mqtt_connector.py : courtier injoignable, sujet "
            "jamais publié, valeur non numérique — contre un courtier MQTT "
            "réel, jamais un équipement physique."
        ),
        "module": "app.connectors.mqtt",
        "daemon_script": "scripts/mqtt_daemon.py",
        "device_mapping_config_type": "mqtt_device_mapping",
    },
}


def _active_mapping_count(connection: Connection, config_type: str) -> int:
    return sum(
        1
        for version in list_versions(connection, config_type=config_type)
        if version["status"] == "active"
    )


def list_connectors(connection: Connection) -> list[dict[str, Any]]:
    """Le catalogue, augmenté pour chaque connecteur du nombre
    d'équipements du tenant qui ont une connexion active de ce type —
    jamais une donnée statique seule : ce qui est réellement déployé,
    pas seulement ce qui est possible."""
    return [
        {
            **manifest,
            "active_equipment_count": _active_mapping_count(
                connection, manifest["device_mapping_config_type"]
            ),
        }
        for manifest in CONNECTOR_CATALOG.values()
    ]
