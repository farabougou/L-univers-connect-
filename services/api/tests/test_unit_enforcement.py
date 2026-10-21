"""Incohérences d'unités (décision de Mohamed du 21/10/2026) : un point déclaré en kW ne doit
jamais accepter silencieusement une valeur fournie en watts. La plateforme refuse avec une
erreur explicite et **ne convertit jamais** ; la conversion est un acte volontaire de l'émetteur.

Ce qui est prouvé ici, de la règle pure jusqu'aux chemins d'entrée réels :
- le vocabulaire (W/kW, kW/W, grandeurs différentes, °C/K, unités inconnues) ;
- l'enregistrement d'une mesure (valeurs limites, historique ancien, lots mêlant bon et mauvais) ;
- l'API (saisie humaine, lot) ; le démon et l'API Edge sont dans tests/test_modbus_daemon.py ;
- la création d'une connexion Modbus (le refus a lieu avant la première mesure) ;
- le tampon hors ligne (l'unité suit la mesure) et l'import d'un export historique.

Limite assumée, et dite : sans unité déclarée, la valeur est prise telle quelle (comportement
d'avant) ; seul un drapeau `out_of_range` signale après coup une valeur hors plage."""

import csv
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config_versions import ConfigInvalid, create_version
from app.connectors.device_mapping import MODBUS_DEVICE_MAPPING
from app.connectors.offline_buffer import BufferedReading
from app.db import engine
from app.i18n import render
from app.main import app
from app.point_vocabulary import (
    LINEAR_UNIT_FACTORS,
    UNITS,
    PointVocabularyError,
    check_declared_unit,
    conversion_factor,
)
from app.points import create_point, decide_point
from app.telemetry import MeasurementRejected, ingest_measurements, record_measurement
from app.tenancy import set_tenant_context
from scripts.replay_import import run as replay_run
from tests.error_helpers import raises_code
from tests.jwt_helpers import JWKS, make_token
from tests.modbus_fixtures import cleanup_tenant, create_tenant_with_energy_and_power_points

client = TestClient(app)


# --- La règle pure ------------------------------------------------------------------


def _refusal(declared: str, point_unit: str | None) -> PointVocabularyError:
    with pytest.raises(PointVocabularyError) as info:
        check_declared_unit(declared, point_unit)
    return info.value


@pytest.mark.parametrize("unit", sorted(UNITS))
def test_la_meme_unite_est_toujours_acceptee(unit) -> None:
    check_declared_unit(unit, unit)


@pytest.mark.parametrize(
    ("declared", "expected", "factor"),
    [
        ("W", "kW", "0.001"),  # le cas qui motive la règle : des watts dans un point en kW
        ("kW", "W", "1000"),
        ("Pa", "kPa", "0.001"),
        ("kPa", "Pa", "1000"),
        ("bar", "kPa", "100"),
        ("Pa", "bar", "0.00001"),
    ],
)
def test_meme_grandeur_exige_une_conversion_volontaire_et_donne_le_facteur(
    declared, expected, factor
) -> None:
    error = _refusal(declared, expected)

    assert error.code == "MEASUREMENT_UNIT_CONVERSION_REQUIRED"
    assert error.params == {"declared": declared, "expected": expected, "factor": factor}


@pytest.mark.parametrize(
    ("declared", "expected"),
    [("W", "Cel"), ("kW.h", "kW"), ("Cel", "K"), ("K", "Cel"), ("kg", "m3/h")],
)
def test_grandeur_differente_ou_conversion_non_lineaire_est_un_desaccord(
    declared, expected
) -> None:
    """°C et K ne sont pas liés par un simple facteur (décalage) : jamais de facteur inventé."""
    error = _refusal(declared, expected)

    assert error.code == "MEASUREMENT_UNIT_MISMATCH"
    assert error.params == {"declared": declared, "expected": expected}


def test_une_unite_declaree_pour_un_point_sans_unite_est_refusee() -> None:
    error = _refusal("W", None)

    assert error.code == "MEASUREMENT_UNIT_NOT_EXPECTED"


@pytest.mark.parametrize("declared", ["", "kw", "KW", "kWh", "Wh", "W ", "watt", "°C"])
def test_une_unite_hors_vocabulaire_est_inconnue_meme_si_elle_y_ressemble(declared) -> None:
    """UCUM est sensible à la casse : « kw » n'est pas « kW », et « kWh » (symbole affiché)
    n'est pas le code « kW.h »."""
    assert _refusal(declared, "kW").code == "UNIT_UNKNOWN"


