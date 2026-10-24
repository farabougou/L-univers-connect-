"""Vérificateur du test terrain SDM120 (app/sdm120_check.py) : chaque défaut que le test
terrain doit révéler (mesure perdue, double mesure, confusion d'unité, énergie figée ou qui
recule, valeur inventée pendant une coupure, absence de reprise) a un témoin négatif.
Un vérificateur qui ne sait pas échouer ne prouve rien."""

import re
from datetime import UTC, datetime, timedelta

import pytest

from app.i18n import load_catalog
from app.sdm120_check import (
    FAIL,
    NOT_EVALUATED,
    PASS,
    REQUIRED_FOR_PASS,
    Check,
    Sample,
    Window,
    check_direct_readings,
    check_point_definitions,
    check_series,
    find_gaps,
    render,
    verdict,
)

T0 = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
INTERVAL = 60.0
POWER_W = 500.0
KWH_PER_SAMPLE = POWER_W * INTERVAL / 3_600_000


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def power_series(times, *, value=POWER_W, flags=()):
    return [Sample(at(t), value, tuple(flags)) for t in times]


def energy_series(times, *, scale=1.0, start=1000.0):
    return [Sample(at(t), start + scale * KWH_PER_SAMPLE * (t / INTERVAL)) for t in times]


def regular(first=0, last=1800, step=60):
    return list(range(first, last + 1, step))


def series_checks(power, energy, *, windows=(), end=1800):
    checks = check_series(
        power=power,
        energy=energy,
        interval_seconds=INTERVAL,
        start=at(0),
        end=at(end),
        windows=windows,
    )
    return {c.code: c for c in checks}


def good_direct(**overrides):
    read = {
        "voltage": 231.4,
        "current": 2.37,
        "active_power": 548.0,
        "frequency": 50.0,
        "total_active_energy": 1284.6,
    }
    return {**read, **overrides}


def direct(reads, **kwargs):
    return {c.code: c for c in check_direct_readings(reads, **kwargs)}


# --- Lecture directe -----------------------------------------------------------


def test_trois_lectures_coherentes_sous_charge_resistive_reussissent() -> None:
    reads = [good_direct(), good_direct(), good_direct(total_active_energy=1284.61)]

    checks = direct(reads, resistive_load=True)

    assert all(checks[c].status == PASS for c in checks if c != "DISPLAY_CONCORDANCE")
    assert checks["DISPLAY_CONCORDANCE"].status == NOT_EVALUATED


def test_moins_de_trois_lectures_ou_une_lecture_incomplete_echoue() -> None:
    assert direct([good_direct(), good_direct()])["DIRECT_READS_COMPLETE"].status == FAIL
    partial = {k: v for k, v in good_direct().items() if k != "frequency"}
    assert direct([good_direct(), good_direct(), partial])["DIRECT_READS_COMPLETE"].status == FAIL
    nan = good_direct(voltage=float("nan"))
    assert direct([good_direct(), good_direct(), nan])["DIRECT_READS_COMPLETE"].status == FAIL


@pytest.mark.parametrize(
    ("override", "quantity"),
    [
        ({"voltage": 260.0}, "voltage"),
        ({"voltage": 200.0}, "voltage"),
        ({"frequency": 52.0}, "frequency"),
        ({"current": -1.0}, "current"),
        ({"active_power": 40_000.0}, "active_power"),
    ],
)
def test_une_valeur_hors_limites_est_nommee(override, quantity) -> None:
    reads = [good_direct(), good_direct(), good_direct(**override)]

    check = direct(reads)["DIRECT_VALUES_PLAUSIBLE"]

    assert check.status == FAIL
    assert quantity in check.params["violations"]


def test_une_energie_qui_recule_entre_deux_lectures_echoue() -> None:
    reads = [good_direct(total_active_energy=1284.7), good_direct(total_active_energy=1284.6)] * 2

    assert direct(reads)["DIRECT_VALUES_PLAUSIBLE"].status == FAIL


@pytest.mark.parametrize("wrong_power", [0.548, 548_000.0])
def test_une_puissance_en_kw_ou_en_mw_trahit_une_confusion_d_unite(wrong_power) -> None:
    reads = [good_direct(active_power=wrong_power)] * 3

    assert direct(reads)["POWER_UNIT_COHERENT"].status == FAIL


def test_sans_charge_les_controles_dependants_de_la_charge_ne_sont_pas_evalues() -> None:
    reads = [good_direct(current=0.0, active_power=0.0)] * 3

    checks = direct(reads, resistive_load=True)

    assert checks["POWER_UNIT_COHERENT"].status == NOT_EVALUATED
    assert checks["POWER_EQUALS_V_TIMES_I"].params["reason"] == "NO_LOAD"


