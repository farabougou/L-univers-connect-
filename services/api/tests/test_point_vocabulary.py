from datetime import UTC, datetime, timedelta

import pytest

from app.point_vocabulary import (
    POINT_CLASSES,
    UNITS,
    PointVocabularyError,
    check_point_definition,
    check_point_ready_for_validation,
    check_value,
)
from app.telemetry import (
    CLOCK_TOLERANCE,
    LATE_ARRIVAL,
    compute_quality_flags,
)
from tests.error_helpers import raises_code

# --- Unités ------------------------------------------------


def test_every_class_quantity_has_at_least_one_unit() -> None:
    quantities = {quantity for _, quantity in UNITS.values()}
    for point_class in POINT_CLASSES.values():
        if point_class.quantity is not None:
            assert point_class.quantity in quantities, point_class.name


def test_temperature_sensor_accepts_celsius_and_kelvin() -> None:
    for unit in ("Cel", "K"):
        check_point_definition(
            point_class="supply_water_temperature_sensor",
            value_type="number",
            unit=unit,
            states=None,
        )


def test_temperature_sensor_cannot_be_declared_in_bar() -> None:
    with raises_code(PointVocabularyError, "UNIT_QUANTITY_MISMATCH"):
        check_point_definition(
            point_class="supply_water_temperature_sensor",
            value_type="number",
            unit="bar",
            states=None,
        )


def test_unit_must_be_a_known_ucum_code() -> None:
    # « °C » est un symbole d'affichage, pas le code stocké (« Cel »).
    with raises_code(PointVocabularyError, "UNIT_UNKNOWN"):
        check_point_definition(
            point_class="temperature_sensor", value_type="number", unit="°C", states=None
        )


def test_boolean_point_has_no_unit() -> None:
    with raises_code(PointVocabularyError, "POINT_UNIT_NOT_ALLOWED"):
        check_point_definition(
            point_class="run_status", value_type="boolean", unit="%", states=None
        )


# --- Classes et types ------------------------------------------------


def test_class_imposes_its_value_type() -> None:
    with raises_code(PointVocabularyError, "POINT_CLASS_VALUE_TYPE_MISMATCH"):
        check_point_definition(
            point_class="run_status", value_type="number", unit=None, states=None
        )


def test_unknown_class_is_rejected() -> None:
    with raises_code(PointVocabularyError, "POINT_CLASS_UNKNOWN"):
        check_point_definition(
            point_class="sonde_magique", value_type="number", unit=None, states=None
        )


def test_discovered_point_without_class_is_accepted_but_not_validatable() -> None:
    check_point_definition(point_class=None, value_type="number", unit=None, states=None)
    with raises_code(PointVocabularyError, "POINT_CLASS_MISSING"):
        check_point_ready_for_validation(
            point_class=None, value_type="number", unit=None, states=None, has_anchor=True
        )


@pytest.mark.parametrize(
    ("unit", "has_anchor", "code"),
    [(None, True, "POINT_UNIT_MISSING"), ("Cel", False, "POINT_NOT_ANCHORED")],
)
def test_validation_requires_a_complete_description(unit, has_anchor, code) -> None:
    with raises_code(PointVocabularyError, code):
        check_point_ready_for_validation(
            point_class="temperature_sensor",
            value_type="number",
            unit=unit,
            states=None,
            has_anchor=has_anchor,
        )


def test_multistate_requires_integer_state_codes() -> None:
    with raises_code(PointVocabularyError, "POINT_MULTISTATE_REQUIRES_STATES"):
        check_point_definition(point_class=None, value_type="multistate", unit=None, states=None)
    with raises_code(PointVocabularyError, "POINT_STATE_CODES_NOT_INTEGER"):
        check_point_definition(
            point_class=None, value_type="multistate", unit=None, states={"arret": "Arrêt"}
        )
    check_point_definition(
        point_class=None, value_type="multistate", unit=None, states={"0": "Arrêt", "1": "Auto"}
    )


# --- Valeurs ------------------------------------------------


@pytest.mark.parametrize(
    ("value", "value_type", "states"),
    [
        (float("inf"), "number", None),
        (float("nan"), "number", None),
        (2, "boolean", None),
        (0.5, "boolean", None),
        (3, "multistate", {"0": "Arrêt", "1": "Auto"}),
        (1.5, "multistate", {"0": "Arrêt", "1": "Auto"}),
    ],
)
def test_impossible_values_are_refused(value, value_type, states) -> None:
    with pytest.raises(PointVocabularyError):
        check_value(value, value_type=value_type, states=states)


def test_valid_values_are_accepted() -> None:
    check_value(45.5, value_type="number", states=None)
    check_value(1, value_type="boolean", states=None)
    check_value(1, value_type="multistate", states={"0": "Arrêt", "1": "Auto"})


# --- Drapeaux de qualité (temps) ------------------------------------------------

RECEIVED = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _point(**overrides) -> dict:
    point = {"mapping_status": "validated", "min_value": 0.0, "max_value": 100.0}
    point.update(overrides)
    return point


def test_clean_measurement_has_no_flag() -> None:
    assert (
        compute_quality_flags(_point(), value=45.5, measured_at=RECEIVED, received_at=RECEIVED)
        == []
    )


def test_value_outside_physical_range_is_flagged_not_discarded() -> None:
    flags = compute_quality_flags(_point(), value=150, measured_at=RECEIVED, received_at=RECEIVED)
    assert flags == ["out_of_range"]


def test_range_bounds_are_inclusive() -> None:
    for value in (0.0, 100.0):
        assert (
            compute_quality_flags(_point(), value=value, measured_at=RECEIVED, received_at=RECEIVED)
            == []
        )


def test_unvalidated_point_is_flagged() -> None:
    flags = compute_quality_flags(
        _point(mapping_status="proposed"), value=45.5, measured_at=RECEIVED, received_at=RECEIVED
    )
    assert flags == ["unvalidated_point"]


def test_clock_tolerance_boundary() -> None:
    at_limit = RECEIVED + CLOCK_TOLERANCE
    beyond = at_limit + timedelta(seconds=1)
    assert (
        compute_quality_flags(_point(), value=1, measured_at=at_limit, received_at=RECEIVED) == []
    )
    assert compute_quality_flags(_point(), value=1, measured_at=beyond, received_at=RECEIVED) == [
        "clock_suspect"
    ]


def test_late_arrival_boundary() -> None:
    at_limit = RECEIVED - LATE_ARRIVAL
    beyond = at_limit - timedelta(seconds=1)
    assert (
        compute_quality_flags(_point(), value=1, measured_at=at_limit, received_at=RECEIVED) == []
    )
    assert compute_quality_flags(_point(), value=1, measured_at=beyond, received_at=RECEIVED) == [
        "late_arrival"
    ]
