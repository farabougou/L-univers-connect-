"""Test de charge borné (app/load_probe.py, scripts/load_probe.py) : les critères
d'arrêt, les bornes et le verdict de retour à la normale, avec un serveur factice
dont la capacité est connue. Le réseau réel n'est pas utilisé."""

import asyncio
import importlib.util
import pathlib
from collections import Counter

import pytest

from app.load_probe import (
    Criteria,
    StepResult,
    classify,
    percentile,
    recovery_verdict,
    run_probe,
    stop_reason,
)

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "load_probe.py"


def _step(statuses: dict[str, int], latencies: list[float] | None = None, clients: int = 1):
    return StepResult(
        concurrency=clients,
        seconds=1.0,
        latencies=latencies if latencies is not None else [0.01] * sum(statuses.values()),
        statuses=Counter(statuses),
    )


# --- Mesures ------------------------------------------------------------


def test_le_percentile_est_une_valeur_observee_au_rang_le_plus_proche() -> None:
    values = [float(n) for n in range(1, 101)]

    assert percentile(values, 0.50) == 50.0
    assert percentile(values, 0.95) == 95.0
    assert percentile(values, 0.99) == 99.0
    assert percentile([0.2], 0.99) == 0.2
    assert percentile([], 0.99) == 0.0


@pytest.mark.parametrize(
    ("status", "label"),
    [
        (200, "2xx"),
        (204, "2xx"),
        (429, "429"),
        (500, "500"),
        (502, "502"),
        (503, "503"),
        (504, "504"),
        (404, "4xx"),
        (301, "autre"),
        (None, "reseau"),
    ],
)
def test_classification_des_statuts(status, label) -> None:
    assert classify(status) == label


# --- Critères d'arrêt ---------------------------------------------------


def test_un_palier_sain_ne_declenche_aucun_arret() -> None:
    assert stop_reason(_step({"2xx": 100}), Criteria()) is None


def test_un_evenement_isole_n_arrete_pas_la_montee_sur_un_petit_echantillon() -> None:
    # 1 erreur sur 80 requêtes = 1,25 % : au-dessus du seuil, mais sans preuve de saturation.
    assert stop_reason(_step({"2xx": 79, "reseau": 1}), Criteria()) is None
    assert stop_reason(_step({"2xx": 79, "503": 1}), Criteria(max_shed_rate=0.0)) is None
    assert stop_reason(_step({"2xx": 79, "429": 1}), Criteria(max_limited_rate=0.0)) is None
    # Dès que l'événement se répète, le critère s'applique.
    assert "erreurs" in stop_reason(_step({"2xx": 77, "reseau": 3}), Criteria())


def test_des_erreurs_serveur_ou_reseau_arretent_la_montee() -> None:
    assert "erreurs" in stop_reason(_step({"2xx": 90, "500": 10}), Criteria())
    assert "erreurs" in stop_reason(_step({"2xx": 90, "reseau": 10}), Criteria())


def test_un_refus_503_est_une_saturation_pas_une_erreur() -> None:
    reason = stop_reason(_step({"2xx": 90, "503": 10}), Criteria())

    assert "saturation" in reason


def test_un_seuil_de_503_inferieur_a_la_tolerance_laisse_continuer() -> None:
    assert stop_reason(_step({"2xx": 98, "503": 2}), Criteria()) is None


def test_la_limitation_429_arrete_car_elle_ne_mesure_plus_la_capacite() -> None:
    assert "429" in stop_reason(_step({"2xx": 80, "429": 20}), Criteria())


def test_une_latence_p99_trop_haute_arrete() -> None:
    step = _step({"2xx": 100}, latencies=[0.1] * 98 + [9.0, 9.0])

    assert "p99" in stop_reason(step, Criteria(max_p99_seconds=5.0))


# --- Retour à la normale -----------------------------------------------


def test_la_reprise_est_reussie_si_la_latence_revient_et_sans_echec() -> None:
    baseline = _step({"2xx": 50}, latencies=[0.020] * 50)
    recovery = _step({"2xx": 50}, latencies=[0.030] * 50)

    assert recovery_verdict(baseline, recovery).ok


