"""Validateur de la configuration « mqtt_device_mapping » et lecture de la
version active (app/connectors/device_mapping.py)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.config_versions import ConfigInvalid, activate_version, create_version, get_version
from app.connectors.device_mapping import MQTT_DEVICE_MAPPING, get_active_mqtt_mapping
from app.db import engine
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code
from tests.modbus_fixtures import cleanup_tenant, create_tenant_with_energy_and_power_points


@pytest.fixture
def tenant():
    created = create_tenant_with_energy_and_power_points("ClientMqttDeviceMapping")
    yield created
    cleanup_tenant(created)


def _content(tenant, **overrides):
    base = {
        "host": "192.168.1.70",
        "port": 1883,
        "points": [
            {"point_id": str(tenant["energy_point_id"]), "topic": "capteurs/cta-01/energie"}
        ],
    }
    base.update(overrides)
    return base


def _create(connection, tenant, **overrides):
    return create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=MQTT_DEVICE_MAPPING,
        subject_key=str(tenant["location_id"]),
        content=_content(tenant, **overrides),
        author="test",
        reason="test",
    )


def test_contenu_valide_est_accepte(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        version_id = _create(connection, tenant)
        version = get_version(connection, version_id)

    assert version["content"]["host"] == "192.168.1.70"
    assert version["content"]["port"] == 1883
    assert version["content"]["points"][0]["topic"] == "capteurs/cta-01/energie"


def test_port_par_defaut_est_1883(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        content = _content(tenant)
        del content["port"]
        version_id = create_version(
            connection,
            tenant_id=tenant["tenant_id"],
            config_type=MQTT_DEVICE_MAPPING,
            subject_key=str(tenant["location_id"]),
            content=content,
            author="test",
            reason="test",
        )
        version = get_version(connection, version_id)

    assert version["content"]["port"] == 1883


def test_point_inexistant_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "MQTT_POINT_NOT_FOUND"):
            _create(
                connection,
                tenant,
                points=[{"point_id": str(uuid.uuid4()), "topic": "capteurs/cta-01/energie"}],
            )


def test_meme_sujet_deux_fois_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "MQTT_TOPIC_DUPLICATED"):
            _create(
                connection,
                tenant,
                points=[
                    {"point_id": str(tenant["energy_point_id"]), "topic": "capteurs/cta-01/x"},
                    {"point_id": str(tenant["power_point_id"]), "topic": "capteurs/cta-01/x"},
                ],
            )


def test_meme_point_deux_fois_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "MQTT_POINT_DUPLICATED"):
            _create(
                connection,
                tenant,
                points=[
                    {"point_id": str(tenant["energy_point_id"]), "topic": "capteurs/cta-01/a"},
                    {"point_id": str(tenant["energy_point_id"]), "topic": "capteurs/cta-01/b"},
                ],
            )


def test_champ_non_prevu_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "MQTT_MAPPING_CONTENT_INVALID"):
            _create(connection, tenant, qos=1)


def test_get_active_mqtt_mapping_renvoie_none_sans_version_active(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _create(connection, tenant)  # reste en brouillon : jamais activée
        assert get_active_mqtt_mapping(connection, equipment_id=tenant["location_id"]) is None


def test_get_active_mqtt_mapping_renvoie_le_contenu_actif(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        version_id = _create(connection, tenant)
        activate_version(
            connection, version_id=version_id, activated_by="test", activated_at=datetime.now(UTC)
        )
        content = get_active_mqtt_mapping(connection, equipment_id=tenant["location_id"])

    assert content is not None
    assert content["host"] == "192.168.1.70"
