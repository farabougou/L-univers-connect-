"""Commandes du test terrain SDM120 : scripts/sdm120_preflight.py (lecture directe) et
scripts/sdm120_verify.py (vérification en base). Simulateur Modbus et base réels, aucun
Internet. La répétition complète (lecture directe, essai avec trois coupures, verdict) est
le test de bout en bout de la procédure de docs/terrain/test-terrain-sdm120.md."""

import argparse
import json
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pymodbus.server import ServerStop, StartTcpServer
from sqlalchemy import text

from app.db import engine
from app.points import create_point
from app.tenancy import set_tenant_context
from scripts import sdm120_preflight, sdm120_verify
from scripts.modbus_simulator import build_context
from tests.modbus_fixtures import cleanup_tenant, create_tenant_with_energy_and_power_points

PORT = 5098
T0 = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
INTERVAL = 60
KWH_PER_SAMPLE = 548.0 * INTERVAL / 3_600_000


@pytest.fixture(scope="module", autouse=True)
def modbus_simulator():
    thread = threading.Thread(
        target=StartTcpServer,
        args=(build_context(),),
        kwargs={"address": ("127.0.0.1", PORT)},
        daemon=True,
    )
    thread.start()
    time.sleep(0.5)
    yield
    ServerStop()
    thread.join(timeout=2)


@pytest.fixture
def tenant():
    created = create_tenant_with_energy_and_power_points("ClientSdm120Verify")
    yield created
    cleanup_tenant(created)


