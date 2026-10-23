import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)


@pytest.fixture
def tenant_id():
    tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": "Client API", "slug": f"client-api-{tenant_id}"},
        )

    yield tenant_id

    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "functional_location_assignments",
            "physical_unit_lifecycle_events",
            "physical_units",
            "functional_locations",
            "product_models",
            "sites",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _auth_headers(tenant_id: uuid.UUID, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant_id), roles=roles)
    return {"Authorization": f"Bearer {token}"}


def test_create_site_rejects_technicien_role(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["technicien"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/sites", json={"name": "Site A", "timezone": "Europe/Paris"}, headers=headers
        )

    assert response.status_code == 403


def test_full_asset_registry_flow_as_admin(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_response = client.post(
            "/sites",
            json={"name": "Site principal", "timezone": "Europe/Paris"},
            headers=headers,
        )
        assert site_response.status_code == 201
        site_id = site_response.json()["id"]

        model_response = client.post(
            "/product-models",
            json={
                "manufacturer": "Fabricant Demo",
                "reference": "PAC-100",
                "equipment_type": "heat_pump",
                "manufacturer_designation": "PAC air/eau réversible",
            },
            headers=headers,
        )
        assert model_response.status_code == 201
        product_model_id = model_response.json()["id"]

        unit_1_response = client.post(
            "/physical-units",
            json={"product_model_id": product_model_id, "serial_number": "SN-001"},
            headers=headers,
        )
        assert unit_1_response.status_code == 201
        unit_1_id = unit_1_response.json()["id"]

        unit_2_response = client.post(
            "/physical-units",
            json={"product_model_id": product_model_id, "serial_number": "SN-002"},
            headers=headers,
        )
        assert unit_2_response.status_code == 201
        unit_2_id = unit_2_response.json()["id"]

        location_response = client.post(
            "/functional-locations",
            json={"site_id": site_id, "code": "sous-station-1", "name": "Sous-station 1"},
            headers=headers,
        )
        assert location_response.status_code == 201
        location_id = location_response.json()["id"]

        assign_1_response = client.post(
            f"/functional-locations/{location_id}/assignment",
            json={"physical_unit_id": unit_1_id},
            headers=headers,
        )
        assert assign_1_response.status_code == 201

        occupant_response = client.get(
            f"/functional-locations/{location_id}/current-occupant", headers=headers
        )
        assert occupant_response.status_code == 200
        assert occupant_response.json()["physical_unit_id"] == unit_1_id

        # Remplacement de l'exemplaire : l'occupant courant doit changer,
        # sans casser les affectations passées (voir test_asset_registry.py
        # pour la preuve de non-régression de l'historique côté base).
        assign_2_response = client.post(
            f"/functional-locations/{location_id}/assignment",
            json={"physical_unit_id": unit_2_id},
            headers=headers,
        )
        assert assign_2_response.status_code == 201

        occupant_after_replacement = client.get(
            f"/functional-locations/{location_id}/current-occupant", headers=headers
        )
        assert occupant_after_replacement.json()["physical_unit_id"] == unit_2_id

        sites = client.get("/sites", headers=headers)
        assert [s["id"] for s in sites.json()] == [site_id]


def test_assignment_on_unknown_functional_location_returns_404(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    random_location_id = uuid.uuid4()
    random_unit_id = uuid.uuid4()

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            f"/functional-locations/{random_location_id}/assignment",
            json={"physical_unit_id": str(random_unit_id)},
            headers=headers,
        )

    assert response.status_code == 404


def test_list_sites_only_shows_own_tenant(tenant_id) -> None:
    other_tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": other_tenant_id, "name": "Autre client", "slug": f"autre-{other_tenant_id}"},
        )
        set_tenant_context(connection, other_tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
            {"id": uuid.uuid4(), "tenant_id": other_tenant_id, "name": "Site de l'autre client"},
        )

    headers = _auth_headers(tenant_id, ["admin_tenant"])
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            client.post(
                "/sites", json={"name": "Mon site", "timezone": "Europe/Paris"}, headers=headers
            )
            response = client.get("/sites", headers=headers)

        assert response.status_code == 200
        assert [site["name"] for site in response.json()] == ["Mon site"]
    finally:
        with engine.begin() as connection:
            set_tenant_context(connection, other_tenant_id)
            connection.execute(
                text("DELETE FROM sites WHERE tenant_id = :id"), {"id": other_tenant_id}
            )
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": other_tenant_id})


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"name": "Site sans fuseau"}, "VALIDATION_ERROR"),
        ({"name": "Site", "timezone": "Mars/Olympus"}, "TIMEZONE_UNKNOWN"),
        ({"name": "Site", "timezone": "UTC+2"}, "TIMEZONE_UNKNOWN"),
    ],
)
def test_a_site_requires_a_valid_iana_time_zone(tenant_id, body, code) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post("/sites", json=body, headers=headers)
    assert (response.status_code, response.json()["code"]) == (422, code)


