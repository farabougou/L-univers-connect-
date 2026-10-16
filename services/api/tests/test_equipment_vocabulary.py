"""Nomenclature des équipements (ADR 013, étape L5)."""

import pytest

from app.equipment_vocabulary import EQUIPMENT_TYPES, suggest_equipment_type
from app.i18n import load_catalog


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pac", "heat_pump"),
        ("PAC air/eau", "heat_pump"),
        ("Pompe à chaleur réversible", "heat_pump"),
        ("Pompe de circulation", "pump"),
        ("Groupe d'eau glacée", "chiller"),
        ("CTA double flux", "air_handling_unit"),
        ("Aéroréfrigérant sec", "dry_cooler"),
        ("Sous-station réseau de froid", "district_cooling_substation"),
        ("Ventilo-convecteur gainable", "fan_coil_unit"),
        ("Chaudière gaz à condensation", "boiler"),
    ],
)
def test_manufacturer_wording_is_normalized(text, expected) -> None:
    assert suggest_equipment_type(text) == expected


@pytest.mark.parametrize("text", ["", "Machine", "Divers", "Compresseur"])
def test_unknown_wording_gets_no_suggestion(text) -> None:
    """Mieux vaut demander que deviner."""
    assert suggest_equipment_type(text) is None


def test_the_longest_alias_wins() -> None:
    # « pompe à chaleur » contient « pompe » : ce n'est pas une pompe.
    assert suggest_equipment_type("pompe a chaleur") == "heat_pump"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_every_type_has_a_label_and_no_label_is_orphaned(locale) -> None:
    labels = load_catalog(locale, "ui")["equipment_type"]
    assert set(labels) == set(EQUIPMENT_TYPES)


def test_brick_mappings_are_explicit() -> None:
    """Pas d'équivalence inventée : une correspondance absente reste vide."""
    assert EQUIPMENT_TYPES["heat_pump"].brick is None
    assert EQUIPMENT_TYPES["chiller"].brick == "brick:Chiller"
