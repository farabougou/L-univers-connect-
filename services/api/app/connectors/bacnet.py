"""Connecteur BACnet/IP générique, en lecture seule (ADR 012 §2.12 : SDK de
connecteur).

Contrairement à Modbus, BACnet normalise déjà l'adressage d'un point (type
d'objet + instance + propriété) : aucun catalogue de registres propre à un
fabricant n'est nécessaire ici. La carte de points reste malgré tout donnée
en paramètre, jamais codée en dur (règle non négociable 8 : pas de
dépendance à un constructeur dans le noyau).

Lecture seule par construction (règle non négociable 1) : ce module ne
propose aucune fonction d'écriture de propriété.

Pont synchrone : la bibliothèque BACnet (bacpypes3) est asynchrone (sa
propre boucle d'événements réseau). Le reste du noyau (démon, ingestion)
reste synchrone comme pour Modbus ; chaque relève ouvre puis referme sa
propre boucle asyncio (`asyncio.run`), de la même façon qu'une connexion
Modbus s'ouvre et se referme à chaque relève — jamais de boucle asyncio
qui vivrait en arrière-plan du reste de l'application.
"""

import argparse
import asyncio
from dataclasses import dataclass
from typing import Any

from bacpypes3.apdu import ErrorRejectAbortNack
from bacpypes3.app import Application
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier, PropertyIdentifier

# Identifiant fournisseur "générique" (ASHRAE, 999) : celui que les outils
# bacpypes3 eux-mêmes utilisent par défaut pour un client qui n'annonce
# aucun matériel propre. Jamais utilisé pour un objet exposé au réseau
# (ce connecteur ne construit qu'une application cliente).
_GENERIC_VENDOR_ID = 999

# Seuls ces types d'objet BACnet sont considérés comme des « points » pour
# la découverte (BACnet V1, directive de Mohamed du 27/09/2026) : un point
# de mesure, de commande lue ou de mode, jamais un objet d'infrastructure du
# protocole (device, network-port, notification-class, calendar, schedule,
# trend-log…) — ceux-là ne sont d'ailleurs pas des points dans notre modèle.
_DISCOVERABLE_OBJECT_TYPES: dict[str, str] = {
    "analog-input": "number",
    "analog-output": "number",
    "analog-value": "number",
    "binary-input": "boolean",
    "binary-output": "boolean",
    "binary-value": "boolean",
    "multi-state-input": "multistate",
    "multi-state-output": "multistate",
    "multi-state-value": "multistate",
}


class BacnetReadError(Exception):
    """Échec de lecture d'un point BACnet (réseau, appareil, objet, délai
    dépassé)."""


@dataclass(frozen=True)
class BacnetPoint:
    """Un point mesuré, décrit par son adressage BACnet natif."""

    name: str
    object_type: str
    object_instance: int
    unit: str
    property_identifier: str = "present-value"


def find_object_by_name(points: list[BacnetPoint], name: str) -> BacnetPoint:
    for point in points:
        if point.name == name:
            return point
    known = ", ".join(point.name for point in points)
    raise ValueError(f"Point BACnet inconnu : {name} (connus : {known})")


def _build_client_application(*, local_instance: int) -> Application:
    """Une application BACnet locale, purement cliente (jamais d'objet
    exposé au réseau) : un identifiant d'instance dédié pour ne jamais
    entrer en conflit avec un vrai appareil du site."""
    args = argparse.Namespace(
        name=f"paios-bacnet-client-{local_instance}",
        instance=local_instance,
        network=0,
        address=None,
        vendoridentifier=_GENERIC_VENDOR_ID,
        foreign=None,
        ttl=30,
        bbmd=None,
    )
    return Application.from_args(args)


