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


def _create_tenant(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    other_site_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        for site, site_name in ((site_id, "Site 1"), (other_site_id, "Site 2")):
            connection.execute(
                text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
                {"id": site, "tenant_id": tenant_id, "name": site_name},
            )
    return {"tenant_id": tenant_id, "site": site_id, "other_site": other_site_id}


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "functional_location_space_history",
            "functional_locations",
            "spaces",
            "sites",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientSpatialApiA")
    tenant_b = _create_tenant("ClientSpatialApiB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        _cleanup(tenant)


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant["tenant_id"]), roles=roles)
    return {"Authorization": f"Bearer {token}"}


def _post(path: str, body: dict, headers: dict):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.post(path, json=body, headers=headers)


def _get(path: str, headers: dict, **params):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.get(path, headers=headers, params=params)


def _build_tree(tenant: dict, headers: dict) -> dict:
    """Construction manuelle sans aucun plan : bâtiment → étage → pièce."""
    ids = {}
    parent = None
    for space_type, code in (("building", "BAT-A"), ("floor", "E1"), ("room", "104")):
        response = _post(
            "/spaces",
            {
                "site_id": str(tenant["site"]),
                "parent_id": parent,
                "space_type": space_type,
                "code": code,
                "name": f"{space_type} {code}",
            },
            headers,
        )
        assert response.status_code == 201, response.text
        parent = response.json()["id"]
        ids[space_type] = parent
    return ids


def test_manual_construction_without_any_plan(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["responsable_exploitation"])

    tree = _build_tree(tenant_a, headers)
    location = _post(
        "/functional-locations",
        {
            "site_id": str(tenant_a["site"]),
            "code": "cta-01",
            "name": "CTA 01",
            "kind": "equipment",
            "space_id": tree["room"],
        },
        headers,
    )
    spaces = _get("/spaces", headers, site_id=str(tenant_a["site"]))

    assert location.status_code == 201, location.text
    assert location.json()["kind"] == "equipment"
    assert location.json()["space_id"] == tree["room"]
    assert {s["code"] for s in spaces.json()} == {"BAT-A", "E1", "104"}

    history = _get(f"/functional-locations/{location.json()['id']}/space-history", headers)
    assert [(row["space_id"], row["reason"]) for row in history.json()] == [
        (tree["room"], "emplacement initial")
    ]


def test_technicien_can_read_spaces_but_not_create_them(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["technicien"])

    create = _post(
        "/spaces",
        {"site_id": str(tenant_a["site"]), "space_type": "building", "code": "X", "name": "X"},
        headers,
    )
    read = _get("/spaces", headers)

    assert create.status_code == 403
    assert read.status_code == 200


def test_wrong_placement_is_explained(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _post(
        "/spaces",
        {"site_id": str(tenant_a["site"]), "space_type": "room", "code": "R", "name": "R"},
        _headers(tenant_a, ["admin_tenant"]),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "SPACE_PLACEMENT_UNDER_SITE_FORBIDDEN"


def test_date_without_timezone_is_rejected(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _post(
        "/spaces",
        {
            "site_id": str(tenant_a["site"]),
            "space_type": "building",
            "code": "B",
            "name": "B",
            "valid_from": "2026-09-23T08:00:00",
        },
        _headers(tenant_a, ["admin_tenant"]),
    )
    assert response.status_code == 422


def test_other_tenant_spaces_are_invisible(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    tree = _build_tree(tenant_a, _headers(tenant_a, ["admin_tenant"]))
    headers_b = _headers(tenant_b, ["admin_tenant"])

    listed = _get("/spaces", headers_b)
    as_parent = _post(
        "/spaces",
        {
            "site_id": str(tenant_b["site"]),
            "parent_id": tree["floor"],
            "space_type": "room",
            "code": "R",
            "name": "R",
        },
        headers_b,
    )

    assert listed.json() == []
    assert as_parent.status_code == 404


def test_functional_location_parent_must_belong_to_the_tenant_and_site(two_tenants) -> None:
    """Correctif F2 : la position parente était seulement vérifiée par une clé
    étrangère, qui ignore l'isolation des tenants."""
    tenant_a, tenant_b = two_tenants
    parent_b = _post(
        "/functional-locations",
        {"site_id": str(tenant_b["site"]), "code": "sys-b", "name": "Système B"},
        _headers(tenant_b, ["admin_tenant"]),
    ).json()["id"]
    headers_a = _headers(tenant_a, ["admin_tenant"])
    parent_a_other_site = _post(
        "/functional-locations",
        {"site_id": str(tenant_a["other_site"]), "code": "sys-a2", "name": "Système A2"},
        headers_a,
    ).json()["id"]

    cross_tenant = _post(
        "/functional-locations",
        {"site_id": str(tenant_a["site"]), "parent_id": parent_b, "code": "c", "name": "c"},
        headers_a,
    )
    cross_site = _post(
        "/functional-locations",
        {
            "site_id": str(tenant_a["site"]),
            "parent_id": parent_a_other_site,
            "code": "c",
            "name": "c",
        },
        headers_a,
    )

    assert cross_tenant.status_code == 404
    assert cross_site.status_code == 409


def test_move_then_close_space_through_the_api(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["admin_tenant"])
    tree = _build_tree(tenant_a, headers)
    location_id = _post(
        "/functional-locations",
        {
            "site_id": str(tenant_a["site"]),
            "code": "cta-01",
            "name": "CTA",
            "space_id": tree["room"],
        },
        headers,
    ).json()["id"]

    refused_close = _post(f"/spaces/{tree['room']}/close", {"reason": "Rénovation"}, headers)
    moved = _post(
        f"/functional-locations/{location_id}/space",
        {"space_id": tree["floor"], "reason": "CTA déplacée en faux plafond d'étage"},
        headers,
    )
    close_without_reason = _post(f"/spaces/{tree['room']}/close", {}, headers)
    closed = _post(f"/spaces/{tree['room']}/close", {"reason": "Rénovation"}, headers)
    open_spaces = _get("/spaces", headers)
    all_spaces = _get("/spaces", headers, include_closed=True)

    assert refused_close.status_code == 409
    assert moved.status_code == 200
    assert [row["space_id"] for row in moved.json()] == [tree["room"], tree["floor"]]
    assert close_without_reason.status_code == 422
    assert closed.status_code == 200
    assert closed.json()["valid_to"] is not None
    assert tree["room"] not in {s["id"] for s in open_spaces.json()}
    assert tree["room"] in {s["id"] for s in all_spaces.json()}

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        actions = set(
            connection.execute(
                text("SELECT action FROM audit_log WHERE entity_id IN (:location, :room)"),
                {"location": location_id, "room": tree["room"]},
            ).scalars()
        )
    assert {"functional_location.space_changed", "space.closed", "space.created"} <= actions


def test_space_history_of_another_tenant_location_is_not_found(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    location_b = _post(
        "/functional-locations",
        {"site_id": str(tenant_b["site"]), "code": "b", "name": "b"},
        _headers(tenant_b, ["admin_tenant"]),
    ).json()["id"]

    response = _get(
        f"/functional-locations/{location_b}/space-history", _headers(tenant_a, ["admin_tenant"])
    )
    assert response.status_code == 404
