"""Politiques de supervision (app/monitoring.py) : État → Événement →
Politique → Alerte si nécessaire (directive de Mohamed du 24/09/2026).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.commands import create_command
from app.db import engine
from app.devices import provision_device
from app.equipment_status import compute_equipment_status
from app.events import list_events_for_subject
from app.monitoring import evaluate_command_timeout, evaluate_communication_status
from app.points import create_point, decide_point
from app.telemetry import ingest_measurements
from app.tenancy import set_tenant_context
from tests.modbus_fixtures import (
    activate_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_point,
)

T0 = datetime(2026, 9, 24, 14, 0, tzinfo=UTC)


def _tenant_with_status_point():
    created = create_tenant_with_energy_point("ClientSupervision")
    with engine.begin() as connection:
        set_tenant_context(connection, created["tenant_id"])
        status_point_id = create_point(
            connection,
            tenant_id=created["tenant_id"],
            code="PAC01-MARCHE",
            name="Marche",
            value_type="boolean",
            point_class="run_status",
            functional_location_id=created["location_id"],
            expected_interval_seconds=60,
            created_by="test",
        )
        decide_point(connection, point_id=status_point_id, decision="validated")
    return {**created, "status_point_id": status_point_id}


def test_equipement_hors_ligne_leve_une_alerte_puis_se_retablit():
    tenant = _tenant_with_status_point()
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant["tenant_id"])
            ingest_measurements(
                connection,
                tenant_id=tenant["tenant_id"],
                items=[
                    {
                        "point_id": tenant["status_point_id"],
                        "value": 1.0,
                        "measured_at": T0,
                        "origin": "measured",
                    }
                ],
                source="test",
                received_at=T0,
            )

            later = T0 + timedelta(minutes=10)
            status = compute_equipment_status(connection, tenant["location_id"], later)
            assert status["communication_status"] == "offline"
            evaluate_communication_status(
                connection,
                tenant_id=tenant["tenant_id"],
                functional_location_id=tenant["location_id"],
                location_code="pac-01",
                status=status,
                at=later,
            )

            findings = (
                connection.execute(
                    text(
                        "SELECT handling_status, condition_state FROM findings "
                        "WHERE subject_node_id = :id"
                    ),
                    {"id": tenant["location_id"]},
                )
                .mappings()
                .all()
            )
            assert len(findings) == 1
            assert findings[0]["condition_state"] == "active"

            events = list_events_for_subject(
                connection, subject_type="functional_location", subject_id=tenant["location_id"]
            )
            assert [e["event_type"] for e in events] == ["DEVICE_WENT_OFFLINE"]

            # Un second appel avec le même statut ne duplique rien (déduplication).
            evaluate_communication_status(
                connection,
                tenant_id=tenant["tenant_id"],
                functional_location_id=tenant["location_id"],
                location_code="pac-01",
                status=status,
                at=later,
            )
            findings_again = connection.execute(
                text("SELECT id FROM findings WHERE subject_node_id = :id"),
                {"id": tenant["location_id"]},
            ).fetchall()
            assert len(findings_again) == 1

            # Retour à la normale : nouvelle mesure fraîche.
            recovery = later + timedelta(minutes=1)
            ingest_measurements(
                connection,
                tenant_id=tenant["tenant_id"],
                items=[
                    {
                        "point_id": tenant["status_point_id"],
                        "value": 1.0,
                        "measured_at": recovery,
                        "origin": "measured",
                    }
                ],
                source="test",
                received_at=recovery,
            )
            online_status = compute_equipment_status(connection, tenant["location_id"], recovery)
            assert online_status["communication_status"] == "online"
            evaluate_communication_status(
                connection,
                tenant_id=tenant["tenant_id"],
                functional_location_id=tenant["location_id"],
                location_code="pac-01",
                status=online_status,
                at=recovery,
            )

            condition = connection.execute(
                text("SELECT condition_state FROM findings WHERE subject_node_id = :id"),
                {"id": tenant["location_id"]},
            ).scalar()
            assert condition == "cleared"

            event_types = {
                e["event_type"]
                for e in list_events_for_subject(
                    connection,
                    subject_type="functional_location",
                    subject_id=tenant["location_id"],
                )
            }
            assert event_types == {"DEVICE_WENT_OFFLINE", "DEVICE_CAME_ONLINE"}
    finally:
        cleanup_tenant(tenant)


def test_statut_inconnu_ne_declenche_rien():
    tenant = create_tenant_with_energy_point("ClientSupervisionInconnu")
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant["tenant_id"])
            status = compute_equipment_status(connection, tenant["location_id"], T0)
            assert status["communication_status"] == "unknown"
            evaluate_communication_status(
                connection,
                tenant_id=tenant["tenant_id"],
                functional_location_id=tenant["location_id"],
                location_code="pac-01",
                status=status,
                at=T0,
            )
            findings = connection.execute(
                text("SELECT id FROM findings WHERE subject_node_id = :id"),
                {"id": tenant["location_id"]},
            ).fetchall()
            assert findings == []
    finally:
        cleanup_tenant(tenant)


def _commandable_tenant():
    created = create_tenant_with_energy_point("ClientSupervisionCommande")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=5921,
        device_type="simulated_relay",
        points=[{"point_id": str(created["point_id"]), "register_name": "relay_state"}],
    )
    return created


def test_commande_non_confirmee_leve_une_alerte():
    tenant = _commandable_tenant()
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant["tenant_id"])
            device_id, _ = provision_device(
                connection,
                tenant_id=tenant["tenant_id"],
                device_id="relais-supervision",
                created_by="test",
            )
            command_id = create_command(
                connection,
                tenant_id=tenant["tenant_id"],
                point_id=tenant["point_id"],
                requested_value=1.0,
                requested_by="mohamed",
                at=T0,
            )
            connection.execute(
                text(
                    "UPDATE commands SET status = 'sent', sent_at = :at, "
                    "edge_device_id = :device_id WHERE id = :id"
                ),
                {"at": T0, "device_id": device_id, "id": command_id},
            )

            late = T0 + timedelta(minutes=10)
            command = {"id": command_id}
            updated = evaluate_command_timeout(
                connection, tenant_id=tenant["tenant_id"], command=command, at=late
            )
            assert updated["status"] == "timed_out"

            finding = (
                connection.execute(
                    text("SELECT reason_code, point_id FROM findings WHERE point_id = :point_id"),
                    {"point_id": tenant["point_id"]},
                )
                .mappings()
                .first()
            )
            assert finding["reason_code"] == "COMMAND_UNCONFIRMED"

            event_types = {
                e["event_type"]
                for e in list_events_for_subject(
                    connection, subject_type="command", subject_id=command_id
                )
            }
            assert "COMMAND_TIMED_OUT" in event_types
    finally:
        cleanup_tenant(tenant)