def test_les_facteurs_de_conversion_sont_inverses_l_un_de_l_autre() -> None:
    for declared in LINEAR_UNIT_FACTORS:
        for expected in LINEAR_UNIT_FACTORS:
            forward = conversion_factor(declared, expected)
            if forward is None:
                assert UNITS[declared][1] != UNITS[expected][1]
                continue
            assert forward * conversion_factor(expected, declared) == pytest.approx(1.0)


def test_les_messages_disent_que_la_plateforme_ne_convertit_jamais() -> None:
    error = _refusal("W", "kW")

    fr = render(error.code, error.params, "fr")
    en = render(error.code, error.params, "en")

    assert "ne convertit jamais" in fr and "0.001" in fr and "« W »" in fr.replace("\xa0", " ")
    assert "never converts" in en and "0.001" in en


# --- L'enregistrement d'une mesure -----------------------------------------------------


@pytest.fixture
def tenant():
    created = create_tenant_with_energy_and_power_points("ClientUnites")
    with engine.begin() as connection:
        set_tenant_context(connection, created["tenant_id"])
        kw_point = create_point(
            connection,
            tenant_id=created["tenant_id"],
            code=f"CPT-{created['tenant_id'].hex[:8]}-PKW",
            name="Puissance en kW",
            value_type="number",
            point_class="electric_power_sensor",
            unit="kW",
            functional_location_id=created["location_id"],
            min_value=0,
            max_value=100,
            created_by="test",
        )
        decide_point(connection, point_id=kw_point, decision="validated")
    created["kw_point_id"] = kw_point
    yield created
    cleanup_tenant(created)


def _point(tenant, key: str) -> dict:
    from app.points import get_point

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return get_point(connection, tenant[key])


def _record(tenant, key: str, value: float, **kwargs) -> str:
    kwargs.setdefault("measured_at", datetime.now(UTC) - timedelta(minutes=1))
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=_point(tenant, key),
            value=value,
            origin="measured",
            source="test",
            received_at=datetime.now(UTC),
            **kwargs,
        )


def _rows(tenant, key: str) -> list[dict]:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT value, quality_flags, measured_at FROM measurements "
                    "WHERE point_id = :p ORDER BY measured_at"
                ),
                {"p": tenant[key]},
            ).mappings()
        ]


def test_des_watts_declares_dans_un_point_en_kw_sont_refuses_et_rien_n_est_stocke(tenant) -> None:
    with raises_code(MeasurementRejected, "MEASUREMENT_UNIT_CONVERSION_REQUIRED") as info:
        _record(tenant, "kw_point_id", 548.0, unit="W")

    assert info.value.params["factor"] == "0.001"
    assert _rows(tenant, "kw_point_id") == []


def test_la_meme_valeur_convertie_volontairement_et_declaree_en_kw_est_acceptee(tenant) -> None:
    assert _record(tenant, "kw_point_id", 0.548, unit="kW") == "inserted"

    assert [row["value"] for row in _rows(tenant, "kw_point_id")] == [0.548]


@pytest.mark.parametrize(
    ("value", "flags"),
    [
        (0.0, []),  # borne basse du point
        (100.0, []),  # borne haute du point, atteinte exactement
        (100.001, ["out_of_range"]),  # juste au-dessus : gardée mais signalée, comme avant
        (-0.001, ["out_of_range"]),
    ],
)
def test_valeurs_limites_d_un_point_en_kw_avec_l_unite_declaree(tenant, value, flags) -> None:
    _record(tenant, "kw_point_id", value, unit="kW")

    assert _rows(tenant, "kw_point_id")[0]["quality_flags"] == flags


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0, 99.9, 100.0, 1000.0, 548.0, 1e9])
def test_le_refus_d_unite_ne_depend_jamais_de_la_valeur(tenant, value) -> None:
    """Y compris une valeur « plausible » (0,5 ou 99,9 : dans la plage du point en kW) : c'est
    l'unité déclarée qui est refusée, pas le nombre. Un contrôle fondé sur la plage laisserait
    passer ces valeurs."""
    with raises_code(MeasurementRejected, "MEASUREMENT_UNIT_CONVERSION_REQUIRED"):
        _record(tenant, "kw_point_id", value, unit="W")

    assert _rows(tenant, "kw_point_id") == []


