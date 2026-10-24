"""Tests du Virtual Protocol Adapter (ADR 017 §2.2) — palier UNIT_TESTED :
aucun réseau, aucune base, seulement la logique pure de génération de
valeurs. Le palier FAILURE_TESTED (scénarios de panne contre la vraie règle
FDD) vit dans tests/test_virtual_telemetry_failure_scenarios.py."""

from datetime import UTC, datetime, timedelta

import pytest

from app.connectors.virtual_telemetry import (
    PROFILES,
    communication_loss_scenario,
    failure_scenario,
    generate_profile_values,
    generate_value,
    list_failure_scenarios,
    list_profiles,
    profile_points,
)
from app.point_vocabulary import POINT_CLASSES, UNITS, check_point_definition


def test_seven_profiles_present() -> None:
    assert list_profiles() == [
        "comptage",
        "cta",
        "groupe_electrogene",
        "groupe_froid",
        "pompe",
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


# --- Scénarios de panne (ADR 017 §2.2, incrément 2) ---


def test_list_failure_scenarios_includes_communication_loss_for_every_profile() -> None:
    for profile in list_profiles():
        assert "perte_communication" in list_failure_scenarios(profile)


def test_unknown_failure_scenario_raises() -> None:
    with pytest.raises(ValueError, match="scénario de panne inconnu"):
        failure_scenario("cta", "fictif")


def test_failure_scenario_scoped_to_another_profile_is_rejected() -> None:
    """Un scénario nommé "vanne_bloquee" n'a de sens que pour "cta" (c'est le
    seul profil qui a une vanne chaude) : le demander pour un autre profil
    est une erreur, jamais un scénario silencieusement vide."""
    with pytest.raises(ValueError, match="scénario de panne inconnu"):
        failure_scenario("groupe_froid", "vanne_bloquee")


def test_stuck_valve_overrides_ignore_normal_bounds_and_time() -> None:
    scenario = failure_scenario("cta", "vanne_bloquee")
    for hour in (0, 6, 12, 18):
        now = datetime(2026, 10, 1, hour, 0, tzinfo=UTC)
        values = generate_profile_values("cta", now=now, scenario=scenario)
        assert values["vanne_chaude"] == 80.0


def test_simultaneous_heating_cooling_scenario_opens_both_valves() -> None:
    scenario = failure_scenario("cta", "chauffage_froid_simultane")
    now = datetime(2026, 10, 1, 14, 0, tzinfo=UTC)
    values = generate_profile_values("cta", now=now, scenario=scenario)
    assert values["vanne_chaude"] > 0
    assert values["vanne_froide"] > 0


def test_drift_scenario_requires_start_time() -> None:
    scenario = failure_scenario("cta", "capteur_derive")
    with pytest.raises(ValueError, match="scenario_started_at est requis"):
        generate_profile_values(
            "cta", now=datetime(2026, 10, 1, 10, 0, tzinfo=UTC), scenario=scenario
        )


def test_drift_scenario_moves_the_value_outside_the_normal_band_over_time() -> None:
    scenario = failure_scenario("cta", "capteur_derive")
    started_at = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    spec = next(s for s in profile_points("cta") if s.code_suffix == "t_depart")

    just_started = generate_profile_values(
        "cta", now=started_at, scenario=scenario, scenario_started_at=started_at
    )
    assert spec.min_value <= just_started["t_depart"] <= spec.max_value

    later = generate_profile_values(
        "cta",
        now=started_at + timedelta(hours=5),
        scenario=scenario,
        scenario_started_at=started_at,
    )
    # +4°C/heure pendant 5h (+20°C, bien au-delà du cycle jour/nuit +/-1.5°C
    # et du bruit +/-0.2°C) : largement hors de la plage normale (10-30°C),
    # une vraie dérive de capteur n'est jamais plafonnée artificiellement.
    assert later["t_depart"] > spec.max_value


def test_communication_loss_scenario_omits_every_point_of_the_profile() -> None:
    scenario = communication_loss_scenario("groupe_froid")
    now = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    values = generate_profile_values("groupe_froid", now=now, scenario=scenario)
    assert values == {}


def test_stuck_economizer_damper_overrides_ignore_normal_modulation() -> None:
    scenario = failure_scenario("cta", "economiseur_bloque")
    for hour in (0, 6, 12, 18):
        now = datetime(2026, 10, 1, hour, 0, tzinfo=UTC)
        values = generate_profile_values("cta", now=now, scenario=scenario)
        assert values["volet_air_neuf"] == 5.0


def test_low_pressure_scenario_overrides_pump_discharge_pressure() -> None:
    scenario = failure_scenario("pompe", "cavitation")
    now = datetime(2026, 10, 1, 14, 0, tzinfo=UTC)
    values = generate_profile_values("pompe", now=now, scenario=scenario)
    assert values["pression_refoulement"] == 0.4


def test_pump_power_draw_drift_moves_outside_the_normal_band_over_time() -> None:
    scenario = failure_scenario("pompe", "derive_puissance")
    started_at = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    later = generate_profile_values(
        "pompe",
        now=started_at + timedelta(hours=10),
        scenario=scenario,
        scenario_started_at=started_at,
    )
    # +0.3 kW/heure pendant 10h (+3 kW) : largement au-delà du bruit et de la
    # variation jour/nuit (+/-0.5 kW) de la puissance absorbée saine.
    assert later["puissance_absorbee"] > 7.0


def test_chiller_return_overheat_scenario_overrides_return_temperature() -> None:
    scenario = failure_scenario("groupe_froid", "surchauffe_retour")
    now = datetime(2026, 10, 1, 14, 0, tzinfo=UTC)
    values = generate_profile_values("groupe_froid", now=now, scenario=scenario)
    assert values["t_eau_glacee_retour"] == 22.0


def test_chiller_exchanger_drift_moves_outside_the_normal_band_over_time() -> None:
    scenario = failure_scenario("groupe_froid", "derive_echangeur")
    started_at = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    spec = next(s for s in profile_points("groupe_froid") if s.code_suffix == "t_eau_glacee_depart")
    later = generate_profile_values(
        "groupe_froid",
        now=started_at + timedelta(hours=20),
        scenario=scenario,
        scenario_started_at=started_at,
    )
    assert later["t_eau_glacee_depart"] > spec.max_value


def test_incoherent_meter_reading_scenario_overrides_with_an_impossible_value() -> None:
    """Valeur incohérente (02/10/2026, demande explicite de Mohamed) : un
    compteur de consommation ne peut pas renvoyer une puissance négative —
    distinct d'une dérive progressive, c'est une valeur immédiatement
    impossible, jamais une tendance à extrapoler."""
    scenario = failure_scenario("comptage", "releve_incoherent")
    now = datetime(2026, 10, 1, 14, 0, tzinfo=UTC)
    values = generate_profile_values("comptage", now=now, scenario=scenario)
    assert values["puissance_active"] == -500.0


def test_other_profile_points_are_unaffected_by_a_scenario() -> None:
    """Un scénario qui ne mentionne que deux points (les vannes) laisse les
    autres points du même profil générer leur valeur normale — jamais une
    panne qui, par effet de bord, en supprime ou n'en fige d'autres."""
    scenario = failure_scenario("cta", "vanne_bloquee")
    now = datetime(2026, 10, 1, 14, 0, tzinfo=UTC)
    with_scenario = generate_profile_values("cta", now=now, scenario=scenario)
    without_scenario = generate_profile_values("cta", now=now)
    for suffix in ("t_depart", "pression_refoulement", "consigne_depart", "defaut_general"):
        assert with_scenario[suffix] == without_scenario[suffix]
