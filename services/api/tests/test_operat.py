"""Déclaration annuelle OPERAT / Éco Énergie Tertiaire (app.regulatory.operat) :
workflow brouillon → prêt → transmis, gelé une fois transmis."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.db import engine
from app.regulatory.operat import (
    DEFAULT_API_ADAPTER,
    OperatDeclarationConflict,
    OperatDeclarationNotFound,
    OperatError,
    create_draft_declaration,
    export_operat_summary,
    get_declaration,
    mark_ready,
    record_manual_submission,
    update_declaration,
)
from app.tenancy import set_tenant_context
from tests.tenant_cleanup import purge_tenant

T0 = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)


def _create_tenant(name: str) -> dict:
    ids = {k: uuid.uuid4() for k in ("tenant_id", "site")}
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": ids["tenant_id"], "name": name, "slug": f"{name.lower()}-{ids['tenant_id']}"},
        )
        set_tenant_context(connection, ids["tenant_id"])
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:site, :tenant_id, 'Site')"),
            ids,
        )
    return ids


@pytest.fixture
def tenant():
    ids = _create_tenant("ClientOperatA")
    yield ids
    purge_tenant(ids["tenant_id"])


def _ready_declaration(connection, tenant, **overrides) -> dict:
    declaration = create_draft_declaration(
        connection, tenant_id=tenant["tenant_id"], site_id=tenant["site"],
        reference_year=2026, created_by="Mohamed",
    )
    update_declaration(
        connection,
        declaration_id=declaration["id"],
        floor_area_m2=overrides.get("floor_area_m2", 500.0),
        activity_category=overrides.get("activity_category", "bureaux"),
        electricity_kwh=overrides.get("electricity_kwh", 12000.0),
        updated_by="Mohamed",
        updated_at=T0,
    )
    return mark_ready(connection, declaration_id=declaration["id"])


def test_creates_a_draft_declaration(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        declaration = create_draft_declaration(
            connection, tenant_id=tenant["tenant_id"], site_id=tenant["site"],
            reference_year=2026, created_by="Mohamed",
        )
        assert declaration["status"] == "draft"
        assert declaration["reference_year"] == 2026


def test_a_second_declaration_for_the_same_site_and_year_is_refused(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        create_draft_declaration(
            connection, tenant_id=tenant["tenant_id"], site_id=tenant["site"],
            reference_year=2026, created_by="Mohamed",
        )
        with pytest.raises(OperatDeclarationConflict):
            create_draft_declaration(
                connection, tenant_id=tenant["tenant_id"], site_id=tenant["site"],
                reference_year=2026, created_by="Mohamed",
            )


def test_declaration_for_an_unknown_site_is_refused(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(OperatDeclarationNotFound):
            create_draft_declaration(
                connection, tenant_id=tenant["tenant_id"], site_id=uuid.uuid4(),
                reference_year=2026, created_by="Mohamed",
            )


def test_mark_ready_requires_surface_activity_and_at_least_one_consumption(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        declaration = create_draft_declaration(
            connection, tenant_id=tenant["tenant_id"], site_id=tenant["site"],
            reference_year=2026, created_by="Mohamed",
        )
        with pytest.raises(OperatError) as excinfo:
            mark_ready(connection, declaration_id=declaration["id"])
        assert excinfo.value.code == "OPERAT_DECLARATION_INCOMPLETE"
        assert set(excinfo.value.params["fields"]) == {
            "activity_category", "consumption", "floor_area_m2",
        }


def test_mark_ready_succeeds_once_complete(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        ready = _ready_declaration(connection, tenant)
        assert ready["status"] == "ready"


def test_mark_ready_twice_is_refused(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        ready = _ready_declaration(connection, tenant)
        with pytest.raises(OperatError) as excinfo:
            mark_ready(connection, declaration_id=ready["id"])
        assert excinfo.value.code == "OPERAT_DECLARATION_NOT_DRAFT"


def test_a_draft_cannot_be_recorded_as_submitted(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        declaration = create_draft_declaration(
            connection, tenant_id=tenant["tenant_id"], site_id=tenant["site"],
            reference_year=2026, created_by="Mohamed",
        )
        with pytest.raises(OperatError) as excinfo:
            record_manual_submission(
                connection, declaration_id=declaration["id"], submitted_by="Mohamed",
                submitted_at=T0,
            )
        assert excinfo.value.code == "OPERAT_DECLARATION_NOT_READY"


def test_records_a_manual_submission_and_freezes_the_declaration(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        ready = _ready_declaration(connection, tenant)
        submitted = record_manual_submission(
            connection, declaration_id=ready["id"], submitted_by="Mohamed", submitted_at=T0,
            submission_reference="OPERAT-2026-000123",
        )
        assert submitted["status"] == "submitted"
        assert submitted["submission_reference"] == "OPERAT-2026-000123"

        # Une déclaration transmise est gelée : même une modification
        # anodine est refusée par le déclencheur en base.
        with pytest.raises(Exception):  # noqa: B017 - erreur Postgres brute, pas un DomainError
            connection.execute(
                text("UPDATE operat_declarations SET notes = 'x' WHERE id = :id"),
                {"id": submitted["id"]},
            )


def test_a_negative_quantity_is_rejected(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        declaration = create_draft_declaration(
            connection, tenant_id=tenant["tenant_id"], site_id=tenant["site"],
            reference_year=2026, created_by="Mohamed",
        )
        with pytest.raises(OperatError) as excinfo:
            update_declaration(
                connection, declaration_id=declaration["id"], electricity_kwh=-1.0,
                updated_by="Mohamed", updated_at=T0,
            )
        assert excinfo.value.code == "OPERAT_QUANTITY_NEGATIVE"


def test_export_summary_matches_the_declaration(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        ready = _ready_declaration(connection, tenant)
        summary = export_operat_summary(ready)
        assert summary["annee_reference"] == 2026
        assert summary["surface_m2"] == 500.0
        assert summary["electricite_kwh"] == 12000.0


def test_the_default_api_adapter_fails_explicitly_rather_than_pretend_to_submit() -> None:
    with pytest.raises(OperatError) as excinfo:
        DEFAULT_API_ADAPTER.submit({})
    assert excinfo.value.code == "OPERAT_API_NOT_CONFIGURED"


def test_isolation_between_tenants() -> None:
    tenant_a = _create_tenant("ClientOperatIsoA")
    tenant_b = _create_tenant("ClientOperatIsoB")
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            declaration = create_draft_declaration(
                connection, tenant_id=tenant_a["tenant_id"], site_id=tenant_a["site"],
                reference_year=2026, created_by="Mohamed",
            )
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_b["tenant_id"])
            assert get_declaration(connection, declaration["id"]) is None
    finally:
        purge_tenant(tenant_a["tenant_id"])
        purge_tenant(tenant_b["tenant_id"])