def test_p_egal_v_fois_i_n_est_evalue_que_si_la_charge_est_declaree_resistive() -> None:
    reads = [good_direct()] * 3

    assert direct(reads)["POWER_EQUALS_V_TIMES_I"].params["reason"] == "LOAD_NOT_DECLARED_RESISTIVE"


def test_p_different_de_v_fois_i_de_plus_de_5_pour_cent_echoue_sous_charge_resistive() -> None:
    reads = [good_direct(active_power=400.0)] * 3

    assert direct(reads, resistive_load=True)["POWER_EQUALS_V_TIMES_I"].status == FAIL


def test_concordance_avec_l_afficheur_a_1_pour_cent_ou_a_la_resolution_pres() -> None:
    reads = [good_direct()] * 3
    close = {"voltage": 231.2, "current": 2.38, "active_power": 549.0, "frequency": 50.0}
    far = {"voltage": 231.4, "active_power": 600.0}

    assert direct(reads, display=close)["DISPLAY_CONCORDANCE"].status == PASS
    check = direct(reads, display=far)["DISPLAY_CONCORDANCE"]
    assert check.status == FAIL and "active_power" in check.params["deviations"]


# --- Série enregistrée ---------------------------------------------------------


def test_une_serie_complete_et_coherente_reussit_sans_epreuve_de_panne() -> None:
    times = regular()

    checks = series_checks(power_series(times), energy_series(times))

    for code in (
        "NO_MISSING_SAMPLES",
        "NO_DOUBLE_SAMPLING",
        "INTERVAL_RESPECTED",
        "QUALITY_FLAGS_CLEAN",
        "ENERGY_NEVER_DECREASES",
        "ENERGY_MATCHES_POWER",
    ):
        assert checks[code].status == PASS, (code, checks[code].params)
    # Sans coupure déclarée, ces épreuves restent « non évaluées », jamais « réussies ».
    for code in ("NO_LOSS_DURING_API_OUTAGE", "GATEWAY_OUTAGE_HANDLED", "RESTART_RESUMED"):
        assert checks[code].status == NOT_EVALUATED


def test_une_mesure_manquante_hors_coupure_est_detectee() -> None:
    times = [t for t in regular() if t != 900]

    checks = series_checks(power_series(times), energy_series(regular()))

    assert checks["NO_MISSING_SAMPLES"].status == FAIL
    assert checks["NO_MISSING_SAMPLES"].params["missing_power"] == 1
    assert checks["NO_MISSING_SAMPLES"].params["missing_energy"] == 0


def test_une_serie_qui_s_arrete_avant_la_fin_de_l_essai_est_detectee() -> None:
    times = regular(last=1200)

    checks = series_checks(power_series(times), energy_series(times))

    assert checks["NO_MISSING_SAMPLES"].status == FAIL


def test_une_double_mesure_est_detectee() -> None:
    times = sorted(regular() + [905])

    checks = series_checks(power_series(times), energy_series(regular()))

    assert checks["NO_DOUBLE_SAMPLING"].status == FAIL
    assert checks["NO_DOUBLE_SAMPLING"].params["count"] >= 1


def test_un_intervalle_different_de_celui_configure_est_detecte() -> None:
    times = regular(step=120)

    checks = series_checks(power_series(times), energy_series(times))

    assert checks["INTERVAL_RESPECTED"].status == FAIL


def test_un_indicateur_de_qualite_inattendu_echoue() -> None:
    times = regular()

    checks = series_checks(power_series(times, flags=("unvalidated_point",)), energy_series(times))

    assert checks["QUALITY_FLAGS_CLEAN"].status == FAIL
    assert "unvalidated_point" in checks["QUALITY_FLAGS_CLEAN"].params["unexpected"]


def test_late_arrival_n_est_toleree_que_pour_une_mesure_rejouee_apres_coupure_de_l_api() -> None:
    times = regular()
    flagged = [Sample(at(t), POWER_W, ("late_arrival",) if t in (660, 720) else ()) for t in times]
    api = Window("api", at(630), at(780))

    inside = series_checks(flagged, energy_series(times), windows=[api])
    outside = series_checks(flagged, energy_series(times))

    assert inside["QUALITY_FLAGS_CLEAN"].status == PASS
    assert outside["QUALITY_FLAGS_CLEAN"].status == FAIL