def test_une_valeur_non_finie_reste_refusee_avant_toute_question_d_unite(tenant) -> None:
    with raises_code(MeasurementRejected, "VALUE_NOT_FINITE"):
        _record(tenant, "kw_point_id", float("inf"), unit="W")


def test_sans_unite_declaree_la_valeur_est_prise_telle_quelle_et_seule_la_plage_alerte(
    tenant,
) -> None:
    """Limite connue : un émetteur qui ne déclare pas son unité n'est pas contrôlé. Au moins,
    548 « watts » dans un point en kW (plage 0 à 100) ressortent signalés `out_of_range`."""
    assert _record(tenant, "kw_point_id", 548.0) == "inserted"

    assert _rows(tenant, "kw_point_id")[0]["quality_flags"] == ["out_of_range"]


def test_une_unite_declaree_pour_un_point_sans_unite_est_refusee_a_l_enregistrement(
    tenant,
) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        boolean_point = create_point(
            connection,
            tenant_id=tenant["tenant_id"],
            code=f"MARCHE-{tenant['tenant_id'].hex[:8]}",
            name="Marche",
            value_type="boolean",
            point_class="run_status",
            unit=None,
            functional_location_id=tenant["location_id"],
            created_by="test",
        )
        decide_point(connection, point_id=boolean_point, decision="validated")
    tenant["run_point_id"] = boolean_point

    with raises_code(MeasurementRejected, "MEASUREMENT_UNIT_NOT_EXPECTED"):
        _record(tenant, "run_point_id", 1.0, unit="W")
    assert _record(tenant, "run_point_id", 1.0) == "inserted"


# --- Données historiques -------------------------------------------------------------


def test_un_historique_ancien_est_controle_comme_une_mesure_en_direct(tenant) -> None:
    three_years_ago = datetime.now(UTC) - timedelta(days=3 * 365)

    with raises_code(MeasurementRejected, "MEASUREMENT_UNIT_CONVERSION_REQUIRED"):
        _record(tenant, "kw_point_id", 548.0, unit="W", measured_at=three_years_ago)
    assert _record(tenant, "kw_point_id", 0.548, unit="kW", measured_at=three_years_ago) == (
        "inserted"
    )

    row = _rows(tenant, "kw_point_id")[0]
    assert row["value"] == 0.548 and "late_arrival" in row["quality_flags"]


def test_un_lot_historique_melange_garde_les_bonnes_lignes_et_nomme_les_mauvaises(
    tenant,
) -> None:
    old = datetime.now(UTC) - timedelta(days=400)
    items = [
        {
            "point_id": tenant["kw_point_id"],
            "value": 0.5 + index,
            "measured_at": old + timedelta(hours=index),
            "origin": "measured",
            "unit": "W" if index == 2 else "kW",
        }
        for index in range(4)
    ]

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        summary = ingest_measurements(
            connection,
            tenant_id=tenant["tenant_id"],
            items=items,
            source="historique",
            received_at=datetime.now(UTC),
        )

    assert (summary["inserted"], summary["rejected"]) == (3, 1)
    assert summary["errors"][0]["index"] == 2
    assert summary["errors"][0]["code"] == "MEASUREMENT_UNIT_CONVERSION_REQUIRED"
    assert [row["value"] for row in _rows(tenant, "kw_point_id")] == [0.5, 1.5, 3.5]


def test_renvoyer_un_historique_deja_recu_avec_une_mauvaise_unite_ne_change_rien(tenant) -> None:
    moment = datetime.now(UTC) - timedelta(days=30)
    _record(tenant, "kw_point_id", 1.25, unit="kW", measured_at=moment)

    with raises_code(MeasurementRejected, "MEASUREMENT_UNIT_CONVERSION_REQUIRED"):
        _record(tenant, "kw_point_id", 1250.0, unit="W", measured_at=moment)

    assert [row["value"] for row in _rows(tenant, "kw_point_id")] == [1.25]
    assert _record(tenant, "kw_point_id", 1.25, unit="kW", measured_at=moment) == "duplicate"


def test_un_point_valide_ne_peut_pas_changer_d_unite_apres_des_mesures(tenant) -> None:
    """Les mesures déjà enregistrées ne changent donc jamais d'unité sous les pieds de leur
    historique : un autre point doit être créé (règle « rien n'est écrasé »)."""
    _record(tenant, "kw_point_id", 1.0, unit="kW")

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(Exception, match="ne peut plus être modifiée"):
            connection.execute(
                text("UPDATE points SET unit = 'W' WHERE id = :id"), {"id": tenant["kw_point_id"]}
            )