async def _read_bacnet_points_async(
    address: str,
    points: list[BacnetPoint],
    *,
    local_instance: int,
    timeout: float,
) -> dict[str, float]:
    application = _build_client_application(local_instance=local_instance)
    values: dict[str, float] = {}
    try:
        for point in points:
            try:
                response = await asyncio.wait_for(
                    application.read_property(
                        address,
                        ObjectIdentifier((point.object_type, point.object_instance)),
                        PropertyIdentifier(point.property_identifier),
                    ),
                    timeout=timeout,
                )
            except TimeoutError as exc:
                raise BacnetReadError(
                    f"Délai dépassé en lisant « {point.name} » à {address}"
                ) from exc
            except (ValueError, TypeError) as exc:
                # Adressage BACnet invalide (type d'objet ou propriété
                # inconnus) : une erreur de configuration, pas une panne
                # réseau, mais on la rapporte de la même façon à l'appelant.
                raise BacnetReadError(f"Adressage invalide pour « {point.name} »") from exc
            except ErrorRejectAbortNack as exc:
                # Une erreur applicative (ex. objet inconnu de l'appareil)
                # peut être levée comme exception plutôt que renvoyée comme
                # valeur, selon le cas — les deux formes sont couvertes ici
                # et un peu plus bas.
                raise BacnetReadError(f"Appareil en erreur pour « {point.name} » : {exc}") from exc

            if isinstance(response, ErrorRejectAbortNack):
                raise BacnetReadError(f"Appareil en erreur pour « {point.name} » : {response}")

            values[point.name] = float(response)
    finally:
        application.close()

    return values


def read_bacnet_points(
    address: str,
    points: list[BacnetPoint],
    *,
    local_instance: int = 3969999,
    timeout: float = 3.0,
) -> dict[str, float]:
    """Lit une liste de points sur un appareil BACnet/IP. Renvoie nom → valeur.

    `address` est l'adresse BACnet/IP de l'appareil distant (ex.
    `"192.168.1.50"` ou `"192.168.1.50:47808"`). `local_instance` identifie
    l'application cliente elle-même sur le réseau BACnet ; à changer si
    plusieurs démons de ce type tournent sur le même réseau BACnet, pour
    qu'ils n'entrent jamais en conflit d'identifiant.
    """
    return asyncio.run(
        _read_bacnet_points_async(address, points, local_instance=local_instance, timeout=timeout)
    )


@dataclass(frozen=True)
class BacnetDeviceInfo:
    """Un appareil BACnet identifié par diffusion Who-Is/I-Am (découverte,
    jamais une configuration donnée en paramètre)."""

    device_instance: int
    address: str
    vendor_id: int | None
    max_apdu_length: int | None


async def _discover_device_async(
    address: str, *, local_instance: int, timeout: float
) -> BacnetDeviceInfo:
    application = _build_client_application(local_instance=local_instance)
    try:
        try:
            responses = await asyncio.wait_for(
                application.who_is(address=Address(address), timeout=timeout),
                timeout=timeout + 1.0,
            )
        except TimeoutError as exc:
            raise BacnetReadError(f"Délai dépassé en découvrant {address}") from exc
        except (ValueError, TypeError) as exc:
            raise BacnetReadError(f"Adresse BACnet invalide : {address}") from exc

        if not responses:
            raise BacnetReadError(f"Aucun appareil BACnet n'a répondu à {address}")
        i_am = responses[0]
        return BacnetDeviceInfo(
            device_instance=i_am.iAmDeviceIdentifier[1],
            address=address,
            vendor_id=int(i_am.vendorID) if i_am.vendorID is not None else None,
            max_apdu_length=(
                int(i_am.maxAPDULengthAccepted)
                if i_am.maxAPDULengthAccepted is not None
                else None
            ),
        )
    finally:
        application.close()


def discover_device(
    address: str, *, local_instance: int = 3969999, timeout: float = 3.0
) -> BacnetDeviceInfo:
    """Diffusion Who-Is dirigée vers `address` (unicast) : confirme qu'un
    appareil BACnet y répond et donne son identifiant, avant de tenter d'en
    inventorier les objets. Jamais une diffusion de sous-réseau entière dans
    cette version (V1) : une adresse précise, donnée par une personne."""
    return asyncio.run(
        _discover_device_async(address, local_instance=local_instance, timeout=timeout)
    )