def test_une_energie_qui_recule_est_detectee() -> None:
    times = regular()
    energy = energy_series(times)
    energy[15] = Sample(energy[15].at, energy[15].value - 5.0)

    checks = series_checks(power_series(times), energy)

    assert checks["ENERGY_NEVER_DECREASES"].status == FAIL


def test_une_energie_figee_alors_que_la_puissance_n_est_pas_nulle_echoue() -> None:
    """C'est précisément le cas du simulateur statique, utile comme témoin négatif."""
    times = regular()
    frozen = [Sample(at(t), 1284.6) for t in times]

    check = series_checks(power_series(times), frozen)["ENERGY_MATCHES_POWER"]

    assert check.status == FAIL and check.params["reason"] == "ENERGY_FROZEN"


@pytest.mark.parametrize(
    ("scale", "power_value"),
    [
        (1000.0, POWER_W),  # énergie en Wh au lieu de kWh
        (1.0, POWER_W / 1000),  # puissance en kW au lieu de W
    ],
)
def test_une_confusion_d_unite_entre_puissance_et_energie_est_nommee(scale, power_value) -> None:
    times = regular()

    check = series_checks(
        power_series(times, value=power_value), energy_series(times, scale=scale)
    )["ENERGY_MATCHES_POWER"]

    assert check.status == FAIL and check.params["reason"] == "UNIT_FACTOR_SUSPECTED"


def test_energie_dans_la_tolerance_reussit_et_hors_tolerance_echoue() -> None:
    times = regular()

    ok = series_checks(power_series(times), energy_series(times, scale=1.07))
    ko = series_checks(power_series(times), energy_series(times, scale=1.25))

    assert ok["ENERGY_MATCHES_POWER"].status == PASS
    assert ko["ENERGY_MATCHES_POWER"].params["reason"] == "OUT_OF_TOLERANCE"


def test_une_energie_trop_petite_pour_conclure_n_est_pas_evaluee() -> None:
    times = regular(last=120)

    check = series_checks(power_series(times), energy_series(times), end=120)[
        "ENERGY_MATCHES_POWER"
    ]

    assert check.status == NOT_EVALUATED and check.params["reason"] == "ENERGY_TOO_SMALL"


def test_des_series_vides_ne_reussissent_rien() -> None:
    checks = series_checks([], [])

    assert checks["NO_SAMPLES"].status == FAIL
    assert verdict(list(checks.values())) == FAIL


# --- Définition des points -------------------------------------------------------


GOOD_POINTS = {
    "power": {"point_class": "electric_power_sensor", "unit": "W"},
    "energy": {"point_class": "energy_meter_reading", "unit": "kW.h"},
}


def test_les_points_declares_en_w_et_kwh_correspondent_au_compteur() -> None:
    assert check_point_definitions(**GOOD_POINTS).status == PASS


@pytest.mark.parametrize(
    ("side", "field", "value", "flagged"),
    [
        ("power", "unit", "kW", "power.unit"),  # accepté par le vocabulaire, faux pour le compteur
        ("energy", "unit", "W.h", "energy.unit"),
        ("power", "point_class", "energy_meter_reading", "power.point_class"),
        ("energy", "point_class", None, "energy.point_class"),
    ],
)
def test_une_unite_ou_une_classe_de_point_qui_ne_correspond_pas_au_compteur_echoue(
    side, field, value, flagged
) -> None:
    points = {**GOOD_POINTS, side: {**GOOD_POINTS[side], field: value}}

    check = check_point_definitions(**points)

    assert check.status == FAIL and flagged in check.params["mismatches"]


# --- Coupure de l'API ------------------------------------------------------------


def test_coupure_de_l_api_toutes_les_mesures_rejouees_aucune_perte() -> None:
    times = regular()
    api = Window("api", at(600), at(900))

    check = series_checks(power_series(times), energy_series(times), windows=[api])[
        "NO_LOSS_DURING_API_OUTAGE"
    ]

    assert check.status == PASS and check.params["replayed"] == 6


def test_coupure_de_l_api_avec_mesures_perdues_est_detectee() -> None:
    """Ancien comportement du démon : sans API, le compteur n'était plus relevé."""
    lost = [t for t in regular() if not 600 < t < 900]
    api = Window("api", at(600), at(900))

    checks = series_checks(power_series(lost), energy_series(lost), windows=[api])

    assert checks["NO_LOSS_DURING_API_OUTAGE"].status == FAIL
    assert checks["NO_LOSS_DURING_API_OUTAGE"].params["lost"] == 4 * 2
    # Une perte pendant la coupure de l'API ne se cache pas dans la complétude générale.
    assert checks["NO_MISSING_SAMPLES"].status == PASS