def test_time_zone_of_an_existing_site_can_be_set_and_is_audited(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = client.post(
            "/sites", json={"name": "Site Lyon", "timezone": "Europe/Paris"}, headers=headers
        ).json()["id"]
        updated = client.put(
            f"/sites/{site_id}/timezone", json={"timezone": "Europe/Madrid"}, headers=headers
        )
        unknown = client.put(
            f"/sites/{uuid.uuid4()}/timezone", json={"timezone": "Europe/Paris"}, headers=headers
        )
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        payload = connection.execute(
            text("SELECT payload FROM audit_log WHERE action = 'site.timezone_set'")
        ).scalar()

    assert updated.json()["timezone"] == "Europe/Madrid"
    assert unknown.status_code == 404
    assert payload == {"previous": "Europe/Paris", "timezone": "Europe/Madrid"}


def test_archiving_a_site_hides_it_from_the_default_list_but_not_forever(tenant_id) -> None:
    """Jamais une suppression (CLAUDE.md, règle 3) : l'archivage masque
    seulement, `include_archived` et le désarchivage retrouvent le site
    intact."""
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = client.post(
            "/sites", json={"name": "Site en double", "timezone": "Europe/Paris"}, headers=headers
        ).json()["id"]

        archived = client.post(f"/sites/{site_id}/archive", headers=headers)
        assert archived.status_code == 200
        assert archived.json()["archived_at"] is not None

        default_list = client.get("/sites", headers=headers)
        assert site_id not in [s["id"] for s in default_list.json()]

        with_archived = client.get("/sites?include_archived=true", headers=headers)
        assert site_id in [s["id"] for s in with_archived.json()]

        # Idempotent : archiver un site déjà archivé ne casse rien.
        again = client.post(f"/sites/{site_id}/archive", headers=headers)
        assert again.status_code == 200

        unarchived = client.post(f"/sites/{site_id}/unarchive", headers=headers)
        assert unarchived.status_code == 200
        assert unarchived.json()["archived_at"] is None

        restored_list = client.get("/sites", headers=headers)
        assert site_id in [s["id"] for s in restored_list.json()]


def test_archiving_an_unknown_site_returns_404(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(f"/sites/{uuid.uuid4()}/archive", headers=headers)
    assert response.status_code == 404


def test_archiving_a_site_rejects_technicien_role(tenant_id) -> None:
    admin_headers = _auth_headers(tenant_id, ["admin_tenant"])
    technicien_headers = _auth_headers(tenant_id, ["technicien"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = client.post(
            "/sites",
            json={"name": "Site protégé", "timezone": "Europe/Paris"},
            headers=admin_headers,
        ).json()["id"]
        response = client.post(f"/sites/{site_id}/archive", headers=technicien_headers)
    assert response.status_code == 403


def test_archiving_a_site_is_audited(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = client.post(
            "/sites", json={"name": "Site audité", "timezone": "Europe/Paris"}, headers=headers
        ).json()["id"]
        client.post(f"/sites/{site_id}/archive", headers=headers)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        action = connection.execute(
            text(
                "SELECT action FROM audit_log WHERE entity_type = 'site' "
                "AND entity_id = :id AND action = 'site.archived'"
            ),
            {"id": site_id},
        ).scalar()
    assert action == "site.archived"


def test_archiving_a_functional_location_hides_it_from_the_default_list(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = client.post(
            "/sites", json={"name": "Site", "timezone": "Europe/Paris"}, headers=headers
        ).json()["id"]
        location_id = client.post(
            "/functional-locations",
            json={"site_id": site_id, "code": "CTA-DOUBLON", "name": "CTA en double"},
            headers=headers,
        ).json()["id"]

        archived = client.post(f"/functional-locations/{location_id}/archive", headers=headers)
        assert archived.status_code == 200
        assert archived.json()["archived_at"] is not None

        default_list = client.get("/functional-locations", headers=headers)
        assert location_id not in [item["id"] for item in default_list.json()]

        with_archived = client.get("/functional-locations?include_archived=true", headers=headers)
        assert location_id in [item["id"] for item in with_archived.json()]

        unarchived = client.post(f"/functional-locations/{location_id}/unarchive", headers=headers)
        assert unarchived.status_code == 200
        assert unarchived.json()["archived_at"] is None


def test_archiving_an_unknown_functional_location_returns_404(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(f"/functional-locations/{uuid.uuid4()}/archive", headers=headers)
    assert response.status_code == 404


def test_a_tenant_cannot_archive_another_tenants_site(tenant_id) -> None:
    """Isolation par tenant (CLAUDE.md, règle 2) : le site d'un autre client
    est invisible sous RLS, donc introuvable, jamais archivable."""
    other_tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": other_tenant_id, "name": "Autre client", "slug": f"autre-{other_tenant_id}"},
        )
        set_tenant_context(connection, other_tenant_id)
        other_site_id = uuid.uuid4()
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
            {"id": other_site_id, "tenant_id": other_tenant_id, "name": "Site de l'autre client"},
        )

    headers = _auth_headers(tenant_id, ["admin_tenant"])
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            response = client.post(f"/sites/{other_site_id}/archive", headers=headers)
        assert response.status_code == 404

        with engine.begin() as connection:
            set_tenant_context(connection, other_tenant_id)
            still_active = connection.execute(
                text("SELECT archived_at FROM sites WHERE id = :id"), {"id": other_site_id}
            ).scalar()
        assert still_active is None
    finally:
        with engine.begin() as connection:
            set_tenant_context(connection, other_tenant_id)
            connection.execute(
                text("DELETE FROM sites WHERE tenant_id = :id"), {"id": other_tenant_id}
            )
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": other_tenant_id})


# --- Archivage d'un site : ses équipements suivent (décision de Mohamed, 23/10/2026) ---------
#
# Constat sur le staging : archiver un site laissait ses équipements actifs (3 équipements
# restés actifs sur des sites archivés). Règle retenue : aucun équipement actif sur un site
# archivé. Le désarchivage d'un site ne restitue que les équipements archivés AVEC lui, jamais
# ceux qu'une personne avait archivés elle-même auparavant.


def _create_site(headers: dict[str, str], name: str) -> str:
    return client.post(
        "/sites", json={"name": name, "timezone": "Europe/Paris"}, headers=headers
    ).json()["id"]


def _create_location(headers: dict[str, str], site_id: str, code: str) -> str:
    response = client.post(
        "/functional-locations",
        json={"site_id": site_id, "code": code, "name": f"Équipement {code}"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _active_location_ids(headers: dict[str, str]) -> set[str]:
    return {item["id"] for item in client.get("/functional-locations", headers=headers).json()}


def _all_locations(headers: dict[str, str]) -> dict[str, dict]:
    response = client.get("/functional-locations?include_archived=true", headers=headers)
    return {item["id"]: item for item in response.json()}


def test_archiving_a_site_archives_its_equipment_and_only_its_own(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = _create_site(headers, "Site à archiver")
        other_site_id = _create_site(headers, "Site conservé")
        first = _create_location(headers, site_id, "CTA-A1")
        second = _create_location(headers, site_id, "CTA-A2")
        kept = _create_location(headers, other_site_id, "CTA-B1")

        assert client.post(f"/sites/{site_id}/archive", headers=headers).status_code == 200

        active = _active_location_ids(headers)
        assert first not in active and second not in active
        assert kept in active
        everything = _all_locations(headers)
        assert everything[first]["archived_at"] is not None
        assert everything[second]["archived_at"] is not None
        assert everything[kept]["archived_at"] is None


def test_unarchiving_a_site_restores_only_the_equipment_archived_with_it(tenant_id) -> None:
    """Un équipement qu'une personne avait archivé elle-même reste archivé : le désarchivage
    du site ne peut pas deviner qu'elle voulait le remettre en service."""
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = _create_site(headers, "Site réversible")
        archived_by_hand = _create_location(headers, site_id, "CTA-MAIN")
        archived_with_site = _create_location(headers, site_id, "CTA-SITE")
        assert (
            client.post(
                f"/functional-locations/{archived_by_hand}/archive", headers=headers
            ).status_code
            == 200
        )

        client.post(f"/sites/{site_id}/archive", headers=headers)
        unarchived = client.post(f"/sites/{site_id}/unarchive", headers=headers)
        assert unarchived.status_code == 200

        active = _active_location_ids(headers)
        assert archived_with_site in active
        assert archived_by_hand not in active
        everything = _all_locations(headers)
        assert everything[archived_with_site]["archived_at"] is None
        assert everything[archived_by_hand]["archived_at"] is not None


def test_archiving_by_hand_an_equipment_archived_with_its_site_makes_it_stay_archived(
    tenant_id,
) -> None:
    """Archiver soi-même un équipement déjà archivé avec son site est une décision explicite :
    il ne revient plus avec le site."""
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = _create_site(headers, "Site décision explicite")
        location_id = _create_location(headers, site_id, "CTA-DECIDE")
        client.post(f"/sites/{site_id}/archive", headers=headers)

        response = client.post(f"/functional-locations/{location_id}/archive", headers=headers)
        assert response.status_code == 200

        client.post(f"/sites/{site_id}/unarchive", headers=headers)
        assert location_id not in _active_location_ids(headers)


def test_archiving_an_already_archived_site_archives_equipment_left_active(tenant_id) -> None:
    """Réparation des données antérieures à la règle : un site archivé qui porte encore un
    équipement actif (cas du staging) est remis d'aplomb par un nouvel archivage, qui reste
    idempotent pour le site lui-même."""
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = _create_site(headers, "Site déjà archivé")
        location_id = _create_location(headers, site_id, "CTA-RESTE")
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("UPDATE sites SET archived_at = now(), archived_by = 'ancien' WHERE id = :id"),
            {"id": site_id},
        )
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        assert location_id in _active_location_ids(headers)

        assert client.post(f"/sites/{site_id}/archive", headers=headers).status_code == 200

        assert location_id not in _active_location_ids(headers)
        client.post(f"/sites/{site_id}/unarchive", headers=headers)
        assert location_id in _active_location_ids(headers)


def test_an_equipment_cannot_be_unarchived_while_its_site_is_archived(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = _create_site(headers, "Site archivé")
        location_id = _create_location(headers, site_id, "CTA-BLOQUE")
        client.post(f"/sites/{site_id}/archive", headers=headers)

        refused = client.post(f"/functional-locations/{location_id}/unarchive", headers=headers)

        assert refused.status_code == 409
        assert refused.json()["code"] == "SITE_ARCHIVED"
        assert location_id not in _active_location_ids(headers)


def test_an_equipment_archived_by_hand_can_be_unarchived_once_its_site_is_back(
    tenant_id,
) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = _create_site(headers, "Site de retour")
        location_id = _create_location(headers, site_id, "CTA-RETOUR")
        client.post(f"/functional-locations/{location_id}/archive", headers=headers)
        client.post(f"/sites/{site_id}/archive", headers=headers)
        client.post(f"/sites/{site_id}/unarchive", headers=headers)

        restored = client.post(f"/functional-locations/{location_id}/unarchive", headers=headers)

        assert restored.status_code == 200
        assert location_id in _active_location_ids(headers)


def test_an_equipment_cannot_be_created_on_an_archived_site(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = _create_site(headers, "Site fermé")
        client.post(f"/sites/{site_id}/archive", headers=headers)

        refused = client.post(
            "/functional-locations",
            json={"site_id": site_id, "code": "CTA-NEUF", "name": "Équipement neuf"},
            headers=headers,
        )

        assert refused.status_code == 409
        assert refused.json()["code"] == "SITE_ARCHIVED"
        assert _all_locations(headers) == {}


def test_archiving_a_site_audits_each_equipment_with_its_cause(tenant_id) -> None:
    headers = _auth_headers(tenant_id, ["admin_tenant"])
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        site_id = _create_site(headers, "Site audité en cascade")
        first = _create_location(headers, site_id, "CTA-AU1")
        second = _create_location(headers, site_id, "CTA-AU2")
        client.post(f"/sites/{site_id}/archive", headers=headers)
        client.post(f"/sites/{site_id}/unarchive", headers=headers)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        rows = connection.execute(
            text(
                "SELECT action, entity_type, entity_id, payload FROM audit_log "
                "WHERE action LIKE 'functional_location.%archived' OR action LIKE 'site.%archived' "
                "ORDER BY seq"
            )
        ).all()
    by_action = {}
    for action, entity_type, entity_id, payload in rows:
        by_action.setdefault(action, []).append((entity_type, entity_id, payload))

    cause = {"cause": "site", "site_id": site_id}
    assert sorted(entity_id for _, entity_id, _ in by_action["functional_location.archived"]) == (
        sorted([first, second])
    )
    assert all(payload == cause for _, _, payload in by_action["functional_location.archived"])
    assert sorted(entity_id for _, entity_id, _ in by_action["functional_location.unarchived"]) == (
        sorted([first, second])
    )
    assert all(payload == cause for _, _, payload in by_action["functional_location.unarchived"])
    assert by_action["site.archived"] == [("site", site_id, {"functional_locations": 2})]
    assert by_action["site.unarchived"] == [("site", site_id, {"functional_locations": 2})]


def test_a_tenant_cannot_archive_another_tenants_equipment_through_its_site(tenant_id) -> None:
    """Isolation (CLAUDE.md, règle 2) : le site d'un autre client est introuvable, et son
    équipement reste actif."""
    other_tenant_id = uuid.uuid4()
    other_site_id = uuid.uuid4()
    other_location_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": other_tenant_id, "name": "Autre client", "slug": f"autre-{other_tenant_id}"},
        )
        set_tenant_context(connection, other_tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
            {"id": other_site_id, "tenant_id": other_tenant_id, "name": "Site de l'autre client"},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name, kind) "
                "VALUES (:id, :tenant_id, :site_id, 'CTA-X', 'Équipement de l''autre', 'equipment')"
            ),
            {"id": other_location_id, "tenant_id": other_tenant_id, "site_id": other_site_id},
        )

    headers = _auth_headers(tenant_id, ["admin_tenant"])
    try:
        with patch("app.auth.fetch_jwks", return_value=JWKS):
            assert (
                client.post(f"/sites/{other_site_id}/archive", headers=headers).status_code == 404
            )
            assert (
                client.post(f"/sites/{other_site_id}/unarchive", headers=headers).status_code == 404
            )

        with engine.begin() as connection:
            set_tenant_context(connection, other_tenant_id)
            archived_at = connection.execute(
                text("SELECT archived_at FROM functional_locations WHERE id = :id"),
                {"id": other_location_id},
            ).scalar()
        assert archived_at is None
    finally:
        with engine.begin() as connection:
            set_tenant_context(connection, other_tenant_id)
            connection.execute(
                text("DELETE FROM functional_locations WHERE tenant_id = :id"),
                {"id": other_tenant_id},
            )
            connection.execute(
                text("DELETE FROM sites WHERE tenant_id = :id"), {"id": other_tenant_id}
            )
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": other_tenant_id})
