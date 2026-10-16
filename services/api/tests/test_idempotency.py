"""Envois mobiles rejouables sans doublon (clé d'idempotence `client_ref`).

Cas réel : le serveur enregistre l'intervention, mais la réponse se perd (le
réseau coupe à ce moment-là). Le téléphone ne le sait pas et renvoie. Avec la
même `client_ref`, le serveur renvoie l'intervention déjà créée au lieu d'en
créer une seconde. Même règle que pour les mesures : même contenu → 200 sans
effet ; contenu différent → 409, rien n'est écrasé.
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)
STARTED_AT = "2026-09-23T08:00:00.000Z"


def _create_tenant(name: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
    return tenant_id


@pytest.fixture
def tenants():
    tenant_a = _create_tenant("ClientIdempotenceA")
    tenant_b = _create_tenant("ClientIdempotenceB")
    yield tenant_a, tenant_b
    for tenant_id in (tenant_a, tenant_b):
        purge_tenant(tenant_id)


def _post(tenant_id: uuid.UUID, path: str, body: dict, sub: str = "technicien-test"):
    token = make_token(tenant_id=str(tenant_id), roles=["technicien"], sub=sub)
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.post(path, json=body, headers={"Authorization": f"Bearer {token}"})


def _intervention(client_ref: str | None = "local-1727078400000-a1b2c3d4", **overrides):
    body = {
        "summary": "Nettoyage filtre CTA",
        "started_at": STARTED_AT,
        "checklist": {"filtre_ok": True},
        **overrides,
    }
    if client_ref is not None:
        body["client_ref"] = client_ref
    return body


def _count(tenant_id: uuid.UUID, query: str) -> int:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        return connection.execute(text(query)).scalar()


# --- Interventions ------------------------------------------------


def test_resending_the_same_intervention_does_not_duplicate_it(tenants) -> None:
    tenant_a, _ = tenants

    first = _post(tenant_a, "/interventions", _intervention())
    second = _post(tenant_a, "/interventions", _intervention())

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert first.json()["client_ref"] == "local-1727078400000-a1b2c3d4"
    assert _count(tenant_a, "SELECT count(*) FROM interventions") == 1
    # Une seule action réelle, donc une seule entrée d'audit.
    assert (
        _count(tenant_a, "SELECT count(*) FROM audit_log WHERE action = 'intervention.logged'") == 1
    )


@pytest.mark.parametrize(
    "change",
    [
        {"summary": "Autre résumé"},
        {"checklist": {"filtre_ok": False}},
        {"started_at": "2026-09-23T09:00:00.000Z"},
        {"intervention_type": "ronde"},
    ],
)
def test_same_client_ref_with_different_content_is_refused(tenants, change) -> None:
    tenant_a, _ = tenants

    _post(tenant_a, "/interventions", _intervention())
    conflict = _post(tenant_a, "/interventions", _intervention(**change))

    assert conflict.status_code == 409
    assert _count(tenant_a, "SELECT count(*) FROM interventions") == 1


def test_same_client_ref_from_another_technician_is_refused(tenants) -> None:
    tenant_a, _ = tenants

    _post(tenant_a, "/interventions", _intervention(), sub="technicien-1")
    conflict = _post(tenant_a, "/interventions", _intervention(), sub="technicien-2")

    assert conflict.status_code == 409


def test_interventions_without_client_ref_are_never_merged(tenants) -> None:
    tenant_a, _ = tenants

    first = _post(tenant_a, "/interventions", _intervention(client_ref=None))
    second = _post(tenant_a, "/interventions", _intervention(client_ref=None))

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]


def test_client_ref_is_scoped_to_the_tenant(tenants) -> None:
    """La même référence chez deux clients : deux interventions distinctes,
    et aucun des deux ne reçoit celle de l'autre."""
    tenant_a, tenant_b = tenants

    in_a = _post(tenant_a, "/interventions", _intervention())
    in_b = _post(tenant_b, "/interventions", _intervention())

    assert (in_a.status_code, in_b.status_code) == (201, 201)
    assert in_a.json()["id"] != in_b.json()["id"]
    assert _count(tenant_b, "SELECT count(*) FROM interventions") == 1


@pytest.mark.parametrize("bad", ["court", "a" * 101, "avec espace-123", "é-accentué-123"])
def test_invalid_client_ref_is_rejected(tenants, bad) -> None:
    tenant_a, _ = tenants

    response = _post(tenant_a, "/interventions", _intervention(client_ref=bad))

    assert response.status_code == 422