def stamp(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def insert_run(tenant, times, *, late_between=None, power_point=None):
    """Enregistre la relève simulée d'un SDM120 à 548 W aux instants `times` (secondes)."""
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        for index, seconds in enumerate(times):
            measured = stamp(seconds)
            late = late_between and late_between[0] <= seconds <= late_between[1]
            received = stamp(late_between[1] + 5) if late else measured
            flags = ["late_arrival"] if late else []
            for point, value in (
                (power_point or tenant["power_point_id"], 548.0),
                (tenant["energy_point_id"], 1000.0 + KWH_PER_SAMPLE * (seconds / INTERVAL)),
            ):
                connection.execute(
                    text(
                        "INSERT INTO measurements (point_id, measured_at, tenant_id, value, "
                        "origin, source, quality_flags, received_at) VALUES (:point, :at, :tenant, "
                        ":value, 'measured', 'edge:test', CAST(:flags AS text[]), :received)"
                    ),
                    {
                        "point": point,
                        "at": measured,
                        "tenant": tenant["tenant_id"],
                        "value": value,
                        "flags": flags,
                        "received": received,
                    },
                )


def iso(seconds: float) -> str:
    return stamp(seconds).strftime("%Y-%m-%dT%H:%M:%SZ")


def verify_args(tenant, direct_json, *outages, end=3000, extra=()):
    args = [
        "--tenant", str(tenant["tenant_id"]),
        "--power-point", str(tenant["power_point_id"]),
        "--energy-point", str(tenant["energy_point_id"]),
        "--start", iso(0),
        "--end", iso(end),
        "--interval", str(INTERVAL),
        "--direct-json", str(direct_json),
    ]  # fmt: skip
    for kind, start, stop in outages:
        args += ["--outage", f"{kind}={iso(start)},{iso(stop)}"]
    return [*args, *extra]


def run_preflight(tmp_path, *extra):
    out = tmp_path / "lecture-directe.json"
    code = sdm120_preflight.main(
        ["--host", "127.0.0.1", "--port", str(PORT), "--pause", "0", "--json-out", str(out), *extra]
    )
    return code, out


# --- Analyse des arguments -----------------------------------------------------------


def test_une_heure_sans_fuseau_est_refusee() -> None:
    assert sdm120_verify.parse_instant("2026-10-21T09:00:00Z") == stamp(0)
    assert sdm120_verify.parse_instant("2026-10-21T10:00:00+01:00") == stamp(0)
    with pytest.raises(argparse.ArgumentTypeError):
        sdm120_verify.parse_instant("2026-10-21T09:00:00")
    with pytest.raises(argparse.ArgumentTypeError):
        sdm120_verify.parse_instant("hier")


@pytest.mark.parametrize(
    "raw",
    [
        "api=2026-10-21T09:10:00Z",  # sans fin
        "reseau=2026-10-21T09:10:00Z,2026-10-21T09:15:00Z",  # type inconnu
        "api=2026-10-21T09:15:00Z,2026-10-21T09:10:00Z",  # fin avant début
        "2026-10-21T09:10:00Z,2026-10-21T09:15:00Z",  # sans type
    ],
)
def test_une_coupure_mal_ecrite_est_refusee(raw) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        sdm120_verify.parse_outage(raw)


def test_les_valeurs_de_l_afficheur_sont_lues_avec_virgule_ou_point() -> None:
    assert sdm120_preflight.parse_display("voltage=231,2") == ("voltage", 231.2)
    assert sdm120_preflight.parse_display("current=2.38") == ("current", 2.38)
    with pytest.raises(argparse.ArgumentTypeError):
        sdm120_preflight.parse_display("tension=231")
    with pytest.raises(argparse.ArgumentTypeError):
        sdm120_preflight.parse_display("voltage=abc")


# --- Lecture directe -----------------------------------------------------------------


def test_lecture_directe_du_simulateur_reussit_et_laisse_une_preuve(tmp_path, capsys) -> None:
    code, out = run_preflight(tmp_path, "--resistive-load", "--display", "voltage=231,4")

    assert code == 0
    evidence = json.loads(out.read_text("utf-8"))
    assert evidence["kind"] == "sdm120_direct"
    assert len(evidence["reads"]) == 3
    statuses = {c["code"]: c["status"] for c in evidence["checks"]}
    assert statuses["DIRECT_READS_COMPLETE"] == "PASS"
    assert statuses["POWER_EQUALS_V_TIMES_I"] == "PASS"
    assert "Lecture seule" in capsys.readouterr().out


def test_un_afficheur_qui_ne_concorde_pas_donne_un_echec(tmp_path) -> None:
    code, _ = run_preflight(tmp_path, "--display", "active_power=900")

    assert code == 1


def test_un_compteur_injoignable_donne_le_code_2_sans_trace_d_erreur(tmp_path, capsys) -> None:
    code = sdm120_preflight.main(["--host", "127.0.0.1", "--port", "1", "--pause", "0"])

    assert code == 2
    assert "Lecture impossible" in capsys.readouterr().err


def test_moins_de_trois_lectures_est_refuse() -> None:
    with pytest.raises(SystemExit):
        sdm120_preflight.main(["--host", "127.0.0.1", "--reads", "2"])


# --- Vérification en base : répétition complète --------------------------------------


API = ("api", 600, 900)
GATEWAY = ("gateway", 1200, 1500)
DAEMON = ("daemon", 2100, 2280)


def full_run_times(*, lose_api_window=False):
    times = [
        t for t in range(0, 3001, INTERVAL) if not (1200 < t < 1500) and not (2100 < t <= 2280)
    ] + [2282]
    if lose_api_window:
        times = [t for t in times if not 600 < t < 900]
    return sorted(times)


def test_repetition_complete_avec_trois_coupures_donne_pass(tmp_path, tenant, capsys) -> None:
    code, direct = run_preflight(tmp_path, "--resistive-load", "--display", "voltage=231,4")
    assert code == 0
    insert_run(tenant, full_run_times(), late_between=(600, 900))

    result = sdm120_verify.main(verify_args(tenant, direct, API, GATEWAY, DAEMON))

    out = capsys.readouterr().out
    assert result == 0, out
    assert "Verdict : Réussi" in out
    assert "Aucun trou de plus de deux intervalles" not in out, "les trous des coupures sont listés"
    assert "Non couvert par ce verdict" in out


def test_mesures_perdues_pendant_la_coupure_de_l_api_donnent_fail(tmp_path, tenant, capsys) -> None:
    """Le défaut corrigé le 21/10/2026 : démon qui ne relevait plus rien sans API."""
    _, direct = run_preflight(tmp_path, "--resistive-load", "--display", "voltage=231,4")
    insert_run(tenant, full_run_times(lose_api_window=True))

    result = sdm120_verify.main(verify_args(tenant, direct, API, GATEWAY, DAEMON))

    out = capsys.readouterr().out
    assert result == 1
    assert "perdue" in out


def test_sans_epreuve_de_panne_ni_afficheur_le_verdict_est_incomplet(
    tmp_path, tenant, capsys
) -> None:
    _, direct = run_preflight(tmp_path)
    insert_run(tenant, list(range(0, 1801, INTERVAL)))

    result = sdm120_verify.main(verify_args(tenant, direct, end=1800))

    assert result == 3
    assert "Verdict : Incomplet" in capsys.readouterr().out


def test_un_point_declare_en_kw_pour_une_puissance_en_watts_est_signale(
    tmp_path, tenant, capsys
) -> None:
    """Le vocabulaire accepte `kW` pour une puissance et rien ne compare l'unité du point à
    celle du compteur : seul ce contrôle révèle le facteur 1000. (Un point validé ne se
    modifie plus : le bon point doit être créé avant la validation.)"""
    _, direct = run_preflight(tmp_path, "--resistive-load", "--display", "voltage=231,4")
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        wrong_point = create_point(
            connection,
            tenant_id=tenant["tenant_id"],
            code=f"CPT-{tenant['tenant_id'].hex[:8]}-PKW",
            name="Puissance déclarée en kW",
            value_type="number",
            point_class="electric_power_sensor",
            unit="kW",
            functional_location_id=tenant["location_id"],
            min_value=0,
            max_value=100,
            created_by="test",
        )
    insert_run(tenant, full_run_times(), late_between=(600, 900), power_point=wrong_point)
    args = verify_args(tenant, direct, API, GATEWAY, DAEMON)
    args[args.index("--power-point") + 1] = str(wrong_point)

    result = sdm120_verify.main(args)

    assert result == 1
    assert "power.unit" in capsys.readouterr().out


def test_le_rapport_json_garde_les_codes_et_les_parametres(tmp_path, tenant) -> None:
    _, direct = run_preflight(tmp_path, "--resistive-load", "--display", "voltage=231,4")
    insert_run(tenant, full_run_times(), late_between=(600, 900))
    report = tmp_path / "rapport.json"

    sdm120_verify.main(
        verify_args(tenant, direct, API, GATEWAY, DAEMON, extra=["--json-out", str(report)])
    )

    data = json.loads(report.read_text("utf-8"))
    assert data["verdict"] == "PASS"
    assert {c["code"] for c in data["checks"]} >= {"NO_LOSS_DURING_API_OUTAGE", "RESTART_RESUMED"}
    assert [o["kind"] for o in data["outages"]] == ["api", "gateway", "daemon"]
    # le rapport ne contient que des codes et des nombres, jamais une phrase générée
    assert "Réussi" not in report.read_text("utf-8")


# --- Isolation des clients -----------------------------------------------------------


def test_un_autre_client_ne_voit_ni_les_points_ni_les_mesures(tmp_path, tenant, capsys) -> None:
    other = create_tenant_with_energy_and_power_points("ClientSdm120Autre")
    try:
        _, direct = run_preflight(tmp_path)
        insert_run(tenant, list(range(0, 601, INTERVAL)))

        assert sdm120_verify.fetch_point(other["tenant_id"], tenant["power_point_id"]) is None
        assert (
            sdm120_verify.fetch_series(
                other["tenant_id"], tenant["power_point_id"], stamp(0), stamp(3000)
            )
            == []
        )
        args = verify_args(tenant, direct, end=600)
        args[args.index("--tenant") + 1] = str(other["tenant_id"])
        assert sdm120_verify.main(args) == 2
        assert "introuvable" in capsys.readouterr().err
    finally:
        cleanup_tenant(other)


def test_un_identifiant_de_point_inconnu_donne_le_code_2(tmp_path, tenant) -> None:
    _, direct = run_preflight(tmp_path)
    args = verify_args(tenant, direct, end=600)
    args[args.index("--power-point") + 1] = str(uuid.uuid4())

    assert sdm120_verify.main(args) == 2
