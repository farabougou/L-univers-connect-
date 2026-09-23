"""Vocabulaire interne versionné du graphe d'actifs (ADR 012, section 2.2).

Aligné sur les standards sans en dépendre : chaque prédicat indique sa
correspondance connue dans Brick Schema ou ASHRAE 223P, et `None` quand aucune
correspondance n'a été vérifiée (mieux vaut l'absence qu'une correspondance
inventée). Un seul sens est stocké ; l'inverse est seulement affiché.

Modifier ce vocabulaire (ajout, retrait, changement de domaine) impose de
changer VOCABULARY_VERSION : chaque relation garde la version sous laquelle
elle a été créée.

Historique :
- 2026-09-23.1 : F1, sites, positions fonctionnelles, exemplaires.
- 2026-09-23.2 : F2, ajout des espaces (bâtiment, étage, pièce, zone) et du
  prédicat déduit « locatedIn ».
"""

from dataclasses import dataclass

VOCABULARY_VERSION = "2026-09-23.2"

# Types de nœuds existants à ce jour. Les types futurs (point, edge_device,
# organization) seront ajoutés avec leurs tables respectives.
NODE_TYPES = ("site", "space", "functional_location", "physical_unit")


@dataclass(frozen=True)
class Predicate:
    name: str
    inverse: str
    subject_types: tuple[str, ...]
    object_types: tuple[str, ...]
    # Déduit des arbres (colonnes parent_id, site_id, space_id) : jamais stocké
    # dans la table relations, pour garder une seule source de vérité.
    structural: bool = False
    brick: str | None = None
    s223: str | None = None


_EQUIPMENT = ("functional_location",)
_SPACE = ("space",)
_EQUIPMENT_OR_SPACE = ("space", "functional_location")

PREDICATES: dict[str, Predicate] = {
    p.name: p
    for p in (
        Predicate(
            "contains",
            "isContainedIn",
            ("site",),
            _EQUIPMENT_OR_SPACE,
            structural=True,
        ),
        Predicate(
            "hasPart",
            "isPartOf",
            _EQUIPMENT_OR_SPACE,
            _EQUIPMENT_OR_SPACE,
            structural=True,
            brick="brick:hasPart",
        ),
        Predicate(
            "locatedIn",
            "isLocationOf",
            _EQUIPMENT,
            _SPACE,
            structural=True,
            brick="brick:hasLocation",
        ),
        # Une CTA alimente un autre équipement ou directement une zone.
        Predicate("feeds", "isFedBy", _EQUIPMENT, _EQUIPMENT_OR_SPACE, brick="brick:feeds"),
        Predicate("poweredBy", "powers", _EQUIPMENT, _EQUIPMENT),
        Predicate("measuredBy", "measures", _EQUIPMENT_OR_SPACE, _EQUIPMENT),
        Predicate("controlledBy", "controls", _EQUIPMENT, _EQUIPMENT),
        Predicate(
            "connectedTo",
            "connectedTo",
            _EQUIPMENT,
            _EQUIPMENT,
            s223="s223:connectedTo",
        ),
        # Une pièce desservie par une zone CVC qui la dépasse (zone transverse,
        # ADR 011) : la zone, elle, est alimentée par la CTA via « feeds ».
        Predicate("servedBy", "serves", _SPACE, _SPACE),
        Predicate(
            "maintainedBy",
            "maintains",
            ("site", "space", "functional_location", "physical_unit"),
            (),
        ),
        Predicate(
            "dependsOn",
            "isDependencyOf",
            ("site", "space", "functional_location"),
            ("site", "space", "functional_location"),
        ),
        Predicate("protectedBy", "protects", _EQUIPMENT_OR_SPACE, _EQUIPMENT),
    )
}


class VocabularyError(ValueError):
    pass


def check_storable_relation(predicate: str, subject_type: str, object_type: str) -> Predicate:
    """Vérifie qu'une relation peut être enregistrée avec ce vocabulaire.

    Lève VocabularyError avec un message compréhensible sinon.
    """
    definition = PREDICATES.get(predicate)
    if definition is None:
        raise VocabularyError(f"prédicat inconnu : {predicate}")
    if definition.structural:
        raise VocabularyError(
            f"« {predicate} » est déduit de la hiérarchie existante : "
            "modifiez la hiérarchie plutôt que d'ajouter une relation"
        )
    if subject_type not in definition.subject_types:
        raise VocabularyError(f"« {predicate} » n'accepte pas un sujet de type {subject_type}")
    if object_type not in definition.object_types:
        raise VocabularyError(f"« {predicate} » n'accepte pas un objet de type {object_type}")
    return definition