def test_coupure_de_l_api_sans_aucune_mesure_datee_de_la_coupure_echoue() -> None:
    lost = [t for t in regular() if not 570 < t < 930]
    api = Window("api", at(600), at(900))

    check = series_checks(power_series(lost), energy_series(lost), windows=[api])[
        "NO_LOSS_DURING_API_OUTAGE"
    ]

    assert check.status == FAIL


# --- Coupure de la passerelle ----------------------------------------------------


def test_coupure_de_la_passerelle_sans_valeur_inventee_et_reprise_reussit() -> None:
    times = [t for t in regular() if not 600 < t < 900]
    gateway = Window("gateway", at(600), at(900))

    checks = series_checks(power_series(times), energy_series(times), windows=[gateway])

    assert checks["GATEWAY_OUTAGE_HANDLED"].status == PASS
    # L'absence de mesure pendant la coupure est attendue, pas une perte.
    assert checks["NO_MISSING_SAMPLES"].status == PASS


def test_reprise_lente_de_la_passerelle_dans_les_deux_intervalles_est_toleree() -> None:
    times = [t for t in regular() if not 600 < t < 1020]
    gateway = Window("gateway", at(600), at(900))

    checks = series_checks(power_series(times), energy_series(times), windows=[gateway])

    assert checks["GATEWAY_OUTAGE_HANDLED"].status == PASS
    assert checks["NO_MISSING_SAMPLES"].status == PASS


def test_une_mesure_enregistree_pendant_la_coupure_de_la_passerelle_est_une_valeur_inventee() -> (
    None
):
    gateway = Window("gateway", at(600), at(900))

    check = series_checks(power_series(regular()), energy_series(regular()), windows=[gateway])[
        "GATEWAY_OUTAGE_HANDLED"
    ]

    assert check.status == FAIL and check.params["invented"] >= 1


def test_une_heure_de_fin_notee_trop_tard_n_est_pas_prise_pour_une_valeur_inventee() -> None:
    """Constaté lors de la répétition réelle : l'opérateur note l'heure de fin de coupure à la
    main, parfois après la première relève réussie."""
    times = [t for t in regular() if not 600 < t < 840]  # reprise réelle à 840
    gateway = Window("gateway", at(600), at(870))  # fin notée 30 s trop tard

    check = series_checks(power_series(times), energy_series(times), windows=[gateway])[
        "GATEWAY_OUTAGE_HANDLED"
    ]

    assert check.status == PASS


def test_une_passerelle_qui_ne_reprend_pas_est_detectee() -> None:
    times = [t for t in regular() if t <= 600]
    gateway = Window("gateway", at(600), at(900))

    check = series_checks(power_series(times), energy_series(times), windows=[gateway])[
        "GATEWAY_OUTAGE_HANDLED"
    ]

    assert check.status == FAIL and check.params["not_resumed"] == 1


# --- Redémarrage du démon ---------------------------------------------------------


def test_redemarrage_du_demon_reprise_sans_doublon_reussit() -> None:
    times = [t for t in regular() if not 600 < t <= 780] + [782]
    stop = Window("daemon", at(600), at(780))

    checks = series_checks(power_series(times), energy_series(times), windows=[stop])

    assert checks["RESTART_RESUMED"].status == PASS
    assert checks["NO_DOUBLE_SAMPLING"].status == PASS
    assert checks["NO_MISSING_SAMPLES"].status == PASS


def test_un_demon_qui_ne_reprend_pas_apres_redemarrage_est_detecte() -> None:
    times = [t for t in regular() if t <= 600]
    stop = Window("daemon", at(600), at(780))

    assert (
        series_checks(power_series(times), energy_series(times), windows=[stop])[
            "RESTART_RESUMED"
        ].status
        == FAIL
    )


def test_un_redemarrage_qui_remet_l_energie_en_arriere_est_detecte() -> None:
    times = [t for t in regular() if not 600 < t < 780]
    energy = energy_series(times)
    after = [i for i, s in enumerate(energy) if s.at >= at(780)]
    for index in after:
        energy[index] = Sample(energy[index].at, energy[index].value - 3.0)
    stop = Window("daemon", at(600), at(780))

    check = series_checks(power_series(times), energy, windows=[stop])["RESTART_RESUMED"]

    assert check.status == FAIL and check.params["energy_dropped"] >= 1


# --- Fenêtres et verdict ------------------------------------------------------------


def test_une_coupure_mal_declaree_est_refusee() -> None:
    with pytest.raises(ValueError):
        Window("reseau", at(0), at(10))
    with pytest.raises(ValueError):
        Window("api", at(10), at(10))


