"""Vocabulaire des espaces et des positions fonctionnelles (ADR 011).

Texte contrôlé côté application, pas énumération figée en base : ajouter un
type pour un autre secteur (station de pompage, zone de production…) ne
demande aucune migration, seulement une nouvelle version de ce fichier.
Correspondances Brick et IFC indiquées seulement quand elles sont sûres.

Les types ne sont ajoutés qu'avec un cas réel (règle des trois) : pas de
type spéculatif « au cas où ».
"""

from dataclasses import dataclass

from app.errors import DomainError

SPATIAL_VOCABULARY_VERSION = "2026-09-23.1"


@dataclass(frozen=True)
class SpaceType:
    name: str
    # Types de parent autorisés ; None = directement sous le site.
    parent_types: tuple[str | None, ...]
    brick: str | None = None
    ifc: str | None = None


SPACE_TYPES: dict[str, SpaceType] = {
    t.name: t
    for t in (
        SpaceType("building", (None,), brick="brick:Building", ifc="IfcBuilding"),
        SpaceType("floor", ("building",), brick="brick:Floor", ifc="IfcBuildingStorey"),
        # Zone : subdivision d'un bâtiment ou d'un étage (open space, zone CVC
        # couvrant plusieurs pièces). Une pièce peut aussi être rattachée à une
        # zone par la relation « servedBy » sans en être un enfant.
        SpaceType("zone", ("building", "floor"), brick="brick:Zone"),
        SpaceType("room", ("floor", "zone"), brick="brick:Room", ifc="IfcSpace"),
        SpaceType("outdoor_area", (None,), brick="brick:Outdoor_Area"),
    )
}


class SpatialVocabularyError(DomainError, ValueError):
    pass


def check_space_placement(space_type: str, parent_type: str | None) -> SpaceType:
    definition = SPACE_TYPES.get(space_type)
    if definition is None:
        raise SpatialVocabularyError("SPACE_TYPE_UNKNOWN", space_type=space_type)
    if parent_type not in definition.parent_types:
        if parent_type is None:
            raise SpatialVocabularyError(
                "SPACE_PLACEMENT_UNDER_SITE_FORBIDDEN", space_type=space_type
            )
        raise SpatialVocabularyError(
            "SPACE_PLACEMENT_FORBIDDEN", space_type=space_type, parent_type=parent_type
        )
    return definition
