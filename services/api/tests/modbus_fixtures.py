"""Tenant + point de compteur d'énergie, réutilisé par les tests Modbus."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from app.config_versions import activate_version, create_version
from app.connectors.device_mapping import MODBUS_DEVICE_MAPPING
from app.db import engine
from app.points import create_point, decide_point
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_config_versions_for_tenant


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
    return {"tenant_id": tenant_id, "location_id": location_id, "point_id": point_id}


def create_tenant_with_energy_and_power_points(name: str) -> dict:
    """Même site qu'un compteur réel exposant plusieurs registres à la fois."""
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
        energy_point_id = create_point(
            connection,
            tenant_id=tenant_id,
            code=f"CPT-{tenant_id.hex[:8]}-E",
            name="Énergie active totale",
            value_type="number",
            point_class="energy_meter_reading",
            unit="kW.h",
            functional_location_id=location_id,
            min_value=0,
            max_value=1_000_000,
            created_by="test",
        )
        decide_point(connection, point_id=energy_point_id, decision="validated")
        power_point_id = create_point(
            connection,
            tenant_id=tenant_id,
            code=f"CPT-{tenant_id.hex[:8]}-P",
            name="Puissance active",
            value_type="number",
            point_class="electric_power_sensor",
            unit="W",
            functional_location_id=location_id,
            min_value=0,
            max_value=100_000,
            created_by="test",
        )
        decide_point(connection, point_id=power_point_id, decision="validated")
    return {
        "tenant_id": tenant_id,
        "location_id": location_id,
        "energy_point_id": energy_point_id,
        "power_point_id": power_point_id,
    }


def activate_device_mapping(
    *, tenant_id: uuid.UUID, equipment_id: uuid.UUID, host: str, points: list[dict], port: int = 502
) -> uuid.UUID:
    """Crée et active une configuration modbus_device_mapping pour un test,
    sans passer par l'API (voir app/connectors/device_mapping.py)."""
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        version_id = create_version(
            connection,
            tenant_id=tenant_id,
            config_type=MODBUS_DEVICE_MAPPING,
            subject_key=str(equipment_id),
            content={"device_type": "sdm120", "host": host, "port": port, "points": points},
            author="test",
            reason="test",
        )
        activate_version(
            connection,
            version_id=version_id,
            activated_by="test",
            activated_at=datetime.now(UTC),
        )
    return version_id


def cleanup_tenant(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("DELETE FROM measurements WHERE tenant_id = :id"), {"id": tenant_id}
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