def test_la_reprise_echoue_si_des_requetes_sont_encore_refusees() -> None:
    baseline = _step({"2xx": 50})
    recovery = _step({"2xx": 45, "503": 5})

    verdict = recovery_verdict(baseline, recovery)

    assert not verdict.ok and "échec" in verdict.reason


def test_la_reprise_echoue_si_la_latence_reste_degradee() -> None:
    baseline = _step({"2xx": 50}, latencies=[0.020] * 50)
    recovery = _step({"2xx": 50}, latencies=[0.500] * 50)

    assert not recovery_verdict(baseline, recovery).ok


def test_une_reprise_sans_requete_n_est_jamais_un_succes() -> None:
    assert not recovery_verdict(_step({"2xx": 10}), _step({})).ok


# --- Montée complète sur un serveur factice de capacité connue ---------


def _server(capacity: int, latency: float = 0.01, degraded: bool = False):
    """Au plus `capacity` requêtes en cours ; les autres sont refusées en 503."""
    in_flight = 0

    async def send():
        nonlocal in_flight
        if in_flight >= capacity:
            return 503, 0.001
        in_flight += 1
        try:
            await asyncio.sleep(latency * (30 if degraded else 1))
        finally:
            in_flight -= 1
        return 200, latency * (30 if degraded else 1)

    return send


def test_la_montee_s_arrete_a_la_saturation_sans_atteindre_les_paliers_suivants() -> None:
    report = asyncio.run(
        run_probe(
            _server(capacity=4),
            levels=[1, 2, 4, 8, 16, 32],
            step_seconds=0.25,
            recovery_seconds=0.25,
        )
    )

    assert report.stopped_because and "saturation" in report.stopped_because
    reached = [step.concurrency for step in report.steps]
    assert reached[-1] == 8, "le premier palier au-dessus de la capacité déclenche l'arrêt"
    assert 16 not in reached and 32 not in reached
    assert report.verdict.ok, report.verdict.reason


def test_la_charge_est_bornee_par_le_nombre_total_de_requetes() -> None:
    report = asyncio.run(
        run_probe(
            _server(capacity=1000, latency=0.001),
            levels=[1, 2, 4, 8],
            step_seconds=0.2,
            recovery_seconds=0.1,
            criteria=Criteria(max_total_requests=50),
        )
    )

    assert report.reached_limit and "plafond" in report.reached_limit
    assert len(report.steps) < 4


def test_un_serveur_qui_ne_revient_pas_a_la_normale_est_signale() -> None:
    state = {"calls": 0}
    healthy = _server(capacity=4)
    degraded = _server(capacity=4, degraded=True)

    async def send():
        state["calls"] += 1
        # sain pendant la montée, durablement dégradé ensuite
        return await (healthy() if state["calls"] < 120 else degraded())

    report = asyncio.run(run_probe(send, levels=[1, 8], step_seconds=0.25, recovery_seconds=0.4))

    assert report.verdict is not None and not report.verdict.ok


# --- Garde-fous du script ----------------------------------------------


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("load_probe_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("url", "local"),
    [
        ("http://127.0.0.1:8000", True),
        ("http://localhost:8000", True),
        ("http://[::1]:8000", True),
        ("https://l-univers-connect-staging.up.railway.app", False),
        ("http://10.0.0.5:8000", False),
    ],
)
def test_une_cible_distante_est_reconnue(script, url, local) -> None:
    assert script.is_local(url) is local


def test_les_paliers_sont_bornes_et_croissants(script) -> None:
    import argparse

    assert script.parse_levels("1,5,10") == [1, 5, 10]
    for bad in ("", "0", "500", "10,5", "a"):
        with pytest.raises((argparse.ArgumentTypeError, ValueError)):
            script.parse_levels(bad)


def test_le_rapport_nomme_le_type_des_erreurs_reseau(script) -> None:
    report = asyncio.run(
        run_probe(_server(capacity=1000), levels=[1], step_seconds=0.1, recovery_seconds=0.1)
    )
    errors = Counter({"ReadTimeout": 2, "ConnectError": 1})

    text = script.render(report, "cible", errors)
    data = script.to_json(report, "cible", errors)

    assert "ReadTimeout ×2" in text and "ConnectError ×1" in text
    assert data["erreurs_reseau"] == {"ReadTimeout": 2, "ConnectError": 1}
    assert "Erreurs réseau" not in script.render(report, "cible")
