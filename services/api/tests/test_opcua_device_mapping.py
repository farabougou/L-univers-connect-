"""Validateur de la configuration « opcua_device_mapping » et lecture de la
version active (app/connectors/device_mapping.py)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.config_versions import ConfigInvalid, activate_version, create_version, get_version
from app.connectors.device_mapping import OPCUA_DEVICE_MAPPING, get_active_opcua_mapping
from app.db import engine
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code
from tests.modbus_fixtures import cleanup_tenant, create_tenant_with_energy_and_power_points


@pytest.fixture
def tenant():
    created = create_tenant_with_energy_and_power_points("ClientOpcuaDeviceMapping")
    yield created
    cleanup_tenant(created)


def _content(tenant, **overrides):
    base = {
        "endpoint_url": "opc.tcp://192.168.1.60:4840/",
        "points": [{"point_id": str(tenant["energy_point_id"]), "node_id": "ns=2;i=1001"}],
    }
    base.update(overrides)
    return base


def _create(connection, tenant, **overrides):
    return create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=OPCUA_DEVICE_MAPPING,
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

    assert version["content"]["endpoint_url"] == "opc.tcp://192.168.1.60:4840/"
    assert version["content"]["points"][0]["node_id"] == "ns=2;i=1001"


def test_node_id_texte_est_accepte(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        version_id = _create(
            connection,
            tenant,
            points=[{"point_id": str(tenant["energy_point_id"]), "node_id": "ns=3;s=Temperature"}],
        )
        version = get_version(connection, version_id)

    assert version["content"]["points"][0]["node_id"] == "ns=3;s=Temperature"


def test_node_id_invalide_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "OPCUA_NODE_ID_INVALID"):
            _create(
                connection,
                tenant,
                points=[{"point_id": str(tenant["energy_point_id"]), "node_id": "pas-un-nodeid"}],
            )


def test_point_inexistant_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "OPCUA_POINT_NOT_FOUND"):
            _create(
                connection,
                tenant,
                points=[{"point_id": str(uuid.uuid4()), "node_id": "ns=2;i=1001"}],
            )


def test_meme_node_id_deux_fois_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "OPCUA_NODE_ID_DUPLICATED"):
            _create(
                connection,
                tenant,
                points=[
                    {"point_id": str(tenant["energy_point_id"]), "node_id": "ns=2;i=1001"},
                    {"point_id": str(tenant["power_point_id"]), "node_id": "ns=2;i=1001"},
                ],
            )


def test_meme_point_deux_fois_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "OPCUA_POINT_DUPLICATED"):
            _create(
                connection,
                tenant,
                points=[
                    {"point_id": str(tenant["energy_point_id"]), "node_id": "ns=2;i=1001"},
                    {"point_id": str(tenant["energy_point_id"]), "node_id": "ns=2;i=1002"},
                ],
            )


def test_champ_non_prevu_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "OPCUA_MAPPING_CONTENT_INVALID"):
            _create(connection, tenant, security_mode="none")


def test_get_active_opcua_mapping_renvoie_none_sans_version_active(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        _create(connection, tenant)  # reste en brouillon : jamais activée
        assert get_active_opcua_mapping(connection, equipment_id=tenant["location_id"]) is None


def test_get_active_opcua_mapping_renvoie_le_contenu_actif(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        version_id = _create(connection, tenant)
        activate_version(
            connection, version_id=version_id, activated_by="test", activated_at=datetime.now(UTC)
        )
        content = get_active_opcua_mapping(connection, equipment_id=tenant["location_id"])

    assert content is not None
    assert content["endpoint_url"] == "opc.tcp://192.168.1.60:4840/"
