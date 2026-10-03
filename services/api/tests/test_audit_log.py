import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.audit import append_audit_entry, verify_chain_integrity
from app.db import engine
from app.tenancy import set_tenant_context
from tests.db_helpers import ADMIN_DATABASE_URL, purge_audit_log_for_tenant


@pytest.fixture
def tenant_id():
    tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": "Client Audit", "slug": f"client-audit-{tenant_id}"},
        )

    yield tenant_id

    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def test_appended_entries_form_a_valid_chain(tenant_id) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor="technicien-1",
            action="site.created",
            entity_type="site",
            entity_id="site-1",
            payload={"name": "Site A"},
        )
        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor="technicien-1",
            action="site.updated",
            entity_type="site",
            entity_id="site-1",
            payload={"name": "Site A bis"},
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        result = verify_chain_integrity(connection, tenant_id=tenant_id)

    assert result.valid is True
    assert result.broken_at_seq is None


def test_database_rejects_update_of_an_existing_entry(tenant_id) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor="technicien-1",
            action="site.created",
            payload={},
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(
                text("UPDATE audit_log SET action = 'falsifie' WHERE tenant_id = :id"),
                {"id": tenant_id},
            )


def test_tampering_directly_in_database_is_detected_by_verification(tenant_id) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor="technicien-1",
            action="site.created",
            payload={"name": "Site A"},
        )
        append_audit_entry(
            connection,
            tenant_id=tenant_id,
            actor="technicien-1",
            action="site.updated",
            payload={"name": "Site A bis"},
        )

    # On simule une falsification par un accès direct et privilégié à la
    # base (contournant l'application et le trigger append-only), pour
    # prouver que la chaîne de hachage détecte quand même la fraude.
    admin_engine = create_engine(ADMIN_DATABASE_URL)
    with admin_engine.begin() as admin_connection:
        admin_connection.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update"))
        admin_connection.execute(
            text(
                'UPDATE audit_log SET payload = \'{"name": "falsifie"}\'::jsonb '
                "WHERE tenant_id = :id AND action = 'site.created'"
            ),
            {"id": tenant_id},
        )
        admin_connection.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_update"))
    admin_engine.dispose()

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        result = verify_chain_integrity(connection, tenant_id=tenant_id)

    assert result.valid is False
    assert result.reason is not None
