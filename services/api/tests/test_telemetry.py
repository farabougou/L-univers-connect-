import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db import engine
from app.graph import add_external_identifier, list_node_relations
from app.points import PointConflict, create_point, decide_point, get_point, identify_point
from app.telemetry import (
    MeasurementConflict,
    MeasurementRejected,
    ingest_measurements,
    list_measurements,
    record_measurement,
)
from app.tenancy import set_tenant_context
from tests.error_helpers import raises_code

T0 = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)


def _create_tenant(name: str) -> dict:
    """Un site, une CTA, et une sonde de départ d'eau validée (0 à 100 °C)."""
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
            min_value=0,
            max_value=100,
            created_by="test",
        )
        decide_point(connection, point_id=sensor, decision="validated")
    return {"tenant_id": tenant_id, "site": site_id, "ahu": ahu_id, "sensor": sensor}


def _cleanup(tenant: dict) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        for table in (
            "finding_status_history",
            "findings",
            "alarm_status_history",
            "alarms",
            "work_order_status_history",
            "work_orders",
            "desired_states",
            "measurements",
            "external_identifiers",
            "points",
            "functional_locations",
            "sites",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant["tenant_id"]}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant["tenant_id"]})


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientTelemetryA")
    tenant_b = _create_tenant("ClientTelemetryB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        _cleanup(tenant)


@contextmanager
def _in_tenant(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        yield connection


def _record(connection, tenant, *, value, measured_at=T0, point=None):
    return record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=point or get_point(connection, tenant["sensor"]),
        value=value,
        measured_at=measured_at,
        origin="simulated",
        source="simulator",
        received_at=T0,
    )


# --- Isolation ------------------------------------------------


@pytest.mark.parametrize("table", ["points", "measurements", "external_identifiers"])
def test_tenant_isolation_on_telemetry_tables(two_tenants, table) -> None:
    tenant_a, tenant_b = two_tenants
    query = text(f"SELECT 1 FROM {table} WHERE tenant_id = :id")
    with _in_tenant(tenant_a) as connection:
        _record(connection, tenant_a, value=45.5)
        add_external_identifier(
            connection,
            tenant_id=tenant_a["tenant_id"],
            node_id=tenant_a["sensor"],
            scheme="bacnet_object",
            external_id="analog-input:12",
            created_by="test",
        )
        seen_by_a = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()
    with _in_tenant(tenant_b) as connection:
        seen_by_b = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()

    assert seen_by_a
    assert seen_by_b == []


def test_point_cannot_be_attached_to_another_tenant_location(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with pytest.raises(IntegrityError):
        with _in_tenant(tenant_a) as connection:
            connection.execute(
                text(
                    "INSERT INTO points (id, tenant_id, functional_location_id, code, name, "
                    "value_type, created_by) VALUES (:id, :tenant_id, :location, 'piege', "
                    "'piege', 'number', 'test')"
                ),
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_a["tenant_id"],
                    "location": tenant_b["ahu"],
                },
            )


# --- Règle non négociable 1 inscrite dans la base ------------------------------------------------


def test_a_point_can_never_be_declared_writable(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(IntegrityError, match="ck_points_read_only_c0"):
        with _in_tenant(tenant_a) as connection:
            connection.execute(
                text(
                    "INSERT INTO points (id, tenant_id, code, name, value_type, is_writable, "
                    "created_by) VALUES (:id, :tenant_id, 'cmd', 'cmd', 'boolean', true, 'test')"
                ),
                {"id": uuid.uuid4(), "tenant_id": tenant_a["tenant_id"]},
            )


def test_a_proposed_point_cannot_be_made_writable_either(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        command = create_point(
            connection,
            tenant_id=tenant_a["tenant_id"],
            code="CTA01-CMD",
            name="Marche/arrêt",
            value_type="boolean",
            point_class="on_off_command",
            functional_location_id=tenant_a["ahu"],
            created_by="test",
        )
    with pytest.raises(IntegrityError, match="ck_points_read_only_c0"):
        with _in_tenant(tenant_a) as connection:
            connection.execute(
                text("UPDATE points SET is_writable = true WHERE id = :id"), {"id": command}
            )


# --- Mise en service des points ------------------------------------------------


def test_points_are_graph_nodes_linked_to_their_equipment(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        from_ahu = list_node_relations(connection, tenant_a["ahu"])
        from_sensor = list_node_relations(connection, tenant_a["sensor"])

    assert ("hasPoint", tenant_a["sensor"]) in {(e["label"], e["object_id"]) for e in from_ahu}
    assert [(e["label"], e["subject_id"]) for e in from_sensor] == [("isPointOf", tenant_a["ahu"])]


def test_a_validated_point_is_frozen(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with raises_code(PointConflict, "POINT_NOT_EDITABLE"):
        with _in_tenant(tenant_a) as connection:
            identify_point(connection, point_id=tenant_a["sensor"], changes={"unit": "K"})
    with pytest.raises(DBAPIError, match="ne peut plus être modifiée"):
        with _in_tenant(tenant_a) as connection:
            connection.execute(
                text("UPDATE points SET name = 'autre' WHERE id = :id"), {"id": tenant_a["sensor"]}
            )


def test_a_discovered_point_is_identified_then_validated(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        discovered = create_point(
            connection,
            tenant_id=tenant_a["tenant_id"],
            code="AI-12",
            name="AI-12 (découvert)",
            value_type="number",
            created_by="decouverte",
        )
        assert get_point(connection, discovered)["mapping_status"] == "proposed"
        identify_point(
            connection,
            point_id=discovered,
            changes={
                "point_class": "return_water_temperature_sensor",
                "unit": "Cel",
                "functional_location_id": tenant_a["ahu"],
            },
        )
        decide_point(connection, point_id=discovered, decision="validated")
        point = get_point(connection, discovered)

    assert point["mapping_status"] == "validated"
    assert point["kind"] == "sensor"


# --- Réception des mesures ------------------------------------------------


def test_resending_the_same_measurement_is_harmless(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        first = _record(connection, tenant_a, value=45.5)
        second = _record(connection, tenant_a, value=45.5)
        rows = list_measurements(connection, point_id=tenant_a["sensor"])

    assert (first, second) == ("inserted", "duplicate")
    assert len(rows) == 1


def test_a_different_value_at_the_same_instant_is_a_conflict_never_an_overwrite(
    two_tenants,
) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        _record(connection, tenant_a, value=45.5)
    with pytest.raises(MeasurementConflict):
        with _in_tenant(tenant_a) as connection:
            _record(connection, tenant_a, value=46.0)
    with _in_tenant(tenant_a) as connection:
        rows = list_measurements(connection, point_id=tenant_a["sensor"])
    assert [row["value"] for row in rows] == [45.5]


def test_out_of_range_value_is_kept_and_flagged(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        _record(connection, tenant_a, value=150.0)
        row = list_measurements(connection, point_id=tenant_a["sensor"])[0]
    assert row["value"] == 150.0
    assert row["quality_flags"] == ["out_of_range"]
    assert row["origin"] == "simulated"


def test_a_rejected_point_refuses_measurements(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        ghost = create_point(
            connection,
            tenant_id=tenant_a["tenant_id"],
            code="AI-99",
            name="Point fantôme",
            value_type="number",
            created_by="decouverte",
        )
        decide_point(connection, point_id=ghost, decision="rejected")
    with raises_code(MeasurementRejected, "POINT_REJECTED"):
        with _in_tenant(tenant_a) as connection:
            _record(connection, tenant_a, value=1.0, point=get_point(connection, ghost))


def test_batch_ingestion_reports_each_item(two_tenants) -> None:
    """Envoi différé après coupure : les bons relevés passent, les autres sont
    expliqués un par un, rien n'est perdu ni dupliqué."""
    tenant_a, tenant_b = two_tenants
    sensor = tenant_a["sensor"]
    items = [
        {"point_id": sensor, "value": 45.0, "measured_at": T0, "origin": "measured"},
        {
            "point_id": sensor,
            "value": 45.5,
            "measured_at": T0 + timedelta(minutes=1),
            "origin": "measured",
        },
        {"point_id": sensor, "value": 45.0, "measured_at": T0, "origin": "measured"},
        {"point_id": sensor, "value": 99.0, "measured_at": T0, "origin": "measured"},
        {"point_id": tenant_b["sensor"], "value": 1.0, "measured_at": T0, "origin": "measured"},
    ]
    with _in_tenant(tenant_a) as connection:
        summary = ingest_measurements(
            connection,
            tenant_id=tenant_a["tenant_id"],
            items=items,
            source="edge-test",
            received_at=T0 + timedelta(minutes=5),
        )

    assert {k: summary[k] for k in ("inserted", "duplicates", "conflicts", "rejected")} == {
        "inserted": 2,
        "duplicates": 1,
        "conflicts": 1,
        "rejected": 1,
    }
    assert [(e["index"], e["code"]) for e in summary["errors"]][1] == (4, "POINT_NOT_FOUND")
