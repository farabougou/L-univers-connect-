"""BACnet Lab : simulateur BACnet réutilisable pour le développement et la
CI (directive de Mohamed, 27/09/2026 — « Mets en place un BACnet Lab /
simulateur automatisé »).

Un vrai appareil BACnet/IP (bacpypes3), pas un mock : un test qui passe ici
prouve que le connecteur dialogue réellement en BACnet (Who-Is/I-Am,
ReadProperty, décodage de propriété). C'est le palier SIMULATOR_TESTED,
distinct de UNIT_TESTED (aucun réseau, ex. test_bacnet_semantics.py) et de
FIELD_TESTED (un vrai appareil sur un vrai réseau, BLOCKED jusqu'aux essais
terrain autorisés — voir docs/spec/bacnet-connector-v1-adr.md).

Le jeu d'objets par défaut couvre volontairement plusieurs typologies
d'installation CVC/froid réelles (température avec unité, pression sans
nom explicite, défaut/marche binaires, consigne en sortie analogique, mode
multi-état) pour que les tests de découverte et de correspondance
sémantique aient quelque chose de représentatif à trouver, sans dépendre
d'un appareil réel.
"""

import argparse
import asyncio
import threading
from dataclasses import dataclass

from bacpypes3.app import Application
from bacpypes3.basetypes import StatusFlags
from bacpypes3.local.analog import AnalogInputObject, AnalogOutputObject
from bacpypes3.local.binary import BinaryInputObject, BinaryValueObject
from bacpypes3.local.multistate import MultiStateValueObject

_NEUTRAL_STATUS = StatusFlags([0, 0, 0, 0])


@dataclass(frozen=True)
class LabDevice:
    address: str
    device_instance: int
    server: Application


def _build_objects(server: Application) -> None:
    server.add_object(
        AnalogInputObject(
            objectIdentifier=("analog-input", 1),
            objectName="T Depart CTA",
            presentValue=18.2,
            statusFlags=_NEUTRAL_STATUS,
            covIncrement=0.1,
            units="degreesCelsius",
        )
    )
    server.add_object(
        AnalogInputObject(
            objectIdentifier=("analog-input", 2),
            objectName="P Refoulement",
            presentValue=350.0,
            statusFlags=_NEUTRAL_STATUS,
            covIncrement=1.0,
            units="kilopascals",
        )
    )
    server.add_object(
        AnalogInputObject(
            objectIdentifier=("analog-input", 3),
            objectName="AI-07",
            presentValue=42.0,
            statusFlags=_NEUTRAL_STATUS,
            covIncrement=1.0,
            units="noUnits",
        )
    )
    server.add_object(
        AnalogOutputObject(
            objectIdentifier=("analog-output", 1),
            objectName="Consigne Depart CTA",
            presentValue=19.0,
            statusFlags=_NEUTRAL_STATUS,
            relinquishDefault=19.0,
            units="degreesCelsius",
        )
    )
    server.add_object(
        BinaryInputObject(
            objectIdentifier=("binary-input", 1),
            objectName="Defaut General CTA",
            presentValue="inactive",
            statusFlags=_NEUTRAL_STATUS,
        )
    )
    server.add_object(
        BinaryInputObject(
            objectIdentifier=("binary-input", 2),
            objectName="Marche Ventilateur",
            presentValue="active",
            statusFlags=_NEUTRAL_STATUS,
        )
    )
    server.add_object(
        BinaryValueObject(
            objectIdentifier=("binary-value", 1),
            objectName="Autorisation Marche",
            presentValue="active",
            statusFlags=_NEUTRAL_STATUS,
        )
    )
    server.add_object(
        MultiStateValueObject(
            objectIdentifier=("multi-state-value", 1),
            objectName="Mode CTA",
            presentValue=2,
            numberOfStates=3,
            stateText=["Arret", "Confort", "Reduit"],
            statusFlags=_NEUTRAL_STATUS,
        )
    )


async def _build_lab_async(address: str, device_instance: int) -> Application:
    args = argparse.Namespace(
        name=f"paios-bacnet-lab-{device_instance}",
        instance=device_instance,
        network=0,
        address=address,
        vendoridentifier=999,
        foreign=None,
        ttl=30,
        bbmd=None,
    )
    server = Application.from_args(args)
    _build_objects(server)
    return server


class BacnetLab:
    """Démarre un appareil BACnet simulé dans un fil dédié, avec sa propre
    boucle asyncio — le même principe que les démons réels (chaque relève
    ouvre puis referme sa propre boucle), pour que les tests appellent les
    fonctions synchrones du connecteur exactement comme le démon le ferait."""

    def __init__(self, address: str, device_instance: int = 5001):
        self.address = address
        self.device_instance = device_instance
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._server: Application | None = None

    def start(self) -> LabDevice:
        self._thread.start()
        self._server = asyncio.run_coroutine_threadsafe(
            _build_lab_async(self.address, self.device_instance), self._loop
        ).result(timeout=5)
        return LabDevice(
            address=self.address, device_instance=self.device_instance, server=self._server
        )

    def stop(self) -> None:
        if self._server is not None:
            self._loop.call_soon_threadsafe(self._server.close)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)
