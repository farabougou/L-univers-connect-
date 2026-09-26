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

from bacpypes3.apdu import ErrorRejectAbortNack
from bacpypes3.app import Application
from bacpypes3.primitivedata import ObjectIdentifier, PropertyIdentifier

# Identifiant fournisseur "générique" (ASHRAE, 999) : celui que les outils
# bacpypes3 eux-mêmes utilisent par défaut pour un client qui n'annonce
# aucun matériel propre. Jamais utilisé pour un objet exposé au réseau
# (ce connecteur ne construit qu'une application cliente).
_GENERIC_VENDOR_ID = 999


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
