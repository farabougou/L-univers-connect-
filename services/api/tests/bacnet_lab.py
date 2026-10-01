"""BACnet Lab : simulateur BACnet réutilisable pour le développement et la
CI (directive de Mohamed, 27/09/2026 — « Mets en place un BACnet Lab /
simulateur automatisé » ; enrichi le 30/09/2026 — « reproduire plusieurs
catégories d'équipements et scénarios réalistes »).

Un vrai appareil BACnet/IP (bacpypes3), pas un mock : un test qui passe ici
prouve que le connecteur dialogue réellement en BACnet (Who-Is/I-Am,
ReadProperty, décodage de propriété). C'est le palier SIMULATOR_TESTED,
distinct de UNIT_TESTED (aucun réseau, ex. test_bacnet_semantics.py) et de
FIELD_TESTED (un vrai appareil sur un vrai réseau, BLOCKED_EXTERNAL_VALIDATION
jusqu'aux essais terrain autorisés — voir docs/adr/015-decouverte-bacnet-v1.md).
Aucun de ces profils, aussi réaliste soit-il, ne constitue une validation
terrain : seul un appareil BACnet réel, sur un réseau réel, le peut.

Six profils d'équipement (`PROFILES`), couvrant volontairement des
typologies CVC/froid/production-électrique/réseaux thermiques/comptage
réelles, avec un mélange délibéré d'objets que notre devineur sémantique
sait déjà classer (température avec unité, pression, défaut/marche,
consigne, autorisation) et d'objets qu'il ne sait pas encore classer
(tension, fréquence, niveau de carburant, débit, puissance réactive —
unité BACnet reconnue ou non, mais sans classe `point_class` correspondante
dans `app.point_vocabulary` : la « règle des trois » n'ajoute une classe que
sur un cas réel, jamais par anticipation) : un test qui passe ici prouve
aussi que le devineur ne force jamais une correspondance hors de sa
compétence réelle, sur un jeu d'équipements volontairement plus large que
la seule CTA d'origine.

Le profil par défaut (`"cta"`) reste inchangé depuis sa version d'origine :
les tests déjà écrits contre lui (BacnetLab(address, device_instance=...))
continuent de fonctionner sans modification.
"""

import argparse
import asyncio
import threading
from collections.abc import Callable
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
    profile: str
    server: Application


def _analog_input(instance: int, name: str, value: float, units: str) -> AnalogInputObject:
    return AnalogInputObject(
        objectIdentifier=("analog-input", instance),
        objectName=name,
        presentValue=value,
        statusFlags=_NEUTRAL_STATUS,
        covIncrement=0.1,
        units=units,
    )


def _analog_output(instance: int, name: str, value: float, units: str) -> AnalogOutputObject:
    return AnalogOutputObject(
        objectIdentifier=("analog-output", instance),
        objectName=name,
        presentValue=value,
        statusFlags=_NEUTRAL_STATUS,
        relinquishDefault=value,
        units=units,
    )


def _binary_input(instance: int, name: str, active: bool) -> BinaryInputObject:
    return BinaryInputObject(
        objectIdentifier=("binary-input", instance),
        objectName=name,
        presentValue="active" if active else "inactive",
        statusFlags=_NEUTRAL_STATUS,
    )


def _binary_value(instance: int, name: str, active: bool) -> BinaryValueObject:
    return BinaryValueObject(
        objectIdentifier=("binary-value", instance),
        objectName=name,
        presentValue="active" if active else "inactive",
        statusFlags=_NEUTRAL_STATUS,
    )


def _multi_state_value(
    instance: int, name: str, value: int, states: list[str]
) -> MultiStateValueObject:
    return MultiStateValueObject(
        objectIdentifier=("multi-state-value", instance),
        objectName=name,
        presentValue=value,
        numberOfStates=len(states),
        stateText=states,
        statusFlags=_NEUTRAL_STATUS,
    )