@pytest.mark.parametrize("started_at", [None, "2026-09-23T08:00:00"])
def test_replayable_intervention_must_carry_its_aware_date(tenants, started_at) -> None:
    """Sans date (ou sans fuseau), le serveur prendrait l'heure du renvoi et
    croirait à une autre intervention."""
    tenant_a, _ = tenants
    body = _intervention()
    if started_at is None:
        del body["started_at"]
    else:
        body["started_at"] = started_at

    response = _post(tenant_a, "/interventions", body)

    assert response.status_code == 422


# --- Photos ------------------------------------------------


def _photo_key(tenant_id: uuid.UUID, intervention_id: str) -> str:
    response = _post(
        tenant_id,
        f"/interventions/{intervention_id}/photos/upload-url",
        {"filename": "filtre.jpg", "content_type": "image/jpeg"},
    )
    assert response.status_code == 200
    return response.json()["object_key"]


def test_resending_the_same_photo_confirmation_does_not_duplicate_it(tenants) -> None:
    """Au nouvel essai, le téléphone renvoie la photo (nouvelle clé de
    stockage) : le serveur garde la première et ne crée rien de plus."""
    tenant_a, _ = tenants
    intervention_id = _post(tenant_a, "/interventions", _intervention()).json()["id"]
    path = f"/interventions/{intervention_id}/photos"

    def confirm():
        key = _photo_key(tenant_a, intervention_id)
        return _post(tenant_a, path, {"object_key": key, "client_ref": "p-1234567"})

    first = confirm()
    second = confirm()

    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["id"] == first.json()["id"]
    assert _count(tenant_a, "SELECT count(*) FROM intervention_photos") == 1
    assert (
        _count(tenant_a, "SELECT count(*) FROM audit_log WHERE action = 'intervention.photo_added'")
        == 1
    )


def test_photo_client_ref_reused_on_another_intervention_is_refused(tenants) -> None:
    tenant_a, _ = tenants
    first_id = _post(tenant_a, "/interventions", _intervention("local-ref-00000001")).json()["id"]
    other_id = _post(tenant_a, "/interventions", _intervention("local-ref-00000002")).json()["id"]

    _post(
        tenant_a,
        f"/interventions/{first_id}/photos",
        {"object_key": _photo_key(tenant_a, first_id), "client_ref": "p-1234567"},
    )
    conflict = _post(
        tenant_a,
        f"/interventions/{other_id}/photos",
        {"object_key": _photo_key(tenant_a, other_id), "client_ref": "p-1234567"},
    )

    assert conflict.status_code == 409


# --- Faille corrigée : clé de stockage d'un autre client ou d'une autre intervention ---


def test_photo_key_from_another_tenant_is_refused(tenants) -> None:
    """Avant ce correctif, n'importe quelle clé était acceptée : connaître la
    clé d'une photo d'un autre client suffisait pour obtenir un lien de
    téléchargement. L'isolation ne doit jamais reposer sur une clé difficile à
    deviner."""
    tenant_a, tenant_b = tenants
    id_a = _post(tenant_a, "/interventions", _intervention("local-ref-0000000a")).json()["id"]
    id_b = _post(tenant_b, "/interventions", _intervention("local-ref-0000000b")).json()["id"]
    key_of_a = _photo_key(tenant_a, id_a)

    response = _post(tenant_b, f"/interventions/{id_b}/photos", {"object_key": key_of_a})

    assert response.status_code == 422
    assert _count(tenant_b, "SELECT count(*) FROM intervention_photos") == 0


@pytest.mark.parametrize(
    "make_key",
    [
        lambda tenant, other, _: f"{tenant}/{other}/photo.jpg",
        lambda tenant, _, own: f"{tenant}/{own}/../autre/photo.jpg",
        lambda tenant, _, own: f"{tenant}/{own}/",
        lambda *_: "photo.jpg",
    ],
)
def test_photo_key_must_belong_to_the_intervention(tenants, make_key) -> None:
    tenant_a, _ = tenants
    own = _post(tenant_a, "/interventions", _intervention("local-ref-00000001")).json()["id"]
    other = _post(tenant_a, "/interventions", _intervention("local-ref-00000002")).json()["id"]

    response = _post(
        tenant_a,
        f"/interventions/{own}/photos",
        {"object_key": make_key(tenant_a, other, own)},
    )

    assert response.status_code == 422