def full_scenario_checks(**direct_overrides):
    """Essai complet : une coupure de chaque type et un redémarrage."""
    times = [t for t in regular(last=3000) if not (1200 < t < 1500) and not (2100 < t < 2280)]
    windows = [
        Window("api", at(600), at(900)),
        Window("gateway", at(1200), at(1500)),
        Window("daemon", at(2100), at(2280)),
    ]
    reads = [good_direct(**direct_overrides)] * 3
    return (
        check_direct_readings(reads, resistive_load=True, display={"voltage": 231.4})
        + [check_point_definitions(**GOOD_POINTS)]
        + check_series(
            power=power_series(times),
            energy=energy_series(times),
            interval_seconds=INTERVAL,
            start=at(0),
            end=at(3000),
            windows=windows,
        )
    )


def test_le_verdict_est_pass_quand_tout_est_evalue_et_reussi() -> None:
    checks = full_scenario_checks()

    assert {c.code for c in checks} >= set(REQUIRED_FOR_PASS)
    assert [c for c in checks if c.status == FAIL] == []
    assert verdict(checks) == PASS


def test_un_seul_echec_donne_fail_meme_si_le_reste_reussit() -> None:
    assert verdict(full_scenario_checks(voltage=260.0)) == FAIL


def test_un_controle_non_evalue_donne_incomplete_jamais_pass() -> None:
    checks = [c for c in full_scenario_checks() if c.code != "GATEWAY_OUTAGE_HANDLED"]
    checks.append(Check("GATEWAY_OUTAGE_HANDLED", NOT_EVALUATED, {"reason": "NO_OUTAGE_DECLARED"}))

    assert verdict(checks) == "INCOMPLETE"


# --- Catalogues et affichage ---------------------------------------------------------


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", text))


def test_les_catalogues_francais_et_anglais_ont_les_memes_cles_et_les_memes_champs() -> None:
    fr, en = (load_catalog(locale, "sdm120_check") for locale in ("fr", "en"))

    for section in ("statuses", "checks", "details", "reasons", "notes"):
        assert fr[section].keys() == en[section].keys(), section
    for section in ("checks", "details", "reasons", "notes"):
        for key, message in fr[section].items():
            assert _placeholders(message) == _placeholders(en[section][key]), key
    assert fr["details"].keys() == fr["checks"].keys(), "un détail par contrôle"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_tous_les_controles_emis_s_affichent_dans_les_deux_langues(locale) -> None:
    batteries = [
        full_scenario_checks(),
        full_scenario_checks(voltage=260.0, active_power=0.5),
        check_direct_readings([good_direct()]),
        check_direct_readings([good_direct(current=0.0, active_power=0.0)] * 3),
        check_series(
            power=power_series(regular()),
            energy=[Sample(at(t), 1284.6) for t in regular()],
            interval_seconds=INTERVAL,
            start=at(0),
            end=at(1800),
            windows=[Window("api", at(600), at(900)), Window("gateway", at(1200), at(1500))],
        ),
        check_series(power=[], energy=[], interval_seconds=INTERVAL, start=at(0), end=at(1800)),
        check_series(
            power=power_series(regular(last=120)),
            energy=energy_series(regular(last=120)),
            interval_seconds=INTERVAL,
            start=at(0),
            end=at(120),
        ),
    ]

    for check in (c for battery in batteries for c in battery):
        text = render(check, locale)
        assert "{" not in text and "}" not in text, (check.code, text)
        assert text.startswith("["), text


def test_la_phrase_est_produite_a_l_affichage_dans_la_langue_demandee() -> None:
    check = Check("NO_MISSING_SAMPLES", FAIL, {"missing_power": 2, "missing_energy": 0})

    fr = render(check, "fr")
    en = render(check, "en")

    assert "Échec" in fr and "2 de puissance" in fr
    assert "Failed" in en and "2 power" in en
    # Les nombres décimaux suivent l'usage de la langue.
    assert "0,25" in render(
        Check(
            "ENERGY_MATCHES_POWER",
            FAIL,
            {"measured_kwh": 0.25, "expected_kwh": 0.5, "reason": None},
        ),
        "fr",
    )


def test_les_trous_sont_listes_pour_etre_rapproches_des_notes_de_coupure() -> None:
    samples = power_series([t for t in regular() if not 600 < t < 900])

    gaps = find_gaps(samples, INTERVAL)

    assert gaps == [(at(600), at(900), 4)]
    assert find_gaps(power_series(regular()), INTERVAL) == []
