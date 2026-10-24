"""Recherche globale (app/search.py) : sites, espaces, équipements,
identifiants/QR, ordres de travail — filtrée par tenant (RLS) et par motif
texte entièrement côté serveur."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.assets import create_functional_location
from app.db import engine
from app.maintenance import create_work_order
from app.search import search
from app.spatial import create_space
from app.tags import create_tag
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant

T0 = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)


def _create_tenant(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
            {"id": site_id, "tenant_id": tenant_id, "name": "Site Nord"},
        )
        space_id = create_space(
            connection,
            tenant_id=tenant_id,
            site_id=site_id,
            parent_id=None,
            space_type="building",
            code="BAT-1",
            name="Bâtiment 1 Nord",
            valid_from=T0,
        )
        location_id = create_functional_location(
            connection,
            tenant_id=tenant_id,
            site_id=site_id,
            parent_id=None,
            code="CTA-NORD-01",
            name="Centrale de traitement d'air Nord",
            kind="equipment",
            space_id=space_id,
            created_by="test",
        )
        work_order_id = create_work_order(
            connection,
            tenant_id=tenant_id,
            created_by="test",
            title="Remplacer le filtre de la CTA Nord",
            functional_location_id=location_id,
        )
        tag = create_tag(
            connection, tenant_id=tenant_id, node_id=location_id, tag_type="qr", created_by="test"
        )
    return {
        "tenant_id": tenant_id,
        "site_id": site_id,
        "space_id": space_id,
        "location_id": location_id,
        "work_order_id": work_order_id,
        "tag_code": tag["code"],
    }


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "asset_tags",
            "work_order_status_history",
            "work_orders",
            "functional_location_space_history",
            "functional_locations",
            "spaces",
            "sites",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientRechercheA")
    tenant_b = _create_tenant("ClientRechercheB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        _cleanup(tenant)


def test_finds_a_site_by_name(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        results = search(connection, query="Nord")
    kinds = {result["kind"] for result in results}
    assert "site" in kinds
    assert "functional_location" in kinds
    assert "work_order" in kinds


def test_finds_an_equipment_by_code(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        results = search(connection, query="CTA-NORD")
    assert [r for r in results if r["kind"] == "functional_location"][0]["id"] == str(
        tenant_a["location_id"]
    )


def test_finds_a_space_by_code(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        results = search(connection, query="BAT-1")
    assert [r for r in results if r["kind"] == "space"][0]["id"] == str(tenant_a["space_id"])


def test_finds_a_tag_by_code_and_resolves_to_its_node(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        results = search(connection, query=tenant_a["tag_code"])
    tag_results = [r for r in results if r["kind"] == "tag"]
    assert len(tag_results) == 1
    assert tag_results[0]["id"] == str(tenant_a["location_id"])


def test_finds_a_work_order_by_title(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        results = search(connection, query="filtre")
    assert [r for r in results if r["kind"] == "work_order"][0]["id"] == str(
        tenant_a["work_order_id"]
    )


def test_search_is_case_insensitive(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        results = search(connection, query="nord")
    assert len(results) > 0


def test_blank_query_returns_nothing(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        assert search(connection, query="   ") == []


def test_tenant_isolation(two_tenants) -> None:
    """Les deux tenants créent chacun un site « Nord » : une recherche dans
    le tenant B ne doit jamais renvoyer les identifiants du tenant A, même
    si le texte correspond aussi aux données du tenant B (RLS, pas un
    simple filtre sur le nom)."""
    tenant_a, tenant_b = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b["tenant_id"])
        results = search(connection, query="Nord")
    found_ids = {result["id"] for result in results}
    assert str(tenant_a["site_id"]) not in found_ids
    assert str(tenant_a["location_id"]) not in found_ids
