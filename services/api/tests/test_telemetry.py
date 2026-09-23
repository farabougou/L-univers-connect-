import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.db import engine
from app.telemetry import record_measurement
from app.tenancy import set_tenant_context


def _create_tenant(connection, *, name: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    connection.execute(
        text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
        {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
    )
    return tenant_id


@pytest.fixture
def two_tenants():
    with engine.begin() as connection:
        tenant_a = _create_tenant(connection, name="ClientTelemetryA")
    with engine.begin() as connection:
        tenant_b = _create_tenant(connection, name="ClientTelemetryB")

    yield tenant_a, tenant_b

    for tenant_id in (tenant_a, tenant_b):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_id)
            connection.execute(
                text("DELETE FROM measurements WHERE tenant_id = :id"), {"id": tenant_id}
            )
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def test_record_measurement_stores_value_and_unit_together(two_tenants) -> None:
    tenant_a, _tenant_b = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        measurement_id = record_measurement(
            connection,
            tenant_id=tenant_a,
            metric="temperature_depart",
            value=45.5,
            unit="°C",
            measured_at=datetime(2026, 9, 23, 8, 0, tzinfo=UTC),
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        row = connection.execute(
            text("SELECT metric, value, unit, source FROM measurements WHERE id = :id"),
            {"id": measurement_id},
        ).one()

    assert row.metric == "temperature_depart"
    assert row.value == 45.5
    assert row.unit == "°C"
    # Par défaut : aucun connecteur réel n'existe encore (voir ADR 004).
    assert row.source == "simulator"


def test_tenant_isolation_on_measurements(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        record_measurement(
            connection,
            tenant_id=tenant_a,
            metric="temperature_depart",
            value=45.5,
            unit="°C",
            measured_at=datetime.now(UTC),
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b)
        rows = connection.execute(text("SELECT id FROM measurements")).fetchall()

    assert rows == []
