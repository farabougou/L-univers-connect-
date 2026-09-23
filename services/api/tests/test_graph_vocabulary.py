import pytest

from app.graph_vocabulary import (
    NODE_TYPES,
    PREDICATES,
    VOCABULARY_VERSION,
    VocabularyError,
    check_storable_relation,
)


def test_vocabulary_has_a_version() -> None:
    assert VOCABULARY_VERSION


def test_every_predicate_only_uses_known_node_types() -> None:
    for predicate in PREDICATES.values():
        assert set(predicate.subject_types) <= set(NODE_TYPES), predicate.name
        assert set(predicate.object_types) <= set(NODE_TYPES), predicate.name


def test_every_predicate_has_an_inverse_label() -> None:
    for predicate in PREDICATES.values():
        assert predicate.inverse, predicate.name


def test_feeds_between_two_functional_locations_is_accepted() -> None:
    definition = check_storable_relation("feeds", "functional_location", "functional_location")
    assert definition.inverse == "isFedBy"


def test_unknown_predicate_is_rejected() -> None:
    with pytest.raises(VocabularyError, match="inconnu"):
        check_storable_relation("aime", "functional_location", "functional_location")


def test_structural_predicate_cannot_be_stored() -> None:
    # « hasPart » est déduit de l'arbre des positions : le stocker créerait une
    # seconde source de vérité.
    with pytest.raises(VocabularyError, match="hiérarchie"):
        check_storable_relation("hasPart", "functional_location", "functional_location")


def test_wrong_subject_type_is_rejected() -> None:
    with pytest.raises(VocabularyError, match="sujet"):
        check_storable_relation("feeds", "physical_unit", "functional_location")


def test_maintained_by_is_not_usable_until_organizations_exist() -> None:
    with pytest.raises(VocabularyError, match="objet"):
        check_storable_relation("maintainedBy", "functional_location", "site")
