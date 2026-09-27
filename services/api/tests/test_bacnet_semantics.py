"""UNIT_TESTED — devineur sémantique BACnet (app/connectors/bacnet_semantics.py),
sans réseau ni base de données (voir aussi test_bacnet_discovery_connector.py,
SIMULATOR_TESTED, et l'ADR BACnet V1 pour la distinction UNIT/SIMULATOR/FIELD)."""

from app.connectors.bacnet_semantics import guess_point_class, map_bacnet_unit


def test_temperature_unit_is_a_strong_signal():
    guess = guess_point_class(
        object_type="analog-input",
        value_type="number",
        units="degrees-celsius",
        object_name="Sonde ambiance",
        description=None,
    )
    assert guess.point_class == "temperature_sensor"
    assert guess.unit == "Cel"
    assert guess.confidence == 0.9
    assert guess.reason_code == "BACNET_UNITS_TEMPERATURE"


def test_temperature_output_named_consigne_is_a_setpoint():
    guess = guess_point_class(
        object_type="analog-output",
        value_type="number",
        units="degrees-celsius",
        object_name="Consigne depart",
        description=None,
    )
    assert guess.point_class == "temperature_setpoint"
    assert guess.reason_code == "BACNET_UNITS_TEMPERATURE_SETPOINT"


def test_pressure_unit_is_recognized():
    guess = guess_point_class(
        object_type="analog-input",
        value_type="number",
        units="kilopascals",
        object_name="P refoulement",
        description=None,
    )
    assert guess.point_class == "pressure_sensor"
    assert guess.unit == "kPa"
    assert guess.confidence == 0.9


def test_humidity_power_and_energy_units_are_recognized():
    humidity = guess_point_class(
        object_type="analog-input", value_type="number",
        units="percent-relative-humidity", object_name="HR salle", description=None,
    )
    power = guess_point_class(
        object_type="analog-input", value_type="number",
        units="kilowatts", object_name="Puissance active", description=None,
    )
    energy = guess_point_class(
        object_type="analog-input", value_type="number",
        units="kilowatt-hours", object_name="Energie", description=None,
    )
    assert humidity.point_class == "humidity_sensor"
    assert power.point_class == "electric_power_sensor"
    assert energy.point_class == "energy_meter_reading"


def test_name_only_keyword_gives_a_lower_confidence_than_a_unit():
    with_unit = guess_point_class(
        object_type="analog-input", value_type="number",
        units="degrees-celsius", object_name="Temp depart", description=None,
    )
    name_only = guess_point_class(
        object_type="analog-input", value_type="number",
        units=None, object_name="Temp depart chaudiere", description=None,
    )
    assert name_only.point_class == "temperature_sensor"
    assert name_only.confidence < with_unit.confidence


def test_no_unit_and_no_keyword_stays_unmapped():
    guess = guess_point_class(
        object_type="analog-input", value_type="number",
        units=None, object_name="AI-07", description=None,
    )
    assert guess.point_class is None
    assert guess.confidence is None
    assert guess.reason_code == "NO_RELIABLE_SIGNAL"


def test_unrecognized_bacnet_unit_is_never_forced_into_a_ucum_code():
    guess = guess_point_class(
        object_type="analog-input", value_type="number",
        units="grams-per-hour", object_name="Debit", description=None,
    )
    assert guess.unit is None
    assert map_bacnet_unit("grams-per-hour") is None


def test_binary_fault_keyword_is_recognized_in_french():
    for name in ("Defaut general", "Défaut ventilateur", "Fault status"):
        guess = guess_point_class(
            object_type="binary-input", value_type="boolean",
            units=None, object_name=name, description=None,
        )
        assert guess.point_class == "fault_status", name
        assert guess.confidence == 0.8


def test_binary_run_keyword_is_recognized():
    guess = guess_point_class(
        object_type="binary-input", value_type="boolean",
        units=None, object_name="Marche compresseur", description=None,
    )
    assert guess.point_class == "run_status"


def test_binary_output_run_keyword_is_a_command_not_a_status():
    guess = guess_point_class(
        object_type="binary-output", value_type="boolean",
        units=None, object_name="Marche pompe", description=None,
    )
    assert guess.point_class == "on_off_command"
    assert guess.reason_code == "NAME_KEYWORD_COMMAND"


def test_binary_enable_keyword_is_recognized():
    guess = guess_point_class(
        object_type="binary-value", value_type="boolean",
        units=None, object_name="Autorisation marche", description=None,
    )
    assert guess.point_class == "enable_status"


def test_binary_without_keyword_stays_unmapped():
    guess = guess_point_class(
        object_type="binary-input", value_type="boolean",
        units=None, object_name="BI-12", description=None,
    )
    assert guess.point_class is None
    assert guess.reason_code == "NO_RELIABLE_SIGNAL"


def test_multistate_is_never_guessed():
    # Règle des trois (app.point_vocabulary) : aucune classe multi-état
    # générique n'existe encore, donc jamais de correspondance inventée.
    guess = guess_point_class(
        object_type="multi-state-value", value_type="multistate",
        units=None, object_name="Mode CTA", description=None,
    )
    assert guess.point_class is None
    assert guess.confidence is None
    assert guess.reason_code == "MULTISTATE_NOT_YET_MAPPED"


def test_description_is_also_searched_for_keywords():
    guess = guess_point_class(
        object_type="binary-input", value_type="boolean",
        units=None, object_name="BI-03", description="Contact defaut disjoncteur",
    )
    assert guess.point_class == "fault_status"
