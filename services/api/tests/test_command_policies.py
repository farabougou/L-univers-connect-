"""Command Policy Engine (app/command_policies.py) : policy versionnée par
point commandable, au-delà des rôles globaux. Voir tests/test_commands.py
pour l'intégration avec create_command (policy bloque une commande) et
tests/test_commands_api.py pour le dry-run via l'API."""

from datetime import UTC, datetime

import pytest

from app.command_policies import (
    COMMAND_POINT_POLICY,
    PolicyViolation,
    enforce_policy,
    get_active_policy,
)
from app.config_versions import ConfigInvalid, activate_version, create_version
from app.db import engine
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code
from tests.modbus_fixtures import (
    activate_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_point,
)

T0 = datetime(2026, 10, 2, tzinfo=UTC)


@pytest.fixture
def commandable():
    created = create_tenant_with_energy_point("ClientPolicyCommande")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=5921,
        device_type="simulated_relay",
        points=[{"point_id": str(created["point_id"]), "register_name": "relay_state"}],
    )
    yield created
    cleanup_tenant(created)


def _create_policy(connection, tenant, **content):
    return create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=COMMAND_POINT_POLICY,
        subject_key=str(tenant["point_id"]),
        content=content,
        author="responsable",
        reason="test",
    )


def _activate(connection, version_id):
    activate_version(connection, version_id=version_id, activated_by="responsable", activated_at=T0)


# --- Validation du contenu --------------------------------------------------------------


def test_une_policy_avec_un_role_inconnu_est_refusee(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        with raises_code(ConfigInvalid, "COMMAND_POINT_POLICY_UNKNOWN_ROLE"):
            _create_policy(connection, commandable, allowed_roles=["super_admin"])


def test_une_policy_avec_un_champ_inconnu_est_refusee(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        with raises_code(ConfigInvalid, "COMMAND_POINT_POLICY_CONTENT_INVALID"):
            _create_policy(connection, commandable, autre_champ=True)


def test_une_policy_avec_une_liste_vide_est_refusee(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        with raises_code(ConfigInvalid, "COMMAND_POINT_POLICY_CONTENT_INVALID"):
            _create_policy(connection, commandable, allowed_roles=[])


# --- Aucune policy active = comportement inchangé ---------------------------------------


def test_aucune_policy_active_ne_bloque_rien():
    enforce_policy(None, requested_value=999.0, roles=[])


def test_get_active_policy_renvoie_none_sans_version_activee(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        _create_policy(connection, commandable, allowed_roles=["admin_tenant"])
        assert get_active_policy(connection, commandable["point_id"]) is None


# --- Policy active : restriction de rôle --------------------------------------------------


def test_policy_active_refuse_un_role_non_liste(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        version_id = _create_policy(connection, commandable, allowed_roles=["admin_tenant"])
        _activate(connection, version_id)
        policy = get_active_policy(connection, commandable["point_id"])

    with raises_code(PolicyViolation, "COMMAND_POLICY_ROLE_NOT_ALLOWED"):
        enforce_policy(policy, requested_value=1.0, roles=["technicien"])

    # Le rôle listé, lui, reste accepté.
    enforce_policy(policy, requested_value=1.0, roles=["admin_tenant"])


# --- Policy active : restriction de valeur -------------------------------------------------


def test_policy_active_refuse_une_valeur_non_listee(commandable):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable["tenant_id"])
        version_id = _create_policy(connection, commandable, allowed_values=[0.0, 1.0])
        _activate(connection, version_id)
        policy = get_active_policy(connection, commandable["point_id"])

    with raises_code(PolicyViolation, "COMMAND_POLICY_VALUE_NOT_ALLOWED"):
        enforce_policy(policy, requested_value=2.0, roles=["technicien"])

    enforce_policy(policy, requested_value=1.0, roles=["technicien"])
