"""Mémoire opérationnelle : chronologie fusionnée d'un équipement ou d'un
exemplaire (feature-benchmark-matrix.md, « Mémoire opérationnelle »)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.findings import raise_or_repeat_finding
from app.main import app
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)
T0 = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)


def _create_tenant(name: str) -> dict:
    ids = {k: uuid.uuid4() for k in ("tenant_id", "site", "room", "loc", "model", "unit")}
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": ids["tenant_id"], "name": name, "slug": f"{name.lower()}-{ids['tenant_id']}"},
        )
        set_tenant_context(connection, ids["tenant_id"])
        p = {**ids}
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:site, :tenant_id, 'Site')"), p
        )
        connection.execute(
            text(
                "INSERT INTO spaces (id, tenant_id, site_id, space_type, code, name, valid_from) "
                "VALUES (:room, :tenant_id, :site, 'zone', 'CHAUF', 'Chaufferie', now())"
            ),
            p,
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:loc, :tenant_id, :site, 'pac-01', 'PAC 01')"
            ),
            p,
        )
        connection.execute(
            text(
                "INSERT INTO product_models "
                "(id, tenant_id, manufacturer, reference, equipment_type) "
                "VALUES (:model, :tenant_id, 'Fabricant Demo', 'PAC-X', 'heat_pump')"
            ),
            p,
        )
        connection.execute(
            text(
                "INSERT INTO physical_units (id, tenant_id, product_model_id, serial_number, "
                "lifecycle_state) VALUES (:unit, :tenant_id, :model, 'SN-PAC-1', 'installed')"
            ),
            p,
        )
    return ids


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientTimelineA")
    tenant_b = _create_tenant("ClientTimelineB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        purge_tenant(tenant["tenant_id"])


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(tenant_id=str(tenant['tenant_id']), roles=roles)}"
    }


def _call(method, path, headers, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def _manager(tenant):
    return _headers(tenant, ["responsable_exploitation"])


def _tech(tenant):
    return _headers(tenant, ["technicien"])


def test_timeline_merges_interventions_work_orders_and_alarms(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)

    intervention = _call(
        "POST",
        "/interventions",
        manager,
        json={
            "functional_location_id": str(tenant_a["loc"]),
            "started_at": T0.isoformat(),
            "summary": "Contrôle annuel",
        },
    )
    work_order = _call(
        "POST",
        "/work-orders",
        manager,
        json={"title": "Remplacer le filtre", "functional_location_id": str(tenant_a["loc"])},
    )
    _call(
        "PATCH",
        f"/work-orders/{work_order.json()['id']}/status",
        manager,
        json={"status": "in_progress"},
    )
    alarm = _call(
        "POST",
        "/alarms",
        manager,
        json={
            "severity": "critical",
            "message": "Défaut haute pression",
            "functional_location_id": str(tenant_a["loc"]),
        },
    )
    _call("POST", f"/alarms/{alarm.json()['id']}/acknowledge", manager, json={})

    assert intervention.status_code == 201, intervention.text
    assert work_order.status_code == 201, work_order.text
    assert alarm.status_code == 201, alarm.text

    response = _call("GET", f"/graph/nodes/{tenant_a['loc']}/timeline", _tech(tenant_a))
    assert response.status_code == 200, response.text
    entries = response.json()
    kinds = {entry["kind"] for entry in entries}
    assert kinds == {"intervention", "work_order", "alarm"}
    ats = [entry["at"] for entry in entries]
    assert ats == sorted(ats, reverse=True)

    work_order_entries = [e for e in entries if e["kind"] == "work_order"]
    assert {e["status"] for e in work_order_entries} == {"open", "in_progress"}
    assert all(e["title"] == "Remplacer le filtre" for e in work_order_entries)

    alarm_entries = [e for e in entries if e["kind"] == "alarm"]
    assert any(e["status"] == "acknowledged" for e in alarm_entries)
    assert all(e["title"] == "Défaut haute pression" for e in alarm_entries)


def test_timeline_of_another_tenant_node_is_not_found(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    response = _call("GET", f"/graph/nodes/{tenant_a['loc']}/timeline", _tech(tenant_b))
    assert response.status_code == 404
    assert response.json()["code"] == "NODE_NOT_FOUND"


def test_timeline_rejects_a_node_type_it_does_not_cover(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call("GET", f"/graph/nodes/{tenant_a['room']}/timeline", _tech(tenant_a))
    assert response.status_code == 422
    assert response.json()["code"] == "TIMELINE_NODE_TYPE_UNSUPPORTED"


def test_timeline_pagination_with_before_and_limit(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    for days_ago in (2, 1, 0):
        created = _call(
            "POST",
            "/interventions",
            manager,
            json={
                "functional_location_id": str(tenant_a["loc"]),
                "started_at": (T0 - timedelta(days=days_ago)).isoformat(),
                "summary": f"Intervention J-{days_ago}",
            },
        )
        assert created.status_code == 201, created.text

    first_page = _call(
        "GET",
        f"/graph/nodes/{tenant_a['loc']}/timeline",
        _tech(tenant_a),
        params={"limit": 1},
    ).json()
    assert [e["title"] for e in first_page] == ["Intervention J-0"]

    second_page = _call(
        "GET",
        f"/graph/nodes/{tenant_a['loc']}/timeline",
        _tech(tenant_a),
        params={"limit": 1, "before": first_page[0]["at"]},
    ).json()
    assert [e["title"] for e in second_page] == ["Intervention J-1"]


# --- Chronologie portefeuille : bloc « Activité récente » du Global Command Center --------


def test_recent_activity_merges_sources_across_the_whole_portfolio(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)

    other_loc = uuid.uuid4()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site, 'cta-01', 'CTA 01')"
            ),
            {"id": other_loc, "tenant_id": tenant_a["tenant_id"], "site": tenant_a["site"]},
        )
        raise_or_repeat_finding(
            connection,
            tenant_id=tenant_a["tenant_id"],
            dedup_key=f"test:{other_loc}",
            subject_node_id=other_loc,
            kind="anomaly",
            method="deterministic_rule",
            severity="warning",
            reason_code="TEST_REASON",
            reason_params={},
            evidence={},
            seen_at=T0,
            changed_by="technicien",
            title="Écart de température",
        )

    intervention = _call(
        "POST",
        "/interventions",
        manager,
        json={
            "functional_location_id": str(tenant_a["loc"]),
            "started_at": (T0 + timedelta(hours=1)).isoformat(),
            "summary": "Contrôle annuel",
        },
    )
    assert intervention.status_code == 201, intervention.text

    response = _call("GET", "/activity/recent", _tech(tenant_a))
    assert response.status_code == 200, response.text
    entries = response.json()

    kinds = {entry["kind"] for entry in entries}
    assert kinds == {"intervention", "finding"}
    locations = {entry["functional_location_id"] for entry in entries}
    assert locations == {str(tenant_a["loc"]), str(other_loc)}
    ats = [entry["at"] for entry in entries]
    assert ats == sorted(ats, reverse=True)
    assert "lifecycle" not in kinds


def test_recent_activity_respects_the_limit(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    for days_ago in (2, 1, 0):
        created = _call(
            "POST",
            "/interventions",
            manager,
            json={
                "functional_location_id": str(tenant_a["loc"]),
                "started_at": (T0 - timedelta(days=days_ago)).isoformat(),
                "summary": f"Intervention J-{days_ago}",
            },
        )
        assert created.status_code == 201, created.text

    response = _call("GET", "/activity/recent", _tech(tenant_a), params={"limit": 2})
    entries = response.json()
    assert [e["title"] for e in entries] == ["Intervention J-0", "Intervention J-1"]


def test_recent_activity_never_leaks_across_tenants(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    manager = _manager(tenant_a)
    created = _call(
        "POST",
        "/interventions",
        manager,
        json={
            "functional_location_id": str(tenant_a["loc"]),
            "started_at": T0.isoformat(),
            "summary": "Contrôle annuel",
        },
    )
    assert created.status_code == 201, created.text

    response = _call("GET", "/activity/recent", _tech(tenant_b))
    assert response.json() == []


def test_recent_activity_rejects_a_limit_out_of_range(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call("GET", "/activity/recent", _tech(tenant_a), params={"limit": 0})
    assert response.status_code == 400
    assert response.json()["code"] == "QUERY_LIMIT_OUT_OF_RANGE"
