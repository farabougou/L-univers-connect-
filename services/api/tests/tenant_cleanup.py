"""Suppression complète des données d'un tenant de test, dans l'ordre imposé
par les clés étrangères. Les tables protégées contre la suppression (audit,
relations, configurations, clôtures) passent par le compte administrateur
(voir db_helpers) ; tout le reste passe par la RLS, comme l'application."""

from sqlalchemy import text

from app.db import engine
from app.tenancy import set_tenant_context
from tests.db_helpers import (
    purge_audit_log_for_tenant,
    purge_config_versions_for_tenant,
    purge_intervention_closures_for_tenant,
    purge_relations_for_tenant,
)

_TABLES_IN_ORDER = (
    "finding_status_history",
    "findings",
    "alarm_status_history",
    "alarms",
    "intervention_photos",
    "interventions",
    "work_order_status_history",
    "work_orders",
    "desired_states",
    "events",
    "commands",
    "measurements",
    "external_identifiers",
    "asset_tags",
    "node_properties",
    "points",
    "functional_location_space_history",
    "functional_location_assignments",
    "physical_unit_lifecycle_events",
    "physical_units",
    "product_models",
    "functional_locations",
    "spaces",
    "sites",
)


def purge_tenant(tenant_id) -> None:
    purge_relations_for_tenant(tenant_id)
    purge_intervention_closures_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in _TABLES_IN_ORDER:
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    purge_config_versions_for_tenant(tenant_id)
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
