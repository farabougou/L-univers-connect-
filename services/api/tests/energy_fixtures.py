"""Données de test communes au moteur énergétique (M5) : un site, un
équipement, un point de mesure d'énergie cumulative (`energy_meter_reading`,
comme le compteur SDM120)."""

import uuid
from contextlib import contextmanager

from sqlalchemy import text

from app.db import engine
from app.points import create_point, decide_point
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_config_versions_for_tenant


def create_tenant_with_energy_meter(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    location_id = uuid.uuid4()
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
                "VALUES (:id, :tenant_id, :site_id, 'pac-01', 'PAC 01')"
            ),
            {"id": location_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        meter = create_point(
            connection,
            tenant_id=tenant_id,
            code="PAC01-ENERGIE",
            name="Énergie active totale",
            value_type="number",
            point_class="energy_meter_reading",
            unit="kW.h",
            functional_location_id=location_id,
            expected_interval_seconds=3600,
            min_value=0,
            created_by="test",
        )
        decide_point(connection, point_id=meter, decision="validated")
    return {
        "tenant_id": tenant_id,
        "site": site_id,
        "location": location_id,
        "meter": meter,
    }


def cleanup_tenant(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "energy_normalized_results",
            "weather_observations",
            "events",
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