# --- L'API (saisie humaine et lot) -------------------------------------------------------


def _headers(tenant) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant["tenant_id"]), roles=["technicien"])
    return {"Authorization": f"Bearer {token}", "Accept-Language": "fr"}


def _call(method: str, path: str, tenant, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=_headers(tenant), **kwargs)


def _recent() -> str:
    return (datetime.now(UTC) - timedelta(minutes=1)).isoformat()


def test_api_une_mesure_en_watts_pour_un_point_en_kw_donne_400_avec_le_code_et_le_facteur(
    tenant,
) -> None:
    response = _call(
        "POST",
        "/measurements",
        tenant,
        json={
            "point_id": str(tenant["kw_point_id"]),
            "value": 548.0,
            "measured_at": _recent(),
            "unit": "W",
        },
    )

    body = response.json()
    assert response.status_code == 400, response.text
    assert body["code"] == "MEASUREMENT_UNIT_CONVERSION_REQUIRED"
    assert body["params"] == {"declared": "W", "expected": "kW", "factor": "0.001"}
    assert "ne convertit jamais" in body["detail"]
    assert _rows(tenant, "kw_point_id") == []


def test_api_la_mesure_convertie_et_declaree_en_kw_est_acceptee(tenant) -> None:
    response = _call(
        "POST",
        "/measurements",
        tenant,
        json={
            "point_id": str(tenant["kw_point_id"]),
            "value": 0.548,
            "measured_at": _recent(),
            "unit": "kW",
        },
    )

    assert response.status_code == 201, response.text


def test_api_une_unite_inconnue_est_une_erreur_explicite(tenant) -> None:
    response = _call(
        "POST",
        "/measurements",
        tenant,
        json={"point_id": str(tenant["kw_point_id"]), "value": 1.0, "unit": "watts"},
    )

    assert response.status_code == 400 and response.json()["code"] == "UNIT_UNKNOWN"


def test_api_sans_unite_le_contrat_precedent_est_inchange(tenant) -> None:
    response = _call(
        "POST",
        "/measurements",
        tenant,
        json={"point_id": str(tenant["kw_point_id"]), "value": 1.0, "measured_at": _recent()},
    )

    assert response.status_code == 201, response.text


def test_api_lot_les_refus_d_unite_sont_nommes_ligne_par_ligne_avec_leur_raison(tenant) -> None:
    now = datetime.now(UTC)
    items = [
        {
            "point_id": str(tenant["kw_point_id"]),
            "value": value,
            "measured_at": (now - timedelta(minutes=minutes)).isoformat(),
            "unit": unit,
        }
        for value, minutes, unit in ((0.4, 3, "kW"), (400.0, 2, "W"), (0.6, 1, "kW"))
    ]

    response = _call("POST", "/measurements/batch", tenant, json={"source": "test", "items": items})

    body = response.json()
    assert response.status_code == 200, response.text
    assert (body["inserted"], body["rejected"]) == (2, 1)
    assert body["errors"][0]["index"] == 1
    assert body["errors"][0]["code"] == "MEASUREMENT_UNIT_CONVERSION_REQUIRED"
    assert "ne convertit jamais" in body["errors"][0]["reason"]


# --- La connexion Modbus : le refus a lieu avant la première mesure ----------------------


def _mapping(tenant, point_key: str, register: str):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return create_version(
            connection,
            tenant_id=tenant["tenant_id"],
            config_type=MODBUS_DEVICE_MAPPING,
            subject_key=str(uuid.uuid4()),
            content={
                "device_type": "sdm120",
                "host": "192.168.1.50",
                "port": 502,
                "points": [{"point_id": str(tenant[point_key]), "register_name": register}],
            },
            author="test",
            reason="test",
        )


def test_un_registre_en_watts_ne_peut_pas_alimenter_un_point_en_kw(tenant) -> None:
    with raises_code(ConfigInvalid, "MODBUS_UNIT_CONVERSION_REQUIRED") as info:
        _mapping(tenant, "kw_point_id", "active_power")

    assert info.value.params["declared"] == "W"
    assert info.value.params["expected"] == "kW"
    assert info.value.params["factor"] == "0.001"
    assert info.value.params["register"] == "active_power"


@pytest.mark.parametrize(
    ("point_key", "register"),
    [("power_point_id", "active_power"), ("energy_point_id", "total_active_energy")],
)
def test_les_associations_dans_la_bonne_unite_sont_acceptees(tenant, point_key, register) -> None:
    assert _mapping(tenant, point_key, register)


