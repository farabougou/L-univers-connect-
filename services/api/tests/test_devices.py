"""Identité d'appareil Edge (app/devices.py) : provisionnement, secret
haché jamais recalculable, authentification sous le tenant annoncé,
isolation entre tenants, statut de communication dérivé sans être stocké."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db import engine
from app.devices import (
    DeviceAuthInvalid,
    DeviceConflict,
    authenticate_device,
    communication_status,
    get_device,
    list_devices,
    provision_device,
    revoke_device,
    touch_last_seen,
)
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code

T0 = datetime(2026, 9, 24, 8, 0, tzinfo=UTC)


@pytest.fixture
def two_tenants():
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            [
                {"id": tenant_a, "name": "ClientDevicesA", "slug": f"devices-a-{tenant_a}"},
                {"id": tenant_b, "name": "ClientDevicesB", "slug": f"devices-b-{tenant_b}"},
            ],
        )
    yield tenant_a, tenant_b
    with engine.begin() as connection:
        for tenant_id in (tenant_a, tenant_b):
            set_tenant_context(connection, tenant_id)
            connection.execute(
                text("DELETE FROM edge_devices WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM tenants WHERE id IN (:a, :b)"), {"a": tenant_a, "b": tenant_b}
        )


def test_provisionnement_puis_authentification_reussie(two_tenants):
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        device_id, secret = provision_device(
            connection, tenant_id=tenant_a, device_id="sdm120-cpt01", created_by="test"
        )
        assert len(secret) >= 32  # haute entropie, pas un mot de passe court

        device = authenticate_device(connection, device_id="sdm120-cpt01", secret=secret)
        assert device["id"] == device_id
        assert device["status"] == "active"


def test_secret_errone_est_refuse(two_tenants):
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(
            connection, tenant_id=tenant_a, device_id="sdm120-cpt01", created_by="test"
        )
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device(connection, device_id="sdm120-cpt01", secret="mauvais-secret")


def test_device_id_inconnu_est_refuse(two_tenants):
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device(connection, device_id="n-existe-pas", secret="peu-importe")


def test_tenant_annonce_a_tort_ne_trouve_pas_l_appareil_de_l_autre(two_tenants):
    """Le vrai test d'isolation : device_id et secret corrects, mais sous le
    contexte du MAUVAIS tenant — RLS doit rendre l'appareil invisible."""
    tenant_a, tenant_b = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        _, secret = provision_device(
            connection, tenant_id=tenant_a, device_id="sdm120-cpt01", created_by="test"
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b)
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device(connection, device_id="sdm120-cpt01", secret=secret)


def test_meme_device_id_permis_pour_deux_tenants_differents(two_tenants):
    tenant_a, tenant_b = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(connection, tenant_id=tenant_a, device_id="cpt01", created_by="test")
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b)
        # Ne lève rien : l'unicité de device_id est par tenant, pas globale.
        provision_device(connection, tenant_id=tenant_b, device_id="cpt01", created_by="test")


def test_meme_device_id_deux_fois_pour_le_meme_tenant_est_refuse(two_tenants):
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(connection, tenant_id=tenant_a, device_id="cpt01", created_by="test")
        with raises_code(DeviceConflict, "DEVICE_ID_ALREADY_USED"):
            provision_device(connection, tenant_id=tenant_a, device_id="cpt01", created_by="test")


def test_liste_des_appareils_isolee_par_tenant(two_tenants):
    tenant_a, tenant_b = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(connection, tenant_id=tenant_a, device_id="cpt-a", created_by="test")
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b)
        provision_device(connection, tenant_id=tenant_b, device_id="cpt-b", created_by="test")

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        seen_by_a = list_devices(connection)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b)
        seen_by_b = list_devices(connection)

    assert [d["device_id"] for d in seen_by_a] == ["cpt-a"]
    assert [d["device_id"] for d in seen_by_b] == ["cpt-b"]


def test_appareil_revoque_ne_peut_plus_s_authentifier(two_tenants):
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        device_id, secret = provision_device(
            connection, tenant_id=tenant_a, device_id="cpt01", created_by="test"
        )
        revoke_device(connection, device_id=device_id, revoked_by="test", reason="Perdu", at=T0)
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device(connection, device_id="cpt01", secret=secret)


def test_revoquer_deux_fois_est_refuse(two_tenants):
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        device_id, _ = provision_device(
            connection, tenant_id=tenant_a, device_id="cpt01", created_by="test"
        )
        revoke_device(connection, device_id=device_id, revoked_by="test", reason="Perdu", at=T0)
        with raises_code(DeviceConflict, "DEVICE_ALREADY_REVOKED_OR_NOT_FOUND"):
            revoke_device(connection, device_id=device_id, revoked_by="test", reason="Perdu", at=T0)


def test_statut_communication_derive_sans_etre_stocke(two_tenants):
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        device_id, _ = provision_device(
            connection, tenant_id=tenant_a, device_id="cpt01", created_by="test"
        )
        device = get_device(connection, device_id)
        assert communication_status(device, now=T0) == "unknown"

        touch_last_seen(connection, device_id=device_id, at=T0)
        device = get_device(connection, device_id)
        assert communication_status(device, now=T0 + timedelta(minutes=1)) == "online"
        assert communication_status(device, now=T0 + timedelta(minutes=10)) == "offline"
