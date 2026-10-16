"""Connecteur de découverte BACnet (`discover_device`, `read_device_objects`)
contre un vrai appareil simulé (BACnet Lab, bacpypes3) — palier
SIMULATOR_TESTED, distinct de `test_bacnet_semantics.py` (UNIT_TESTED,
aucun réseau) et des essais terrain (FIELD_TESTED, BLOCKED_EXTERNAL_VALIDATION
jusqu'aux essais autorisés)."""

import pytest

from app.connectors.bacnet import BacnetReadError, discover_device, read_device_objects
from tests.bacnet_lab import BacnetLab

ADDRESS = "127.0.0.1:47820"
DEVICE_INSTANCE = 5010


@pytest.fixture(scope="module", autouse=True)
def lab():
    simulator = BacnetLab(ADDRESS, device_instance=DEVICE_INSTANCE)
    simulator.start()
    yield simulator
    simulator.stop()


def test_discover_device_identifie_un_appareil_simule_reel():
    info = discover_device(ADDRESS, timeout=3.0)

    assert info.device_instance == DEVICE_INSTANCE
    assert info.address == ADDRESS


def test_discover_device_appareil_injoignable_leve_une_erreur():
    with pytest.raises(BacnetReadError):
        discover_device("127.0.0.1:47899", timeout=0.5)


def test_read_device_objects_inventorie_uniquement_les_types_point():
    objects = read_device_objects(ADDRESS, DEVICE_INSTANCE, timeout=3.0)

    assert len(objects) == 8
    assert {obj.object_type for obj in objects} == {
        "analog-input",
        "analog-output",
        "binary-input",
        "binary-value",
        "multi-state-value",
    }


def test_read_device_objects_lit_les_metadonnees_reelles_par_readproperty():
    objects = read_device_objects(ADDRESS, DEVICE_INSTANCE, timeout=3.0)
    by_name = {obj.object_name: obj for obj in objects}

    temperature = by_name["T Depart CTA"]
    assert temperature.object_type == "analog-input"
    assert temperature.value_type == "number"
    assert temperature.units == "degrees-celsius"
    assert temperature.present_value_preview == "18.200000762939453"
    assert temperature.states is None

    unitless = by_name["AI-07"]
    assert unitless.units == "no-units"


def test_read_device_objects_numerote_les_etats_multi_etats_a_partir_de_un():
    objects = read_device_objects(ADDRESS, DEVICE_INSTANCE, timeout=3.0)
    mode = next(obj for obj in objects if obj.object_name == "Mode CTA")

    assert mode.value_type == "multistate"
    assert mode.states == {"1": "Arret", "2": "Confort", "3": "Reduit"}


def test_read_device_objects_appareil_injoignable_leve_une_erreur():
    with pytest.raises(BacnetReadError):
        read_device_objects("127.0.0.1:47899", DEVICE_INSTANCE, timeout=0.5)