def _build_cta_objects(server: Application) -> None:
    """Centrale de traitement d'air (CVC tertiaire) — profil d'origine,
    inchangé : température avec unité, pression, valeur sans unité
    exploitable, consigne en sortie analogique, défaut/marche binaires,
    autorisation, mode multi-état."""
    server.add_object(_analog_input(1, "T Depart CTA", 18.2, "degreesCelsius"))
    server.add_object(_analog_input(2, "P Refoulement", 350.0, "kilopascals"))
    server.add_object(_analog_input(3, "AI-07", 42.0, "noUnits"))
    server.add_object(_analog_output(1, "Consigne Depart CTA", 19.0, "degreesCelsius"))
    server.add_object(_binary_input(1, "Defaut General CTA", False))
    server.add_object(_binary_input(2, "Marche Ventilateur", True))
    server.add_object(_binary_value(1, "Autorisation Marche", True))
    server.add_object(_multi_state_value(1, "Mode CTA", 2, ["Arret", "Confort", "Reduit"]))


def _build_groupe_froid_objects(server: Application) -> None:
    """Groupe de production d'eau glacée (froid tertiaire/industriel)."""
    server.add_object(_analog_input(1, "T Eau Glacee Depart", 7.0, "degreesCelsius"))
    server.add_object(_analog_input(2, "T Eau Glacee Retour", 12.5, "degreesCelsius"))
    server.add_object(_analog_input(3, "Taux Charge Compresseur", 68.0, "percent"))
    server.add_object(_binary_input(1, "Defaut Compresseur", False))
    server.add_object(_binary_input(2, "Marche Compresseur", True))
    server.add_object(_binary_value(1, "Autorisation Production Froid", True))
    server.add_object(
        _multi_state_value(1, "Etat Groupe Froid", 2, ["Arret", "Production", "Degivrage"])
    )


def _build_groupe_electrogene_objects(server: Application) -> None:
    """Groupe électrogène de secours — deux mesures volontairement sans
    correspondance sémantique fiable aujourd'hui (tension, niveau de
    carburant : aucune classe `point_class` ni unité BACnet reconnue pour la
    tension dans notre vocabulaire actuel)."""
    server.add_object(_analog_input(1, "Tension Sortie", 400.0, "volts"))
    server.add_object(_analog_input(2, "Niveau Carburant", 82.0, "percent"))
    server.add_object(_binary_input(1, "Defaut Groupe Electrogene", False))
    server.add_object(_binary_input(2, "Marche Groupe Electrogene", False))
    server.add_object(_binary_value(1, "Autorisation Demarrage", True))
    server.add_object(
        _multi_state_value(1, "Mode Fonctionnement", 2, ["Arret", "Automatique", "Manuel", "Test"])
    )


def _build_vrv_drv_objects(server: Application) -> None:
    """Système VRV/DRV (climatisation multi-split à débit de réfrigérant
    variable), plusieurs zones intérieures sur un même appareil BACnet."""
    server.add_object(_analog_input(1, "T Air Interieur Zone 1", 22.5, "degreesCelsius"))
    server.add_object(_analog_input(2, "T Air Exterieur", 8.0, "degreesCelsius"))
    server.add_object(_analog_output(1, "Consigne Zone 1", 21.0, "degreesCelsius"))
    server.add_object(_binary_input(1, "Defaut Unite Exterieure", False))
    server.add_object(_binary_input(2, "Marche Zone 1", True))
    server.add_object(
        _multi_state_value(1, "Mode Zone 1", 3, ["Arret", "Froid", "Chaud", "Ventilation", "Auto"])
    )


def _build_sous_station_thermique_objects(server: Application) -> None:
    """Sous-station d'échange avec un réseau urbain de chaleur ou de
    froid — le débit à l'échangeur est une unité reconnue
    (`cubic-meters-per-hour`) mais sans classe de point de débit dans notre
    vocabulaire actuel : reste volontairement à revoir."""
    server.add_object(_analog_input(1, "T Depart Reseau", 75.0, "degreesCelsius"))
    server.add_object(_analog_input(2, "T Retour Reseau", 55.0, "degreesCelsius"))
    server.add_object(_analog_input(3, "Pression Reseau", 4.2, "bars"))
    server.add_object(_analog_input(4, "Debit Echangeur", 12.5, "cubicMetersPerHour"))
    server.add_object(_binary_value(1, "Autorisation Reseau", True))
    server.add_object(
        _multi_state_value(1, "Etat Sous-Station", 1, ["Arret", "Chauffage", "Refroidissement"])
    )