def test_un_registre_dans_une_autre_grandeur_est_un_desaccord(tenant) -> None:
    with raises_code(ConfigInvalid, "MODBUS_UNIT_MISMATCH"):
        _mapping(tenant, "energy_point_id", "active_power")  # W vers un point en kW.h


def test_un_registre_dont_l_unite_est_inconnue_ne_peut_alimenter_aucun_point(tenant) -> None:
    """Tension (V), courant (A) et fréquence (Hz) du SDM120 : pas encore dans le vocabulaire."""
    with raises_code(ConfigInvalid, "MODBUS_REGISTER_UNIT_UNKNOWN") as info:
        _mapping(tenant, "power_point_id", "voltage")

    assert info.value.params["unit"] == "V"


def test_les_messages_de_configuration_existent_dans_les_deux_langues() -> None:
    for code in (
        "MODBUS_UNIT_CONVERSION_REQUIRED",
        "MODBUS_UNIT_MISMATCH",
        "MODBUS_UNIT_NOT_EXPECTED",
        "MODBUS_REGISTER_UNIT_UNKNOWN",
    ):
        params = {
            "register": "r",
            "declared": "W",
            "expected": "kW",
            "factor": "0.001",
            "unit": "V",
        }
        for locale in ("fr", "en"):
            assert render(code, params, locale) != code and "{" not in render(code, params, locale)


# --- Le tampon hors ligne : l'unité suit la mesure --------------------------------------


def _reading(**overrides) -> BufferedReading:
    base = {
        "tenant_id": uuid.uuid4(),
        "point_id": uuid.uuid4(),
        "value": 548.0,
        "measured_at": datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
        "origin": "measured",
        "source": "sdm120",
    }
    return BufferedReading(**{**base, **overrides})


def test_l_unite_survit_au_tampon_et_part_avec_la_mesure() -> None:
    reading = _reading(unit="W")

    restored = BufferedReading.from_json(reading.to_json())

    assert restored == reading
    assert restored.as_http_item()["unit"] == "W"


def test_un_ancien_tampon_sans_unite_se_relit_et_s_envoie_comme_avant() -> None:
    reading = _reading()
    legacy_line = reading.to_json()
    assert "unit" not in legacy_line

    restored = BufferedReading.from_json(legacy_line)

    assert restored.unit is None and "unit" not in restored.as_http_item()


# --- Import d'un export historique ----------------------------------------------------------


def _write_export(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["horodatage", "puissance"])
        writer.writerows(rows)


def _replay(tenant, tmp_path, rows, *, column_units):
    export = tmp_path / "export.csv"
    _write_export(export, rows)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        code = connection.execute(
            text("SELECT code FROM points WHERE id = :id"), {"id": tenant["kw_point_id"]}
        ).scalar()
    base = datetime.now(UTC) - timedelta(days=200)
    rows_with_dates = [[(base + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M"), v] for i, v in rows]
    _write_export(export, rows_with_dates)
    return replay_run(
        tenant_id=tenant["tenant_id"],
        csv_path=export,
        timestamp_column="horodatage",
        timestamp_format="%Y-%m-%d %H:%M",
        column_to_point_code={"puissance": code},
        timezone=None,
        source="export-gtb",
        dry_run=False,
        column_units=column_units,
    )


def test_un_export_en_watts_vers_un_point_en_kw_est_refuse_ligne_par_ligne(
    tenant, tmp_path, capsys
) -> None:
    summary = _replay(tenant, tmp_path, [(0, 540), (1, 560)], column_units={"puissance": "W"})

    assert summary == {"inserted": 0, "duplicate": 0, "rejected": 2}
    assert _rows(tenant, "kw_point_id") == []
    assert "ne convertit jamais" in capsys.readouterr().out.replace("\xa0", " ")


def test_un_export_dans_l_unite_du_point_est_importe(tenant, tmp_path) -> None:
    summary = _replay(tenant, tmp_path, [(0, 0.54), (1, 0.56)], column_units={"puissance": "kW"})

    assert summary["inserted"] == 2


def test_un_export_sans_unite_declaree_est_importe_mais_le_risque_est_dit(
    tenant, tmp_path, capsys
) -> None:
    summary = _replay(tenant, tmp_path, [(0, 0.54)], column_units=None)

    out = capsys.readouterr().out
    assert summary["inserted"] == 1
    assert "unité" in out and "non déclarée" in out and "aucune vérification" in out
