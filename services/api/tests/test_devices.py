"""Identité d'appareil Edge (app/devices.py) : provisionnement, secret
haché jamais recalculable, authentification sous le tenant annoncé,
isolation entre tenants, statut de communication dérivé sans être stocké.

Modèle cible (Mohamed, 24/09/2026) : identité par paire de clés et preuve
cryptographique applicative (`public_key_assertion`), `shared_secret` gardé
pour la seule compatibilité — voir le module."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jose import jwt
from sqlalchemy import text

from app.db import engine
from app.devices import (
    ASSERTION_ALGORITHM,
    MAX_ASSERTION_TTL,
    DeviceAuthInvalid,
    DeviceConflict,
    DeviceNotFound,
    DevicePublicKeyInvalid,
    authenticate_device,
    authenticate_device_by_assertion,
    communication_status,
    get_device,
    list_devices,
    provision_device,
    revoke_device,
    set_public_key,
    touch_last_seen,
)
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code

T0 = datetime(2026, 9, 24, 8, 0, tzinfo=UTC)


def _keypair() -> tuple[str, str]:
    """(clé privée PEM, clé publique PEM) — une paire fraîche par appel,
    jamais partagée entre deux appareils (voir le principe 1 de Mohamed)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private_pem, public_pem


def _assertion(
    private_pem: str,
    *,
    device_id: str,
    tenant_id: uuid.UUID,
    at: datetime,
    jti: str = "nonce-1",
    ttl: timedelta = timedelta(seconds=30),
) -> str:
    claims = {
        "device_id": device_id,
        "tenant_id": str(tenant_id),
        "jti": jti,
        "iat": int(at.timestamp()),
        "exp": int((at + ttl).timestamp()),
    }
    return jwt.encode(claims, private_pem, algorithm=ASSERTION_ALGORITHM)


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
                text("DELETE FROM device_assertion_nonces WHERE tenant_id = :id"),
                {"id": tenant_id},
            )
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


# --- Identité par clé publique (modèle cible, Mohamed 24/09/2026) ---------


def test_provisionnement_par_cle_publique_puis_authentification_reussie(two_tenants):
    tenant_a, _ = two_tenants
    private_pem, public_pem = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        device_id, secret = provision_device(
            connection,
            tenant_id=tenant_a,
            device_id="edge-01",
            created_by="test",
            public_key_pem=public_pem,
        )
        assert secret is None  # rien à transmettre, aucune clé privée côté serveur

        assertion = _assertion(private_pem, device_id="edge-01", tenant_id=tenant_a, at=T0)
        device = authenticate_device_by_assertion(
            connection, device_id="edge-01", assertion=assertion, at=T0
        )
        assert device["id"] == device_id
        assert device["credential_type"] == "public_key_assertion"


def test_assertion_signee_avec_une_mauvaise_cle_est_refusee(two_tenants):
    """La signature ne correspond pas à la clé publique enregistrée : même
    device_id et mêmes revendications, mais une autre paire de clés."""
    tenant_a, _ = two_tenants
    _, public_pem = _keypair()
    other_private_pem, _ = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(
            connection,
            tenant_id=tenant_a,
            device_id="edge-01",
            created_by="test",
            public_key_pem=public_pem,
        )
        assertion = _assertion(other_private_pem, device_id="edge-01", tenant_id=tenant_a, at=T0)
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device_by_assertion(
                connection, device_id="edge-01", assertion=assertion, at=T0
            )


def test_assertion_mal_formee_est_refusee(two_tenants):
    tenant_a, _ = two_tenants
    _, public_pem = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(
            connection,
            tenant_id=tenant_a,
            device_id="edge-01",
            created_by="test",
            public_key_pem=public_pem,
        )
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device_by_assertion(
                connection, device_id="edge-01", assertion="pas-un-jwt", at=T0
            )


def test_assertion_expiree_est_refusee(two_tenants):
    tenant_a, _ = two_tenants
    private_pem, public_pem = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(
            connection,
            tenant_id=tenant_a,
            device_id="edge-01",
            created_by="test",
            public_key_pem=public_pem,
        )
        assertion = _assertion(
            private_pem,
            device_id="edge-01",
            tenant_id=tenant_a,
            at=T0,
            ttl=timedelta(seconds=30),
        )
        later = T0 + timedelta(minutes=5)
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device_by_assertion(
                connection, device_id="edge-01", assertion=assertion, at=later
            )


def test_assertion_a_fenetre_de_validite_trop_longue_est_refusee(two_tenants):
    """Signature valide, pas encore expirée, mais une fenêtre exp - iat plus
    longue que ce que le serveur autorise (MAX_ASSERTION_TTL) : jamais
    confiance dans la durée que l'appareil s'attribuerait lui-même."""
    tenant_a, _ = two_tenants
    private_pem, public_pem = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(
            connection,
            tenant_id=tenant_a,
            device_id="edge-01",
            created_by="test",
            public_key_pem=public_pem,
        )
        assertion = _assertion(
            private_pem,
            device_id="edge-01",
            tenant_id=tenant_a,
            at=T0,
            ttl=MAX_ASSERTION_TTL + timedelta(seconds=1),
        )
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device_by_assertion(
                connection, device_id="edge-01", assertion=assertion, at=T0
            )


