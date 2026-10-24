"""Mode de point — manuel/automatique (app/point_control_mode.py), priorité
« modes/consignes » de la feuille de route V2."""

from datetime import UTC, datetime

import pytest

from app.config_versions import ConfigConflict, ConfigInvalid, activate_version, create_version
from app.db import engine
from app.point_control_mode import POINT_CONTROL_MODE, get_control_mode
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code
from tests.modbus_fixtures import cleanup_tenant, create_tenant_with_energy_point

T0 = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


@pytest.fixture
def tenant():
    created = create_tenant_with_energy_point("ClientModePoint")
    yield created
    cleanup_tenant(created)


def _create_mode(connection, tenant, mode):
    return create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=POINT_CONTROL_MODE,
        subject_key=str(tenant["point_id"]),
        content={"mode": mode},
        author="responsable",
        reason="test",
    )


def test_un_point_sans_mode_jamais_active_est_manuel(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        assert get_control_mode(connection, tenant["point_id"]) == "manual"


def test_un_mode_invalide_est_refuse(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with raises_code(ConfigInvalid, "POINT_CONTROL_MODE_CONTENT_INVALID"):
            _create_mode(connection, tenant, "auto")  # valeur hors énumération


def test_basculer_en_automatique_exige_une_deuxieme_personne(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        version_id = _create_mode(connection, tenant, "automatic")
        with raises_code(ConfigConflict, "CONFIG_ACTIVATION_REQUIRES_SECOND_PERSON"):
            activate_version(
                connection, version_id=version_id, activated_by="responsable", activated_at=T0
            )


def test_le_mode_actif_est_automatique_une_fois_valide_par_une_deuxieme_personne(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        version_id = _create_mode(connection, tenant, "automatic")
        activate_version(
            connection, version_id=version_id, activated_by="admin_tenant", activated_at=T0
        )
        assert get_control_mode(connection, tenant["point_id"]) == "automatic"


def test_repasser_en_manuel_desactive_immediatement_l_automatique(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        first = _create_mode(connection, tenant, "automatic")
        activate_version(connection, version_id=first, activated_by="admin_tenant", activated_at=T0)
        second = _create_mode(connection, tenant, "manual")
        activate_version(
            connection, version_id=second, activated_by="admin_tenant", activated_at=T0
        )
        assert get_control_mode(connection, tenant["point_id"]) == "manual"