def _build_comptage_objects(server: Application) -> None:
    """Comptage électrique exposé par une passerelle BACnet (plutôt que
    Modbus directement, cas réel sur certains sites) — la puissance
    réactive reste volontairement à revoir (aucune unité BACnet reconnue
    dans notre table de conversion pour le kvar)."""
    server.add_object(_analog_input(1, "Energie Active Totale", 154302.0, "kilowattHours"))
    server.add_object(_analog_input(2, "Puissance Active", 48.5, "kilowatts"))
    server.add_object(_analog_input(3, "Puissance Reactive", 12.0, "noUnits"))
    server.add_object(_binary_input(1, "Defaut Comptage", False))


# Six profils, un par catégorie d'équipement demandée explicitement
# (CVC, froid, production électrique de secours, VRV/DRV, réseaux
# thermiques urbains, comptage) — jamais présentés comme une liste
# exhaustive des équipements GTB réels, seulement comme un jeu de départ
# réaliste pour le développement et la CI.
PROFILES: dict[str, Callable[[Application], None]] = {
    "cta": _build_cta_objects,
    "groupe_froid": _build_groupe_froid_objects,
    "groupe_electrogene": _build_groupe_electrogene_objects,
    "vrv_drv": _build_vrv_drv_objects,
    "sous_station_thermique": _build_sous_station_thermique_objects,
    "comptage": _build_comptage_objects,
}


def list_profiles() -> list[str]:
    return sorted(PROFILES)


async def _build_lab_async(address: str, device_instance: int, profile: str) -> Application:
    try:
        build_objects = PROFILES[profile]
    except KeyError:
        raise ValueError(
            f"profil BACnet Lab inconnu : {profile!r} (profils disponibles : "
            f"{', '.join(list_profiles())})"
        ) from None
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
    build_objects(server)
    return server


class BacnetLab:
    """Démarre un appareil BACnet simulé dans un fil dédié, avec sa propre
    boucle asyncio — le même principe que les démons réels (chaque relève
    ouvre puis referme sa propre boucle), pour que les tests appellent les
    fonctions synchrones du connecteur exactement comme le démon le ferait.

    `profile` choisit le jeu d'objets simulés (voir `PROFILES` /
    `list_profiles()`) ; par défaut `"cta"`, pour rester compatible avec
    tout code déjà écrit contre ce simulateur."""

    def __init__(self, address: str, device_instance: int = 5001, profile: str = "cta"):
        if profile not in PROFILES:
            raise ValueError(
                f"profil BACnet Lab inconnu : {profile!r} (profils disponibles : "
                f"{', '.join(list_profiles())})"
            )
        self.address = address
        self.device_instance = device_instance
        self.profile = profile
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._server: Application | None = None

    def start(self) -> LabDevice:
        self._thread.start()
        self._server = asyncio.run_coroutine_threadsafe(
            _build_lab_async(self.address, self.device_instance, self.profile), self._loop
        ).result(timeout=5)
        return LabDevice(
            address=self.address,
            device_instance=self.device_instance,
            profile=self.profile,
            server=self._server,
        )

    def stop(self) -> None:
        if self._server is not None:
            self._loop.call_soon_threadsafe(self._server.close)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)


class BacnetSite:
    """Simule un petit site avec plusieurs appareils BACnet de catégories
    différentes en même temps (une adresse:port distincte par appareil) —
    utile pour préparer la méthodologie de comparaison terrain (ADR 015,
    section 6 : GTB existante ↔ découverte ↔ Edge ↔ modèle sémantique ↔
    jumeau numérique) sans dépendre d'un site réel pendant le développement.

    `devices` associe un nom d'appareil (libre, ex. « cta-01 », choisi par
    l'appelant) à (adresse, profil) ; l'identifiant BACnet de chaque
    appareil est dérivé automatiquement pour rester unique sur le site
    simulé."""

    def __init__(self, devices: dict[str, tuple[str, str]], *, base_device_instance: int = 6000):
        self._labs: dict[str, BacnetLab] = {
            name: BacnetLab(address, device_instance=base_device_instance + index, profile=profile)
            for index, (name, (address, profile)) in enumerate(devices.items())
        }
        self.devices: dict[str, LabDevice] = {}

    def start(self) -> dict[str, LabDevice]:
        self.devices = {name: lab.start() for name, lab in self._labs.items()}
        return self.devices

    def stop(self) -> None:
        for lab in self._labs.values():
            lab.stop()
