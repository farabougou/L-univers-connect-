"""Adaptateur d'import IFC (ADR 011, section 2 « BIM / IFC »).

Seul fichier du dépôt qui importe ifcopenshell (LGPL-3.0-or-later, mûre et
maintenue — vérifié le 26/09/2026 avant d'ajouter la dépendance). Rien en
dehors de ce module ne connaît cette bibliothèque : un futur changement de
parseur, y compris un changement de version majeure incompatible, se limite
à ce fichier, jamais au modèle métier (app.ifc_import, app.assets,
app.spatial). La sortie est volontairement pauvre — des structures simples,
jamais les objets ifcopenshell eux-mêmes.

Un fichier IFC vient d'un client, jamais d'une source de confiance : trois
protections avant tout appel à la bibliothèque (taille, en-tête attendu,
encodage), puis tout appel à ifcopenshell est encadré, une exception non
prévue de la bibliothèque devenant une erreur de format ordinaire plutôt
qu'un plantage (mitigations documentées pour les fichiers IFC non fiables).
"""

import dataclasses

import ifcopenshell

MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024

# Correspondance sûre avec app/spatial_vocabulary.py (SPACE_TYPES) : seules
# les classes IFC déjà déclarées là comme correspondance certaine. IfcSite
# et IfcZone sont volontairement absents (aucune correspondance fiable,
# jamais un espace de notre modèle) — voir la même prudence dans le
# vocabulaire, qui n'attribue pas d'équivalent IFC à « zone ».
_IFC_CLASS_TO_SPACE_TYPE = {
    "IfcBuilding": "building",
    "IfcBuildingStorey": "floor",
    "IfcSpace": "room",
}

# Sous-arbre IFC4 des équipements de distribution CVC, froid, plomberie et
# électricité : le socle pertinent pour le premier produit (wedge CVC/froid
# tertiaire). Une classe absente de cette liste n'est jamais proposée :
# mieux vaut manquer un équipement que proposer n'importe quel objet du
# modèle (ADR 011, point 9 : « toute détection automatique doit rester
# vérifiable/corrigeable par l'utilisateur »).
_EQUIPMENT_BASE_CLASSES = (
    "IfcDistributionElement",
    "IfcFlowMovingDevice",
    "IfcEnergyConversionDevice",
    "IfcFlowController",
    "IfcFlowStorageDevice",
    "IfcFlowTreatmentDevice",
)


class IfcParseError(Exception):
    """Fichier illisible, trop volumineux ou dont l'en-tête n'est pas reconnu.

    `code` porte le code d'erreur stable (catalogue i18n) ; jamais de phrase
    générée ici."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class SpaceProposal:
    ifc_global_id: str
    ifc_class: str
    space_type: str
    name: str
    parent_ifc_global_id: str | None


@dataclasses.dataclass(frozen=True)
class EquipmentProposal:
    ifc_global_id: str
    ifc_class: str
    name: str
    containing_space_ifc_global_id: str | None


@dataclasses.dataclass(frozen=True)
class IfcParseResult:
    schema: str
    spaces: list[SpaceProposal]
    equipment: list[EquipmentProposal]
    skipped_element_count: int


def parse_ifc_bytes(content: bytes) -> IfcParseResult:
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise IfcParseError("IFC_IMPORT_FILE_TOO_LARGE")
    text = _decode(content)
    try:
        model = ifcopenshell.file.from_string(text)
    except IfcParseError:
        raise
    except Exception as exc:  # ifcopenshell ne documente pas un type d'erreur unique
        raise IfcParseError("IFC_IMPORT_PARSE_FAILED") from exc
    return _extract(model)


def _decode(content: bytes) -> str:
    # En-tête STEP obligatoire (ISO 10303-21) : premier filtre, avant tout
    # appel à la bibliothèque, contre un fichier qui n'est simplement pas de
    # l'IFC (IFC-ZIP et IfcXML : DEFER, non pris en charge pour l'instant).
    if not content.lstrip().startswith(b"ISO-10303-21;"):
        raise IfcParseError("IFC_IMPORT_INVALID_FORMAT")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IfcParseError("IFC_IMPORT_INVALID_FORMAT") from exc


def _parent_global_id(entity) -> str | None:
    decomposes = getattr(entity, "Decomposes", None)
    if not decomposes:
        return None
    return decomposes[0].RelatingObject.GlobalId


def _containing_space_global_id(entity) -> str | None:
    contained = getattr(entity, "ContainedInStructure", None)
    if not contained:
        return None
    return contained[0].RelatingStructure.GlobalId


def _extract(model) -> IfcParseResult:
    spaces = [
        SpaceProposal(
            ifc_global_id=entity.GlobalId,
            ifc_class=ifc_class,
            space_type=space_type,
            name=entity.Name or ifc_class,
            parent_ifc_global_id=_parent_global_id(entity),
        )
        for ifc_class, space_type in _IFC_CLASS_TO_SPACE_TYPE.items()
        for entity in model.by_type(ifc_class)
    ]

    equipment = [
        EquipmentProposal(
            ifc_global_id=entity.GlobalId,
            ifc_class=entity.is_a(),
            name=entity.Name or entity.is_a(),
            containing_space_ifc_global_id=_containing_space_global_id(entity),
        )
        for entity in model.by_type("IfcElement")
        if any(entity.is_a(base_class) for base_class in _EQUIPMENT_BASE_CLASSES)
    ]

    total_elements = len(model.by_type("IfcElement"))
    return IfcParseResult(
        schema=model.schema,
        spaces=spaces,
        equipment=equipment,
        skipped_element_count=max(0, total_elements - len(equipment)),
    )
