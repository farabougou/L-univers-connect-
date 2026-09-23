import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.assets import assign_physical_unit
from app.db import engine
from app.lifecycle import LifecycleError, change_state, current_state, lifecycle_history
from app.main import app
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)
T0 = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)


def _create_tenant(name: str) -> dict:
    ids = {
        key: uuid.uuid4() for key in ("tenant_id", "site", "model", "loc_a", "loc_b", "u1", "u2")
    }
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": ids["tenant_id"], "name": name, "slug": f"{name.lower()}-{ids['tenant_id']}"},
        )
        set_tenant_context(connection, ids["tenant_id"])
        params = {"tenant_id": ids["tenant_id"], "site": ids["site"], "model": ids["model"]}
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:site, :tenant_id, 'Site')"),
            params,
        )
        connection.execute(
            text(
                "INSERT INTO product_models "
                "(id, tenant_id, manufacturer, reference, equipment_type) "
                "VALUES (:model, :tenant_id, 'Fabricant Demo', 'PAC-1', 'heat_pump')"
            ),
            params,
        )
        for loc in ("loc_a", "loc_b"):
            connection.execute(
                text(
                    "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                    "VALUES (:id, :tenant_id, :site, :code, :code)"
                ),
                {**params, "id": ids[loc], "code": loc},
            )
        for unit in ("u1", "u2"):
            connection.execute(
                text(
                    "INSERT INTO physical_units (id, tenant_id, product_model_id, serial_number) "
                    "VALUES (:id, :tenant_id, :model, :serial)"
                ),
                {**params, "id": ids[unit], "serial": f"SN-{ids[unit]}"},
            )
    return ids


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientLifecycleA")
    tenant_b = _create_tenant("ClientLifecycleB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        purge_tenant(tenant["tenant_id"])


@contextmanager
def _in(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        yield connection


def _assign(connection, tenant, unit, loc, at=T0):
    return assign_physical_unit(
        connection,
        tenant_id=tenant["tenant_id"],
        functional_location_id=tenant[loc],
        physical_unit_id=tenant[unit],
        valid_from=at,
        changed_by="technicien",
    )


def test_new_unit_starts_in_stock(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in(tenant_a) as connection:
        assert current_state(connection, tenant_a["u1"]) == "in_stock"


def test_installation_and_replacement_follow_the_assignments(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in(tenant_a) as connection:
        _assign(connection, tenant_a, "u1", "loc_a")
        _assign(connection, tenant_a, "u2", "loc_a", at=T0 + timedelta(days=30))
        states = (
            current_state(connection, tenant_a["u1"]),
            current_state(connection, tenant_a["u2"]),
        )
        history_u1 = [
            (e["from_state"], e["to_state"]) for e in lifecycle_history(connection, tenant_a["u1"])
        ]

    assert states == ("removed", "installed")
    assert history_u1 == [("in_stock", "installed"), ("installed", "removed")]


def test_a_unit_cannot_be_installed_in_two_positions_at_once(two_tenants) -> None:
    """Corrige un trou d'avant F5 : rien n'empêchait d'affecter le même
    exemplaire à deux positions en même temps."""
    tenant_a, _ = two_tenants
    with _in(tenant_a) as connection:
        _assign(connection, tenant_a, "u1", "loc_a")
    with raises_code(LifecycleError, "UNIT_NOT_INSTALLABLE"):
        with _in(tenant_a) as connection:
            _assign(connection, tenant_a, "u1", "loc_b")


def test_the_same_unit_cannot_be_assigned_twice_to_its_position(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in(tenant_a) as connection:
        _assign(connection, tenant_a, "u1", "loc_a")
    with raises_code(LifecycleError, "UNIT_ALREADY_AT_LOCATION"):
        with _in(tenant_a) as connection:
            _assign(connection, tenant_a, "u1", "loc_a")


def _change(connection, tenant, to_state, unit="u1"):
    change_state(
        connection,
        tenant_id=tenant["tenant_id"],
        physical_unit_id=tenant[unit],
        to_state=to_state,
        occurred_at=T0,
        changed_by="responsable",
    )


def test_commissioning_then_service(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in(tenant_a) as connection:
        _assign(connection, tenant_a, "u1", "loc_a")
        for state in ("commissioned", "in_service", "out_of_service", "in_service"):
            _change(connection, tenant_a, state)
        assert current_state(connection, tenant_a["u1"]) == "in_service"


@pytest.mark.parametrize(
    ("to_state", "code"),
    [
        ("installed", "LIFECYCLE_STATE_FROM_ASSIGNMENT"),
        ("in_service", "LIFECYCLE_TRANSITION_FORBIDDEN"),
        ("flying", "LIFECYCLE_STATE_UNKNOWN"),
    ],
)
def test_invalid_manual_transitions(two_tenants, to_state, code) -> None:
    tenant_a, _ = two_tenants
    with raises_code(LifecycleError, code):
        with _in(tenant_a) as connection:
            _change(connection, tenant_a, to_state)


def test_decommissioned_unit_cannot_be_installed(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in(tenant_a) as connection:
        _change(connection, tenant_a, "decommissioned")
    with pytest.raises(LifecycleError):
        with _in(tenant_a) as connection:
            _assign(connection, tenant_a, "u1", "loc_a")


def test_tenant_isolation_on_lifecycle_events(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    query = text("SELECT 1 FROM physical_unit_lifecycle_events WHERE tenant_id = :id")
    with _in(tenant_a) as connection:
        _assign(connection, tenant_a, "u1", "loc_a")
        seen_by_a = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()
    with _in(tenant_b) as connection:
        seen_by_b = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()
    assert seen_by_a and seen_by_b == []


# --- API ------------------------------------------------


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(tenant_id=str(tenant['tenant_id']), roles=roles)}"
    }


def _call(method, path, headers, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def test_api_creation_records_the_first_lifecycle_event(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["technicien"])
    created = _call(
        "POST",
        "/physical-units",
        headers,
        json={"product_model_id": str(tenant_a["model"]), "serial_number": "SN-API-1"},
    )
    history = _call("GET", f"/physical-units/{created.json()['id']}/lifecycle", headers)

    assert created.json()["lifecycle_state"] == "in_stock"
    assert [(e["from_state"], e["to_state"]) for e in history.json()] == [(None, "in_stock")]


def test_api_refuses_to_mount_a_unit_already_mounted_elsewhere(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["technicien"])
    body = {"physical_unit_id": str(tenant_a["u1"])}

    first = _call(
        "POST", f"/functional-locations/{tenant_a['loc_a']}/assignment", headers, json=body
    )
    second = _call(
        "POST", f"/functional-locations/{tenant_a['loc_b']}/assignment", headers, json=body
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_only_managers_change_lifecycle_by_hand(two_tenants) -> None:
    tenant_a, _ = two_tenants
    url = f"/physical-units/{tenant_a['u1']}/lifecycle"
    body = {"to_state": "decommissioned", "note": "Compresseur hors d'usage"}

    as_technicien = _call("POST", url, _headers(tenant_a, ["technicien"]), json=body)
    as_manager = _call("POST", url, _headers(tenant_a, ["responsable_exploitation"]), json=body)

    assert as_technicien.status_code == 403
    assert as_manager.status_code == 200
    assert as_manager.json()[-1]["to_state"] == "decommissioned"
