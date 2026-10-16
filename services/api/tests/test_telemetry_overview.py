"""Vue d'ensemble télémétrie pour tout le portefeuille (page Telemetry,
directive UI/dashboard, section 36 point 9) : la dernière valeur de chaque
point validé du tenant, en une poignée de requêtes plutôt qu'une par point."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.points import create_point, decide_point, get_point
from app.telemetry import record_measurement
from app.telemetry_overview import portfolio_telemetry
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

T0 = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
client = TestClient(app)


def _tenant(name: str) -> dict:
    ids = {"tenant_id": uuid.uuid4(), "site": uuid.uuid4(), "ahu": uuid.uuid4()}
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": ids["tenant_id"], "name": name, "slug": f"{name.lower()}-{ids['tenant_id']}"},
        )
        set_tenant_context(connection, ids["tenant_id"])
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site')"),
            {"id": ids["site"], "tenant_id": ids["tenant_id"]},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'cta-01', 'CTA 01')"
            ),
            {"id": ids["ahu"], "tenant_id": ids["tenant_id"], "site_id": ids["site"]},
        )
        ids["point"] = create_point(
            connection,
            tenant_id=ids["tenant_id"],
            code="CTA01-TEMP",
            name="Température de soufflage",
            value_type="number",
            point_class="supply_air_temperature_sensor",
            unit="Cel",
            functional_location_id=ids["ahu"],
            expected_interval_seconds=300,
            created_by="test",
        )
        decide_point(connection, point_id=ids["point"], decision="validated")
    return ids


@pytest.fixture
def two_tenants():
    tenant_a, tenant_b = _tenant("ClientTelemetryA"), _tenant("ClientTelemetryB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        purge_tenant(tenant["tenant_id"])


def _measure(tenant, value, at):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant["point"]),
            value=value,
            measured_at=at,
            origin="measured",
            source="test",
            received_at=at,
        )


def _overview(tenant, at):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return portfolio_telemetry(connection, at=at)


def test_reports_latest_value_and_freshness(two_tenants) -> None:
    tenant_a, _ = two_tenants
    _measure(tenant_a, 18.0, T0 - timedelta(minutes=10))
    _measure(tenant_a, 19.5, T0 - timedelta(minutes=2))
    [entry] = _overview(tenant_a, T0)
    assert entry["point_id"] == tenant_a["point"]
    assert entry["functional_location_id"] == tenant_a["ahu"]
    assert entry["value"] == 19.5
    assert entry["measured_at"] == T0 - timedelta(minutes=2)
    assert entry["stale"] is False


def test_reports_none_without_any_measurement(two_tenants) -> None:
    tenant_a, _ = two_tenants
    [entry] = _overview(tenant_a, T0)
    assert entry["value"] is None
    assert entry["measured_at"] is None
    assert entry["stale"] is None


def test_flags_data_older_than_the_expected_interval_as_stale(two_tenants) -> None:
    tenant_a, _ = two_tenants
    # Intervalle attendu de 300 s (5 min) ; seuil de péremption à 3 intervalles.
    _measure(tenant_a, 18.0, T0 - timedelta(minutes=30))
    [entry] = _overview(tenant_a, T0)
    assert entry["stale"] is True


def test_excludes_a_point_not_yet_validated(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        create_point(
            connection,
            tenant_id=tenant_a["tenant_id"],
            code="CTA01-TDEP",
            name="Température de départ",
            value_type="number",
            point_class="supply_water_temperature_sensor",
            unit="Cel",
            functional_location_id=tenant_a["ahu"],
            created_by="test",
        )
    entries = _overview(tenant_a, T0)
    assert [e["code"] for e in entries] == ["CTA01-TEMP"]


def test_tenant_isolation(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    _measure(tenant_a, 18.0, T0 - timedelta(minutes=1))
    entries = _overview(tenant_b, T0)
    assert [e["point_id"] for e in entries] == [tenant_b["point"]]
    assert entries[0]["value"] is None


def test_route_through_the_api(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    _measure(tenant_a, 18.0, datetime.now(UTC))
    headers = {"Authorization": f"Bearer {make_token(tenant_id=str(tenant_a['tenant_id']))}"}
    other = {"Authorization": f"Bearer {make_token(tenant_id=str(tenant_b['tenant_id']))}"}
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.get("/telemetry/portfolio-latest", headers=headers)
        other_response = client.get("/telemetry/portfolio-latest", headers=other)
    assert response.status_code == 200, response.text
    body = {row["point_id"]: row for row in response.json()}
    assert body[str(tenant_a["point"])]["value"] == 18.0
    assert str(tenant_a["point"]) not in {row["point_id"] for row in other_response.json()}
