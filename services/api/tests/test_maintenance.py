import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.db import engine
from app.maintenance import (
    change_alarm_status,
    change_work_order_status,
    create_work_order,
    log_intervention,
    raise_alarm,
)
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant


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
        tenant_a = _create_tenant(connection, name="ClientMaintA")
    with engine.begin() as connection:
        tenant_b = _create_tenant(connection, name="ClientMaintB")

    yield tenant_a, tenant_b

    for tenant_id in (tenant_a, tenant_b):
        purge_audit_log_for_tenant(tenant_id)
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_id)
            for table in (
                "interventions",
                "alarm_status_history",
                "alarms",
                "work_order_status_history",
                "work_orders",
            ):
                connection.execute(
                    text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
                )
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def test_work_order_status_change_keeps_full_history(two_tenants) -> None:
    tenant_a, _tenant_b = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        work_order_id = create_work_order(
            connection,
            tenant_id=tenant_a,
            created_by="responsable-1",
            title="Vérifier la PAC",
            priority="high",
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        change_work_order_status(
            connection,
            tenant_id=tenant_a,
            work_order_id=work_order_id,
            status="in_progress",
            changed_by="technicien-1",
        )
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        change_work_order_status(
            connection,
            tenant_id=tenant_a,
            work_order_id=work_order_id,
            status="completed",
            changed_by="technicien-1",
            note="Filtre remplacé",
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        current_status = connection.execute(
            text("SELECT status FROM work_orders WHERE id = :id"), {"id": work_order_id}
        ).scalar()
        history = (
            connection.execute(
                text(
                    "SELECT status FROM work_order_status_history "
                    "WHERE work_order_id = :id ORDER BY changed_at"
                ),
                {"id": work_order_id},
            )
            .scalars()
            .all()
        )

    assert current_status == "completed"
    # Les trois transitions restent visibles, aucune n'a été écrasée.
    assert history == ["open", "in_progress", "completed"]


def test_change_work_order_status_rejects_unknown_status(two_tenants) -> None:
    tenant_a, _tenant_b = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        work_order_id = create_work_order(
            connection, tenant_id=tenant_a, created_by="responsable-1", title="Tâche"
        )

    with pytest.raises(ValueError):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a)
            change_work_order_status(
                connection,
                tenant_id=tenant_a,
                work_order_id=work_order_id,
                status="statut-invente",
                changed_by="technicien-1",
            )


def test_work_order_type_defaults_to_corrective(two_tenants) -> None:
    tenant_a, _tenant_b = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        work_order_id = create_work_order(
            connection, tenant_id=tenant_a, created_by="responsable-1", title="Fuite constatée"
        )
        work_order_type = connection.execute(
            text("SELECT work_order_type FROM work_orders WHERE id = :id"), {"id": work_order_id}
        ).scalar()

    assert work_order_type == "corrective"


def test_work_order_type_can_be_set_explicitly(two_tenants) -> None:
    tenant_a, _tenant_b = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        work_order_id = create_work_order(
            connection,
            tenant_id=tenant_a,
            created_by="responsable-1",
            title="Révision trimestrielle",
            work_order_type="preventive",
        )
        work_order_type = connection.execute(
            text("SELECT work_order_type FROM work_orders WHERE id = :id"), {"id": work_order_id}
        ).scalar()

    assert work_order_type == "preventive"


def test_alarm_lifecycle_keeps_full_history(two_tenants) -> None:
    tenant_a, _tenant_b = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        alarm_id = raise_alarm(
            connection,
            tenant_id=tenant_a,
            raised_by="technicien-1",
            severity="critical",
            message="Pression basse détectée",
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        change_alarm_status(
            connection,
            tenant_id=tenant_a,
            alarm_id=alarm_id,
            status="acknowledged",
            changed_by="responsable-1",
        )
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        change_alarm_status(
            connection,
            tenant_id=tenant_a,
            alarm_id=alarm_id,
            status="resolved",
            changed_by="technicien-1",
            note="Vanne resserrée",
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        current_status = connection.execute(
            text("SELECT status FROM alarms WHERE id = :id"), {"id": alarm_id}
        ).scalar()
        history = (
            connection.execute(
                text(
                    "SELECT status FROM alarm_status_history "
                    "WHERE alarm_id = :id ORDER BY changed_at"
                ),
                {"id": alarm_id},
            )
            .scalars()
            .all()
        )

    assert current_status == "resolved"
    assert history == ["open", "acknowledged", "resolved"]


def test_log_intervention_without_work_order(two_tenants) -> None:
    tenant_a, _tenant_b = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        intervention_id = log_intervention(
            connection,
            tenant_id=tenant_a,
            technician="technicien-1",
            started_at=datetime.now(UTC),
            summary="Contrôle visuel rapide",
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        row = connection.execute(
            text("SELECT work_order_id, technician FROM interventions WHERE id = :id"),
            {"id": intervention_id},
        ).one()

    assert row.work_order_id is None
    assert row.technician == "technicien-1"


def test_log_ronde_stores_checklist_and_type(two_tenants) -> None:
    tenant_a, _tenant_b = two_tenants
    checklist = {"pression_ok": True, "bruit_anormal": False, "filtre_propre": True}

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        intervention_id = log_intervention(
            connection,
            tenant_id=tenant_a,
            technician="technicien-1",
            started_at=datetime.now(UTC),
            intervention_type="ronde",
            checklist=checklist,
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        row = connection.execute(
            text("SELECT intervention_type, checklist FROM interventions WHERE id = :id"),
            {"id": intervention_id},
        ).one()

    assert row.intervention_type == "ronde"
    assert row.checklist == checklist


def test_log_intervention_defaults_to_intervention_type_with_empty_checklist(two_tenants) -> None:
    tenant_a, _tenant_b = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        intervention_id = log_intervention(
            connection,
            tenant_id=tenant_a,
            technician="technicien-1",
            started_at=datetime.now(UTC),
            summary="Fuite réparée",
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        row = connection.execute(
            text("SELECT intervention_type, checklist FROM interventions WHERE id = :id"),
            {"id": intervention_id},
        ).one()

    assert row.intervention_type == "intervention"
    assert row.checklist == {}


@pytest.mark.parametrize(
    "table",
    ["work_orders", "work_order_status_history", "interventions", "alarms", "alarm_status_history"],
)
def test_tenant_isolation_on_maintenance_tables(two_tenants, table) -> None:
    tenant_a, tenant_b = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        work_order_a = create_work_order(
            connection, tenant_id=tenant_a, created_by="responsable-a", title="Tâche A"
        )
        log_intervention(
            connection, tenant_id=tenant_a, technician="technicien-a", started_at=datetime.now(UTC)
        )
        raise_alarm(
            connection, tenant_id=tenant_a, raised_by="technicien-a", severity="info", message="A"
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b)
        create_work_order(
            connection, tenant_id=tenant_b, created_by="responsable-b", title="Tâche B"
        )
        log_intervention(
            connection, tenant_id=tenant_b, technician="technicien-b", started_at=datetime.now(UTC)
        )
        raise_alarm(
            connection, tenant_id=tenant_b, raised_by="technicien-b", severity="info", message="B"
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        rows = connection.execute(text(f"SELECT tenant_id FROM {table}")).fetchall()

    seen_tenant_ids = {row.tenant_id for row in rows}
    assert tenant_b not in seen_tenant_ids
    assert seen_tenant_ids.issubset({tenant_a})

    # Sans le contexte tenant_a, "work_order_a" sert juste à garder la
    # référence vivante pour la lisibilité du test ci-dessus.
    assert work_order_a is not None
