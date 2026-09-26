"""Moteur énergétique interne (M5) : agrégation d'un compteur cumulatif,
degrés-jours, référence énergétique versionnée, normalisation et
comparaison. Voir app/energy/ pour la conception (Mohamed, 24/09/2026) :
chaque résultat doit rester explicable des années plus tard."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text

from app.config_versions import ConfigInvalid, activate_version, create_version
from app.energy.aggregation import EnergyDataInsufficient, aggregate_energy_consumption
from app.energy.baseline import ENERGY_BASELINE
from app.energy.comparison import compare_results
from app.energy.normalization import (
    EnergyBaselineNotFound,
    compute_normalized_performance,
    get_normalized_result,
    list_normalized_results,
)
from app.energy.weather import (
    aggregate_degree_days,
    list_weather_observations,
    record_weather_observation,
)
from app.points import create_point, decide_point, get_point
from app.telemetry import record_measurement
from tests.energy_fixtures import cleanup_tenant, create_tenant_with_energy_meter, in_tenant
from tests.error_helpers import raises_code

T0 = datetime(2026, 9, 24, 8, 0, tzinfo=UTC)


@pytest.fixture
def two_tenants():
    tenant_a = create_tenant_with_energy_meter("ClientEnergyA")
    tenant_b = create_tenant_with_energy_meter("ClientEnergyB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        cleanup_tenant(tenant)


def _reading(connection, tenant, value, at):
    return record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=get_point(connection, tenant["meter"]),
        value=value,
        measured_at=at,
        origin="simulated",
        source="simulator",
        received_at=at,
    )


def _weather(connection, tenant, start, days, mean_temperature_celsius):
    for offset in range(days):
        record_weather_observation(
            connection,
            tenant_id=tenant["tenant_id"],
            site_id=tenant["site"],
            observed_date=start + timedelta(days=offset),
            mean_temperature_celsius=mean_temperature_celsius,
            created_by="technicien",
        )


def _activate_baseline(connection, tenant, **overrides):
    content = {
        "point_id": str(tenant["meter"]),
        "method": "degree_day_ratio",
        "method_version": "v1",
        "reference_period": {"start": "2025-01-01", "end": "2025-01-31"},
        "degree_day_base_temperature_celsius": 18.0,
        "degree_day_kind": "heating",
    }
    content.update(overrides)
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ENERGY_BASELINE,
        subject_key=f"baseline:{tenant['meter']}",
        content=content,
        author="responsable",
        reason="test",
    )
    activate_version(connection, version_id=version_id, activated_by="responsable", activated_at=T0)
    return version_id


# --- Agrégation : un compteur cumulatif ne se somme pas -----------------------------------


def test_consumption_is_the_delta_between_closing_and_opening_readings(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _reading(connection, tenant_a, 1000.0, datetime(2025, 12, 31, 23, 0, tzinfo=UTC))
        _reading(connection, tenant_a, 1100.0, datetime(2026, 1, 1, 0, 30, tzinfo=UTC))
        _reading(connection, tenant_a, 1620.0, datetime(2026, 1, 31, 23, 0, tzinfo=UTC))
        point = get_point(connection, tenant_a["meter"])
        result = aggregate_energy_consumption(
            connection, point=point, period_start=date(2026, 1, 1), period_end=date(2026, 1, 31)
        )
    assert result["raw_consumption"] == 620.0
    assert result["raw_consumption_unit"] == "kW.h"
    assert result["measurement_count"] == 2
    assert result["evidence"]["opening_value"] == 1000.0
    assert result["evidence"]["closing_value"] == 1620.0


def test_missing_boundary_reading_is_reported_not_guessed(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(EnergyDataInsufficient) as info:
        with in_tenant(tenant_a) as connection:
            point = get_point(connection, tenant_a["meter"])
            aggregate_energy_consumption(
                connection, point=point, period_start=date(2026, 1, 1), period_end=date(2026, 1, 31)
            )
    assert info.value.code == "ENERGY_DATA_INSUFFICIENT"


def test_a_meter_reset_is_detected_and_never_silently_absorbed(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(EnergyDataInsufficient) as info:
        with in_tenant(tenant_a) as connection:
            _reading(connection, tenant_a, 5000.0, datetime(2025, 12, 31, 23, 0, tzinfo=UTC))
            _reading(connection, tenant_a, 120.0, datetime(2026, 1, 31, 23, 0, tzinfo=UTC))
            point = get_point(connection, tenant_a["meter"])
            aggregate_energy_consumption(
                connection, point=point, period_start=date(2026, 1, 1), period_end=date(2026, 1, 31)
            )
    assert info.value.code == "ENERGY_METER_RESET_DETECTED"


def test_a_doubtful_reading_is_never_used_as_a_boundary(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _reading(connection, tenant_a, 1000.0, datetime(2025, 12, 31, 23, 0, tzinfo=UTC))
        # Hors plage physique du compteur : marqué douteux, jamais utilisé comme borne.
        _reading(connection, tenant_a, -1.0, datetime(2026, 1, 31, 20, 0, tzinfo=UTC))
        _reading(connection, tenant_a, 1400.0, datetime(2026, 1, 31, 23, 0, tzinfo=UTC))
        point = get_point(connection, tenant_a["meter"])
        result = aggregate_energy_consumption(
            connection, point=point, period_start=date(2026, 1, 1), period_end=date(2026, 1, 31)
        )
    assert result["raw_consumption"] == 400.0


# --- Contexte météo et degrés-jours ------------------------------------------------------


def test_a_later_observation_corrects_the_earlier_one_for_the_same_day(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        record_weather_observation(
            connection,
            tenant_id=tenant_a["tenant_id"],
            site_id=tenant_a["site"],
            observed_date=date(2026, 1, 1),
            mean_temperature_celsius=5.0,
            created_by="technicien",
        )
        record_weather_observation(
            connection,
            tenant_id=tenant_a["tenant_id"],
            site_id=tenant_a["site"],
            observed_date=date(2026, 1, 1),
            mean_temperature_celsius=6.5,
            created_by="technicien",
        )
        observations = list_weather_observations(
            connection,
            site_id=tenant_a["site"],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 1),
        )
    assert [o["mean_temperature_celsius"] for o in observations] == [6.5]


def test_heating_and_cooling_degree_days_from_daily_temperatures(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _weather(connection, tenant_a, date(2026, 1, 1), 3, mean_temperature_celsius=5.0)
        heating = aggregate_degree_days(
            connection,
            site_id=tenant_a["site"],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 3),
            base_temperature_celsius=18.0,
            kind="heating",
        )
        cooling = aggregate_degree_days(
            connection,
            site_id=tenant_a["site"],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 3),
            base_temperature_celsius=18.0,
            kind="cooling",
        )
    assert heating == {
        "degree_days": 39.0,
        "days_total": 3,
        "days_observed": 3,
        "days_missing": 0,
        "sources": ["manual"],
    }
    assert cooling["degree_days"] == 0.0


def test_missing_days_are_reported_never_estimated(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        _weather(connection, tenant_a, date(2026, 1, 1), 3, mean_temperature_celsius=5.0)
        result = aggregate_degree_days(
            connection,
            site_id=tenant_a["site"],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 5),
            base_temperature_celsius=18.0,
            kind="heating",
        )
    assert result["days_observed"] == 3
    assert result["days_missing"] == 2
    assert result["degree_days"] == 39.0


def test_no_observation_at_all_yields_no_degree_days(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        result = aggregate_degree_days(
            connection,
            site_id=tenant_a["site"],
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 5),
            base_temperature_celsius=18.0,
            kind="heating",
        )
    assert result["degree_days"] is None
    assert result["days_missing"] == 5
    assert result["sources"] == []


# --- Référence énergétique (baseline) : une configuration versionnée de plus --------------


def test_a_valid_baseline_is_registered_as_a_config_version(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        version_id = _activate_baseline(connection, tenant_a)
        status = connection.execute(
            text("SELECT status, config_type FROM config_versions WHERE id = :id"),
            {"id": version_id},
        ).one()
    assert tuple(status) == ("active", ENERGY_BASELINE)


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"degree_day_kind": "unknown"}, "ENERGY_BASELINE_CONTENT_INVALID"),
        (
            {"reference_period": {"start": "2025-02-01", "end": "2025-01-01"}},
            "ENERGY_BASELINE_CONTENT_INVALID",
        ),
        ({"method": "unknown_method"}, "ENERGY_BASELINE_METHOD_UNKNOWN"),
    ],
)
def test_invalid_baseline_content_is_rejected(two_tenants, overrides, code) -> None:
    tenant_a, _ = two_tenants
    with raises_code(ConfigInvalid, code):
        with in_tenant(tenant_a) as connection:
            _activate_baseline(connection, tenant_a, **overrides)


def test_baseline_on_an_unknown_point_is_rejected(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with raises_code(ConfigInvalid, "ENERGY_BASELINE_POINT_NOT_FOUND"):
        with in_tenant(tenant_a) as connection:
            _activate_baseline(connection, tenant_a, point_id=str(uuid.uuid4()))


def test_baseline_on_a_non_energy_point_is_rejected(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        other_point = create_point(
            connection,
            tenant_id=tenant_a["tenant_id"],
            code="PAC01-TDEP",
            name="Température départ",
            value_type="number",
            point_class="supply_water_temperature_sensor",
            unit="Cel",
            functional_location_id=tenant_a["location"],
            created_by="test",
        )
        decide_point(connection, point_id=other_point, decision="validated")
    with raises_code(ConfigInvalid, "ENERGY_BASELINE_POINT_NOT_ENERGY_METER"):
        with in_tenant(tenant_a) as connection:
            _activate_baseline(connection, tenant_a, point_id=str(other_point))


def test_baseline_on_an_unvalidated_point_is_rejected(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        candidate = create_point(
            connection,
            tenant_id=tenant_a["tenant_id"],
            code="PAC01-ENERGIE-2",
            name="Énergie active totale (2)",
            value_type="number",
            point_class="energy_meter_reading",
            unit="kW.h",
            functional_location_id=tenant_a["location"],
            created_by="test",
        )
    with raises_code(ConfigInvalid, "ENERGY_BASELINE_POINT_NOT_VALIDATED"):
        with in_tenant(tenant_a) as connection:
            _activate_baseline(connection, tenant_a, point_id=str(candidate))


# --- Normalisation : la chaîne complète ---------------------------------------------------


def _seed_full_period(connection, tenant):
    _reading(connection, tenant, 1000.0, datetime(2025, 12, 31, 23, 0, tzinfo=UTC))
    _reading(connection, tenant, 1620.0, datetime(2026, 1, 31, 23, 0, tzinfo=UTC))
    _weather(connection, tenant, date(2025, 1, 1), 31, mean_temperature_celsius=5.0)
    _weather(connection, tenant, date(2026, 1, 1), 31, mean_temperature_celsius=8.0)


def test_a_normalized_result_carries_its_full_traceability(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        baseline_id = _activate_baseline(connection, tenant_a)
        _seed_full_period(connection, tenant_a)
        result = compute_normalized_performance(
            connection,
            tenant_id=tenant_a["tenant_id"],
            baseline_config_version_id=baseline_id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            computed_by="responsable",
            at=T0,
        )
    # Degrés-jours chauffage (base 18°C) : référence 2025 à 5°C -> 13*31 = 403 ;
    # période analysée 2026 à 8°C -> 10*31 = 310. Consommation brute 620 kWh.
    assert result["degree_days"] == 310.0
    assert result["raw_consumption"] == 620.0
    assert result["normalization_status"] == "ok"
    assert result["normalized_consumption"] == pytest.approx(806.0)
    assert result["method"] == "degree_day_ratio"
    assert result["method_version"] == "v1"
    assert result["weather_source"] == "manual"
    assert result["weather_days_missing"] == 0
    assert result["baseline_config_version_id"] == baseline_id
    assert result["functional_location_id"] == tenant_a["location"]
    assert result["point_id"] == tenant_a["meter"]
    assert result["computed_by"] == "responsable"
    assert result["parameters"]["method"] == "degree_day_ratio"
    assert result["evidence"]["reference_period_degree_days"]["degree_days"] == 403.0

    with in_tenant(tenant_a) as connection:
        fetched = get_normalized_result(connection, result["id"])
        listed = list_normalized_results(connection, functional_location_id=tenant_a["location"])
    assert fetched["id"] == result["id"]
    assert [row["id"] for row in listed] == [result["id"]]


def test_a_new_computation_never_overwrites_the_previous_one(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        baseline_id = _activate_baseline(connection, tenant_a)
        _seed_full_period(connection, tenant_a)
        first = compute_normalized_performance(
            connection,
            tenant_id=tenant_a["tenant_id"],
            baseline_config_version_id=baseline_id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            computed_by="responsable",
            at=T0,
        )
        second = compute_normalized_performance(
            connection,
            tenant_id=tenant_a["tenant_id"],
            baseline_config_version_id=baseline_id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            computed_by="responsable",
            at=T0 + timedelta(hours=1),
        )
        count = connection.execute(text("SELECT count(*) FROM energy_normalized_results")).scalar()
    assert first["id"] != second["id"]
    assert count == 2


def test_missing_weather_yields_a_result_without_normalization(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        baseline_id = _activate_baseline(connection, tenant_a)
        _reading(connection, tenant_a, 1000.0, datetime(2025, 12, 31, 23, 0, tzinfo=UTC))
        _reading(connection, tenant_a, 1620.0, datetime(2026, 1, 31, 23, 0, tzinfo=UTC))
        # Référence renseignée, mais aucune observation météo pour la période analysée.
        _weather(connection, tenant_a, date(2025, 1, 1), 31, mean_temperature_celsius=5.0)
        result = compute_normalized_performance(
            connection,
            tenant_id=tenant_a["tenant_id"],
            baseline_config_version_id=baseline_id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            computed_by="responsable",
            at=T0,
        )
    assert result["normalization_status"] == "no_weather_data"
    assert result["normalized_consumption"] is None
    assert result["raw_consumption"] == 620.0


def test_zero_degree_days_yields_a_result_without_normalization(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        baseline_id = _activate_baseline(
            connection, tenant_a, degree_day_base_temperature_celsius=5.0
        )
        _reading(connection, tenant_a, 1000.0, datetime(2025, 12, 31, 23, 0, tzinfo=UTC))
        _reading(connection, tenant_a, 1620.0, datetime(2026, 1, 31, 23, 0, tzinfo=UTC))
        _weather(connection, tenant_a, date(2025, 1, 1), 31, mean_temperature_celsius=5.0)
        # Température toujours égale à la base : aucun degré-jour de chauffage.
        _weather(connection, tenant_a, date(2026, 1, 1), 31, mean_temperature_celsius=5.0)
        result = compute_normalized_performance(
            connection,
            tenant_id=tenant_a["tenant_id"],
            baseline_config_version_id=baseline_id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            computed_by="responsable",
            at=T0,
        )
    assert result["degree_days"] == 0.0
    assert result["normalization_status"] == "zero_degree_days"
    assert result["normalized_consumption"] is None


def test_insufficient_energy_data_stops_before_any_row_is_persisted(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with in_tenant(tenant_a) as connection:
        baseline_id = _activate_baseline(connection, tenant_a)
        _weather(connection, tenant_a, date(2025, 1, 1), 31, mean_temperature_celsius=5.0)
        _weather(connection, tenant_a, date(2026, 1, 1), 31, mean_temperature_celsius=8.0)
    with pytest.raises(EnergyDataInsufficient) as info:
        with in_tenant(tenant_a) as connection:
            compute_normalized_performance(
                connection,
                tenant_id=tenant_a["tenant_id"],
                baseline_config_version_id=baseline_id,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                computed_by="responsable",
                at=T0,
            )
    assert info.value.code == "ENERGY_DATA_INSUFFICIENT"
    with in_tenant(tenant_a) as connection:
        count = connection.execute(text("SELECT count(*) FROM energy_normalized_results")).scalar()
    assert count == 0


def test_computing_from_an_unknown_baseline_is_refused(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with raises_code(EnergyBaselineNotFound, "ENERGY_BASELINE_NOT_FOUND"):
        with in_tenant(tenant_a) as connection:
            compute_normalized_performance(
                connection,
                tenant_id=tenant_a["tenant_id"],
                baseline_config_version_id=uuid.uuid4(),
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                computed_by="responsable",
                at=T0,
            )


# --- Comparaison : une lecture pure, jamais un nouveau calcul stocké ----------------------


def test_a_reduction_in_normalized_consumption_is_reported_as_such() -> None:
    reference = {"id": "ref", "normalized_consumption": 1000.0}
    analyzed = {"id": "analyzed", "normalized_consumption": 800.0}
    comparison = compare_results(reference, analyzed)
    assert comparison["comparable"] is True
    assert comparison["absolute_deviation"] == -200.0
    assert comparison["percent_deviation"] == -20.0
    assert comparison["reduced"] is True


def test_an_increase_in_normalized_consumption_is_reported_as_such() -> None:
    reference = {"id": "ref", "normalized_consumption": 1000.0}
    analyzed = {"id": "analyzed", "normalized_consumption": 1200.0}
    comparison = compare_results(reference, analyzed)
    assert comparison["percent_deviation"] == 20.0
    assert comparison["reduced"] is False


def test_a_result_without_normalization_is_never_compared() -> None:
    reference = {"id": "ref", "normalized_consumption": None}
    analyzed = {"id": "analyzed", "normalized_consumption": 800.0}
    comparison = compare_results(reference, analyzed)
    assert comparison == {
        "comparable": False,
        "reason": "normalization_unavailable",
        "reference_result_id": "ref",
        "analyzed_result_id": "analyzed",
    }


# --- Isolation des clients (règle non négociable n°2) -------------------------------------


@pytest.mark.parametrize("table", ["weather_observations", "energy_normalized_results"])
def test_tenant_isolation_on_energy_tables(two_tenants, table) -> None:
    tenant_a, tenant_b = two_tenants
    with in_tenant(tenant_a) as connection:
        baseline_id = _activate_baseline(connection, tenant_a)
        _seed_full_period(connection, tenant_a)
        compute_normalized_performance(
            connection,
            tenant_id=tenant_a["tenant_id"],
            baseline_config_version_id=baseline_id,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            computed_by="responsable",
            at=T0,
        )
        seen_by_a = connection.execute(
            text(f"SELECT 1 FROM {table} WHERE tenant_id = :id"), {"id": tenant_a["tenant_id"]}
        ).fetchall()
    with in_tenant(tenant_b) as connection:
        seen_by_b = connection.execute(
            text(f"SELECT 1 FROM {table} WHERE tenant_id = :id"), {"id": tenant_a["tenant_id"]}
        ).fetchall()
    assert seen_by_a
    assert seen_by_b == []