@dataclass(frozen=True)
class BacnetObjectInfo:
    """Un objet BACnet découvert sur un appareil, avec assez de métadonnées
    pour proposer une correspondance sémantique (app.connectors.bacnet_semantics)
    — jamais la valeur elle-même comme télémétrie : cette découverte est un
    inventaire, la relève régulière (read_bacnet_points) reste le seul chemin
    vers app.telemetry."""

    object_type: str
    object_instance: int
    value_type: str
    object_name: str | None
    description: str | None
    units: str | None
    present_value_preview: str | None
    states: dict[str, str] | None


async def _read_optional_property(
    application: Application, address: str, object_identifier: ObjectIdentifier, property_name: str
) -> Any | None:
    """None si la propriété n'existe pas pour ce type d'objet (courant :
    « units » sur un objet binaire, « description » absente) — une absence
    de propriété n'est jamais une panne de communication."""
    try:
        return await application.read_property(
            address, object_identifier, PropertyIdentifier(property_name)
        )
    except ErrorRejectAbortNack:
        return None


async def _read_device_objects_async(
    address: str,
    device_instance: int,
    *,
    local_instance: int,
    timeout: float,
) -> list[BacnetObjectInfo]:
    application = _build_client_application(local_instance=local_instance)
    objects: list[BacnetObjectInfo] = []
    try:
        try:
            object_list = await asyncio.wait_for(
                application.read_property(
                    address,
                    ObjectIdentifier(("device", device_instance)),
                    PropertyIdentifier("object-list"),
                ),
                timeout=timeout,
            )
        except TimeoutError as exc:
            raise BacnetReadError(f"Délai dépassé en lisant l'inventaire de {address}") from exc
        except ErrorRejectAbortNack as exc:
            raise BacnetReadError(
                f"Appareil en erreur en lisant l'inventaire de {address} : {exc}"
            ) from exc

        for object_identifier in object_list:
            object_type = str(object_identifier[0])
            value_type = _DISCOVERABLE_OBJECT_TYPES.get(object_type)
            if value_type is None:
                continue
            object_instance = int(object_identifier[1])

            name = await _read_optional_property(
                application, address, object_identifier, "object-name"
            )
            description = await _read_optional_property(
                application, address, object_identifier, "description"
            )
            units = await _read_optional_property(application, address, object_identifier, "units")
            present_value = await _read_optional_property(
                application, address, object_identifier, "present-value"
            )
            states: dict[str, str] | None = None
            if value_type == "multistate":
                state_text = await _read_optional_property(
                    application, address, object_identifier, "state-text"
                )
                if state_text:
                    # Les valeurs multi-état BACnet sont numérotées à partir
                    # de 1, dans l'ordre de state-text (norme ASHRAE 135) —
                    # jamais une correspondance devinée.
                    states = {str(index + 1): str(text) for index, text in enumerate(state_text)}

            objects.append(
                BacnetObjectInfo(
                    object_type=object_type,
                    object_instance=object_instance,
                    value_type=value_type,
                    object_name=str(name) if name is not None else None,
                    description=str(description) if description is not None else None,
                    units=str(units) if units is not None else None,
                    present_value_preview=str(present_value) if present_value is not None else None,
                    states=states,
                )
            )
    finally:
        application.close()

    return objects


def read_device_objects(
    address: str,
    device_instance: int,
    *,
    local_instance: int = 3969999,
    timeout: float = 3.0,
) -> list[BacnetObjectInfo]:
    """Inventaire des objets « point » (voir `_DISCOVERABLE_OBJECT_TYPES`)
    exposés par un appareil déjà identifié (`discover_device`). Lecture
    seule : ReadProperty uniquement, jamais d'écriture, comme le reste de ce
    module (règle non négociable 1)."""
    return asyncio.run(
        _read_device_objects_async(
            address, device_instance, local_instance=local_instance, timeout=timeout
        )
    )
