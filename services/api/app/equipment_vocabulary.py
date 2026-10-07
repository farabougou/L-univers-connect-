"""Types universels d'équipement et normalisation des appellations (ADR 013,
étape L5 ; directive « langage produit », point 12).

Chaque fabricant nomme ses produits à sa façon ; la plateforme conserve :
- la désignation du fabricant, telle quelle (`manufacturer_designation`) ;
- le type universel, stable et indépendant de la langue (`equipment_type`) ;
- la correspondance Brick quand elle existe (vérifiée sur Brick 1.3.0 :
  aucune classe n'y représente une pompe à chaleur ni une sous-station, la
  case reste donc vide plutôt que d'inventer une équivalence) ;
- des alias, qui servent à proposer un type à partir d'un texte libre.
Les libellés affichés sont dans le catalogue `ui` (section `equipment_type`).

Une proposition de normalisation n'est qu'une proposition : c'est une
personne qui choisit le type enregistré.

Comme les autres vocabulaires, ajouter un type ne demande pas de migration,
seulement une nouvelle version de ce fichier ; on n'en retire jamais.
"""

import re
import unicodedata
from dataclasses import dataclass

EQUIPMENT_VOCABULARY_VERSION = "2026-09-24.1"


@dataclass(frozen=True)
class EquipmentType:
    code: str
    brick: str | None
    aliases: tuple[str, ...]


EQUIPMENT_TYPES: dict[str, EquipmentType] = {
    t.code: t
    for t in (
        EquipmentType(
            "heat_pump",
            None,
            ("pac", "pompe a chaleur", "heat pump", "thermodynamique"),
        ),
        EquipmentType(
            "chiller",
            "brick:Chiller",
            ("groupe froid", "groupe d eau glacee", "gef", "refroidisseur", "chiller"),
        ),
        EquipmentType(
            "dry_cooler",
            "brick:Dry_Cooler",
            ("dry cooler", "drycooler", "aerorefrigerant", "aeroréfrigérant sec"),
        ),
        EquipmentType(
            "air_handling_unit",
            "brick:Air_Handling_Unit",
            ("cta", "centrale de traitement d air", "ahu", "air handling unit"),
        ),
        EquipmentType("pump", "brick:Pump", ("pompe", "circulateur", "pump")),
        EquipmentType(
            "district_heating_substation",
            None,
            ("sous station", "sous station chaud", "sst", "sous station reseau de chaleur"),
        ),
        EquipmentType(
            "district_cooling_substation",
            None,
            ("sous station froid", "sous station reseau de froid"),
        ),
        EquipmentType("boiler", "brick:Boiler", ("chaudiere", "boiler")),
        EquipmentType(
            "fan_coil_unit",
            "brick:Fan_Coil_Unit",
            ("ventilo convecteur", "ventiloconvecteur", "fcu", "fan coil"),
        ),
        EquipmentType(
            "heat_exchanger",
            "brick:Heat_Exchanger",
            ("echangeur", "echangeur a plaques", "heat exchanger"),
        ),
        EquipmentType("other", None, ()),
    )
}


def _normalize(text: str) -> str:
    """« Pompe à Chaleur — Air/Eau » → « pompe a chaleur air eau »."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", ascii_only).strip()


def suggest_equipment_type(text: str) -> str | None:
    """Type proposé pour un texte libre (désignation, ancienne catégorie).

    L'alias le plus long trouvé comme suite de mots l'emporte (« pompe à
    chaleur » avant « pompe ») ; en cas d'égalité entre deux types, aucune
    proposition : mieux vaut demander que deviner."""
    words = f" {_normalize(text)} "
    best_length, best = 0, set()
    for equipment in EQUIPMENT_TYPES.values():
        for alias in equipment.aliases:
            normalized = _normalize(alias)
            if f" {normalized} " in words:
                if len(normalized) > best_length:
                    best_length, best = len(normalized), {equipment.code}
                elif len(normalized) == best_length:
                    best.add(equipment.code)
    return best.pop() if len(best) == 1 else None