def test_rejeu_d_une_assertion_est_refuse(two_tenants):
    tenant_a, _ = two_tenants
    private_pem, public_pem = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(
            connection,
            tenant_id=tenant_a,
            device_id="edge-01",
            created_by="test",
            public_key_pem=public_pem,
        )
        assertion = _assertion(private_pem, device_id="edge-01", tenant_id=tenant_a, at=T0)
        authenticate_device_by_assertion(
            connection, device_id="edge-01", assertion=assertion, at=T0
        )
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device_by_assertion(
                connection, device_id="edge-01", assertion=assertion, at=T0
            )


def test_appareil_inconnu_est_refuse_par_assertion(two_tenants):
    tenant_a, _ = two_tenants
    private_pem, _ = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        assertion = _assertion(private_pem, device_id="n-existe-pas", tenant_id=tenant_a, at=T0)
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device_by_assertion(
                connection, device_id="n-existe-pas", assertion=assertion, at=T0
            )


def test_appareil_revoque_ne_peut_plus_s_authentifier_par_assertion(two_tenants):
    tenant_a, _ = two_tenants
    private_pem, public_pem = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        device_id, _ = provision_device(
            connection,
            tenant_id=tenant_a,
            device_id="edge-01",
            created_by="test",
            public_key_pem=public_pem,
        )
        revoke_device(connection, device_id=device_id, revoked_by="test", reason="Perdu", at=T0)
        assertion = _assertion(private_pem, device_id="edge-01", tenant_id=tenant_a, at=T0)
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device_by_assertion(
                connection, device_id="edge-01", assertion=assertion, at=T0
            )


def test_appareil_shared_secret_refuse_une_assertion(two_tenants):
    """Un appareil encore en compatibilité shared_secret n'a pas de clé
    publique enregistrée : une preuve signée est refusée, pas seulement
    ignorée."""
    tenant_a, _ = two_tenants
    private_pem, _ = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(connection, tenant_id=tenant_a, device_id="edge-01", created_by="test")
        assertion = _assertion(private_pem, device_id="edge-01", tenant_id=tenant_a, at=T0)
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device_by_assertion(
                connection, device_id="edge-01", assertion=assertion, at=T0
            )


def test_tenant_annonce_a_tort_ne_trouve_pas_l_appareil_par_assertion(two_tenants):
    tenant_a, tenant_b = two_tenants
    private_pem, public_pem = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        provision_device(
            connection,
            tenant_id=tenant_a,
            device_id="edge-01",
            created_by="test",
            public_key_pem=public_pem,
        )
    assertion = _assertion(private_pem, device_id="edge-01", tenant_id=tenant_a, at=T0)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b)
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device_by_assertion(
                connection, device_id="edge-01", assertion=assertion, at=T0
            )


def test_cle_publique_invalide_est_refusee_au_provisionnement(two_tenants):
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        with raises_code(DevicePublicKeyInvalid, "DEVICE_PUBLIC_KEY_INVALID"):
            provision_device(
                connection,
                tenant_id=tenant_a,
                device_id="edge-01",
                created_by="test",
                public_key_pem="pas une clé",
            )


def test_migration_shared_secret_vers_cle_publique(two_tenants):
    """set_public_key bascule un appareil shared_secret vers le modèle
    cible : l'ancien secret cesse aussitôt de fonctionner, la nouvelle
    preuve signée fonctionne."""
    tenant_a, _ = two_tenants
    private_pem, public_pem = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        device_id, secret = provision_device(
            connection, tenant_id=tenant_a, device_id="edge-01", created_by="test"
        )
        result = set_public_key(connection, device_id=device_id, public_key_pem=public_pem, at=T0)
        assert result["old_fingerprint"] is None
        assert result["new_fingerprint"]

        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device(connection, device_id="edge-01", secret=secret)

        assertion = _assertion(private_pem, device_id="edge-01", tenant_id=tenant_a, at=T0)
        device = authenticate_device_by_assertion(
            connection, device_id="edge-01", assertion=assertion, at=T0
        )
        assert device["credential_type"] == "public_key_assertion"


def test_rotation_de_cle_publique(two_tenants):
    tenant_a, _ = two_tenants
    old_private_pem, old_public_pem = _keypair()
    new_private_pem, new_public_pem = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        device_id, _ = provision_device(
            connection,
            tenant_id=tenant_a,
            device_id="edge-01",
            created_by="test",
            public_key_pem=old_public_pem,
        )
        result = set_public_key(
            connection, device_id=device_id, public_key_pem=new_public_pem, at=T0
        )
        assert result["old_fingerprint"] is not None
        assert result["old_fingerprint"] != result["new_fingerprint"]

        old_assertion = _assertion(old_private_pem, device_id="edge-01", tenant_id=tenant_a, at=T0)
        with raises_code(DeviceAuthInvalid, "DEVICE_AUTH_INVALID"):
            authenticate_device_by_assertion(
                connection, device_id="edge-01", assertion=old_assertion, at=T0
            )

        new_assertion = _assertion(
            new_private_pem, device_id="edge-01", tenant_id=tenant_a, at=T0, jti="nonce-2"
        )
        device = authenticate_device_by_assertion(
            connection, device_id="edge-01", assertion=new_assertion, at=T0
        )
        assert device["id"] == device_id


def test_set_public_key_sur_un_appareil_inconnu_est_refuse(two_tenants):
    tenant_a, _ = two_tenants
    _, public_pem = _keypair()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        with raises_code(DeviceNotFound, "DEVICE_NOT_FOUND"):
            set_public_key(connection, device_id=uuid.uuid4(), public_key_pem=public_pem, at=T0)
