"""Vocabulaire interne versionné du graphe d'actifs (ADR 012, section 2.2).

Aligné sur les standards sans en dépendre : chaque prédicat indique sa
correspondance connue dans Brick Schema ou ASHRAE 223P, et `None` quand aucune
correspondance n'a été vérifiée (mieux vaut l'absence qu'une correspondance
inventée). Un seul sens est stocké ; l'inverse est seulement affiché.

Modifier ce vocabulaire (ajout, retrait, changement de domaine) impose de
changer VOCABULARY_VERSION : chaque relation garde la version sous laquelle
elle a été créée.
"""

from dataclasses import dataclass

VOCABULARY_VERSION = "2026-09-23.1"

# Types de nœuds existants à ce jour. Les types futurs (space, point,
# edge_device, organization) seront ajoutés avec leurs tables respectives,
# ainsi que « locatedIn », déduit de l'arbre spatial (étape F2).
NODE_TYPES = ("site", "functional_location", "physical_unit")


@dataclass(frozen=True)
class Predicate:
    name: str
    inverse: str
    subject_types: tuple[str, ...]
    object_types: tuple[str, ...]
    # Déduit des arbres (colonnes parent_id, site_id...) : jamais stocké dans
    # la table relations, pour garder une seule source de vérité.
    structural: bool = False
    brick: str | None = None
    s223: str | None = None


_EQUIPMENT = ("functional_location",)

PREDICATES: dict[str, Predicate] = {
    p.name: p
    for p in (
        Predicate(
            "contains",
            "isContainedIn",
            ("site",),
            ("functional_location",),
            structural=True,
        ),
        Predicate(
            "hasPart",
            "isPartOf",
            _EQUIPMENT,
            _EQUIPMENT,
            structural=True,
            brick="brick:hasPart",
        ),
        Predicate("feeds", "isFedBy", _EQUIPMENT, _EQUIPMENT, brick="brick:feeds"),
        Predicate("poweredBy", "powers", _EQUIPMENT, _EQUIPMENT),
        Predicate("measuredBy", "measures", _EQUIPMENT, _EQUIPMENT),
        Predicate("controlledBy", "controls", _EQUIPMENT, _EQUIPMENT),
        Predicate(
            "connectedTo",
            "connectedTo",
            _EQUIPMENT,
            _EQUIPMENT,
            s223="s223:connectedTo",
        ),
        Predicate("servedBy", "serves", _EQUIPMENT, _EQUIPMENT),
        Predicate(
            "maintainedBy",
            "maintains",
            ("site", "functional_location", "physical_unit"),
            (),
        ),
        Predicate(
            "dependsOn",
            "isDependencyOf",
            ("site", "functional_location"),
            ("site", "functional_location"),
        ),
        Predicate("protectedBy", "protects", _EQUIPMENT, _EQUIPMENT),
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
