"""Tests du Virtual Protocol Adapter (ADR 017 §2.2) — palier UNIT_TESTED :
aucun réseau, aucune base, seulement la logique pure de génération de
valeurs. Le palier SIMULATOR_TESTED (via le démon + une API réelle) et
INTEGRATION_TESTED (bout en bout avec le reste de la plateforme) viennent
ensuite, voir incrément 2 de l'ADR 017."""

from datetime import UTC, datetime

import pytest

from app.connectors.virtual_telemetry import (
    PROFILES,
    generate_profile_values,
    generate_value,
    list_profiles,
    profile_points,
)
from app.point_vocabulary import POINT_CLASSES, UNITS, check_point_definition


def test_six_profiles_present() -> None:
    assert list_profiles() == [
        "comptage",
        "cta",
        "groupe_electrogene",
        "groupe_froid",
        "sous_station_thermique",
        "vrv_drv",
    ]


def test_unknown_profile_raises() -> None:
    with pytest.raises(ValueError, match="profil Virtual Commissioning Lab inconnu"):
        profile_points("fictif")


@pytest.mark.parametrize("profile", list_profiles())
def test_every_point_spec_is_valid_against_point_vocabulary(profile: str) -> None:
    """Chaque point simulé doit être un point réellement créable et
    validable (app.points.create_point, app.point_vocabulary) : un profil
    dont un point serait rejeté par le vocabulaire casserait la graine du
    registre (scripts/seed_virtual_site.py) au moment de l'exécution."""
    for spec in profile_points(profile):
        assert spec.point_class in POINT_CLASSES, spec.point_class
        if spec.unit is not None:
            assert spec.unit in UNITS, spec.unit
        # Ne lève pas : classe, type de valeur et unité cohérents entre eux.
        check_point_definition(
            point_class=spec.point_class,
            value_type=spec.value_type,
            unit=spec.unit,
            states=None,
        )


def test_generate_value_is_deterministic_for_same_timestamp() -> None:
    spec = profile_points("cta")[0]
    now = datetime(2026, 10, 1, 14, 30, tzinfo=UTC)
    assert generate_value(spec, now=now) == generate_value(spec, now=now)


def test_generate_value_respects_bounds() -> None:
    spec = next(s for s in profile_points("cta") if s.code_suffix == "t_depart")
    for hour in range(24):
        now = datetime(2026, 10, 1, hour, 0, tzinfo=UTC)
        value = generate_value(spec, now=now)
        assert spec.min_value <= value <= spec.max_value


def test_boolean_point_follows_active_hours() -> None:
    spec = next(s for s in profile_points("cta") if s.code_suffix == "marche_ventilateur")
    assert generate_value(spec, now=datetime(2026, 10, 1, 5, 59, tzinfo=UTC)) is False
    assert generate_value(spec, now=datetime(2026, 10, 1, 6, 0, tzinfo=UTC)) is True
    assert generate_value(spec, now=datetime(2026, 10, 1, 19, 59, tzinfo=UTC)) is True
    assert generate_value(spec, now=datetime(2026, 10, 1, 20, 0, tzinfo=UTC)) is False


def test_boolean_point_without_active_hours_is_always_false() -> None:
    spec = next(s for s in profile_points("cta") if s.code_suffix == "defaut_general")
    assert generate_value(spec, now=datetime(2026, 10, 1, 12, 0, tzinfo=UTC)) is False


def test_cumulative_meter_only_increases_over_time() -> None:
    spec = next(s for s in profile_points("comptage") if s.code_suffix == "energie_active_totale")
    earlier = generate_value(spec, now=datetime(2026, 6, 1, 0, 0, tzinfo=UTC))
    later = generate_value(spec, now=datetime(2026, 6, 1, 6, 0, tzinfo=UTC))
    assert later > earlier


def test_generate_profile_values_covers_every_point_of_the_profile() -> None:
    now = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    values = generate_profile_values("cta", now=now)
    assert set(values) == {spec.code_suffix for spec in PROFILES["cta"]}
