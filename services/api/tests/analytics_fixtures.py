"""Données de test communes à F4 : un site, une CTA, une sonde de départ d'eau
validée (0 à 100 °C, un relevé attendu par minute) et un état de marche."""

import uuid
from contextlib import contextmanager

from sqlalchemy import text

from app.db import engine
from app.points import create_point, decide_point
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_config_versions_for_tenant


def create_tenant_with_points(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    ahu_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site')"),
            {"id": site_id, "tenant_id": tenant_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'cta-01', 'CTA 01')"
            ),
            {"id": ahu_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        sensor = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA01-TDEP",
            name="Température départ eau",
            value_type="number",
            point_class="supply_water_temperature_sensor",
            unit="Cel",
            functional_location_id=ahu_id,
            expected_interval_seconds=60,
            min_value=0,
            max_value=100,
            created_by="test",
        )
        run_status = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA01-MARCHE",
            name="État de marche",
            value_type="boolean",
            point_class="run_status",
            functional_location_id=ahu_id,
            created_by="test",
        )
        for point_id in (sensor, run_status):
            decide_point(connection, point_id=point_id, decision="validated")
    return {
        "tenant_id": tenant_id,
        "site": site_id,
        "ahu": ahu_id,
        "sensor": sensor,
        "run_status": run_status,
    }


def cleanup_tenant(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "finding_status_history",
            "findings",
            "alarm_status_history",
            "alarms",
            "work_order_status_history",
            "work_orders",
            "desired_states",
            "measurements",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    purge_config_versions_for_tenant(tenant_id)
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("points", "functional_locations", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


@contextmanager
def in_tenant(tenant: dict):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        yield connection
