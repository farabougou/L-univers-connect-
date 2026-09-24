"""Tenant + point de compteur d'énergie, réutilisé par les tests Modbus."""

import uuid

from sqlalchemy import text

from app.db import engine
from app.points import create_point, decide_point
from app.tenancy import set_tenant_context


def create_tenant_with_energy_point(name: str) -> dict:
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
                "VALUES (:id, :tenant_id, :site_id, 'cpt-01', 'Compteur test')"
            ),
            {"id": location_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        point_id = create_point(
            connection,
            tenant_id=tenant_id,
            code=f"CPT-{tenant_id.hex[:8]}",
            name="Énergie active totale",
            value_type="number",
            point_class="energy_meter_reading",
            unit="kW.h",
            functional_location_id=location_id,
            min_value=0,
            max_value=1_000_000,
            created_by="test",
        )
        decide_point(connection, point_id=point_id, decision="validated")
    return {"tenant_id": tenant_id, "point_id": point_id}


def cleanup_tenant(tenant: dict) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        for table in ("measurements", "points", "functional_locations", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant["tenant_id"]}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant["tenant_id"]})
