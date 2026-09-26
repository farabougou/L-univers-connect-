"""Validateur de la configuration « modbus_device_mapping » et lecture de la
version active (app/connectors/device_mapping.py)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.config_versions import ConfigInvalid, activate_version, create_version, get_version
from app.connectors.device_mapping import MODBUS_DEVICE_MAPPING, get_active_mapping
from app.db import engine
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code
from tests.modbus_fixtures import cleanup_tenant, create_tenant_with_energy_and_power_points


@pytest.fixture
def tenant():
    created = create_tenant_with_energy_and_power_points("ClientDeviceMapping")
    yield created
    cleanup_tenant(created)


def _content(tenant, **overrides):
    base = {
        "device_type": "sdm120",
        "host": "192.168.1.50",
        "port": 502,
        "points": [
            {"point_id": str(tenant["energy_point_id"]), "register_name": "total_active_energy"}
        ],
    }
    base.update(overrides)
    return base


def _create(connection, tenant, **overrides):
    return create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=MODBUS_DEVICE_MAPPING,
        subject_key=str(tenant["location_id"]),
        content=_content(tenant, **overrides),
        author="test",
        reason="test",
    )


def test_contenu_valide_est_accepte_et_normalise(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        version_id = _create(connection, tenant)
        version = get_version(connection, version_id)

    assert version["content"]["host"] == "192.168.1.50"
    assert version["content"]["port"] == 502


def test_registre_inconnu_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "MODBUS_REGISTER_UNKNOWN"):
            _create(
                connection,
                tenant,
                points=[
                    {"point_id": str(tenant["energy_point_id"]), "register_name": "n_existe_pas"}
                ],
            )


def test_point_inexistant_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "MODBUS_POINT_NOT_FOUND"):
            _create(
                connection,
                tenant,
                points=[{"point_id": str(uuid.uuid4()), "register_name": "total_active_energy"}],
            )


def test_meme_registre_deux_fois_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "MODBUS_REGISTER_DUPLICATED"):
            _create(
                connection,
                tenant,
                points=[
                    {
                        "point_id": str(tenant["energy_point_id"]),
                        "register_name": "total_active_energy",
                    },
                    {
                        "point_id": str(tenant["power_point_id"]),
                        "register_name": "total_active_energy",
                    },
                ],
            )


def test_meme_point_deux_fois_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "MODBUS_POINT_DUPLICATED"):
            _create(
                connection,
                tenant,
                points=[
                    {"point_id": str(tenant["energy_point_id"]), "register_name": "voltage"},
                    {
                        "point_id": str(tenant["energy_point_id"]),
                        "register_name": "total_active_energy",
                    },
                ],
            )


def test_type_appareil_inconnu_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "MODBUS_MAPPING_CONTENT_INVALID"):
            _create(connection, tenant, device_type="marque_inconnue")


def test_champ_non_prevu_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "MODBUS_MAPPING_CONTENT_INVALID"):
            _create(connection, tenant, protocole="modbus_rtu_en_trop")


def test_get_active_mapping_renvoie_none_sans_version_active(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _create(connection, tenant)  # reste en brouillon : jamais activée
        assert get_active_mapping(connection, equipment_id=tenant["location_id"]) is None


def test_get_active_mapping_renvoie_le_contenu_actif(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        version_id = _create(connection, tenant)
        activate_version(
            connection, version_id=version_id, activated_by="test", activated_at=datetime.now(UTC)
        )
        content = get_active_mapping(connection, equipment_id=tenant["location_id"])

    assert content is not None
    assert content["host"] == "192.168.1.50"
