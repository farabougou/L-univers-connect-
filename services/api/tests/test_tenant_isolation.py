import uuid

import pytest
from sqlalchemy import text

from app.db import engine
from app.tenancy import set_tenant_context


@pytest.fixture
def two_tenants_with_one_site_each():
    """Crée deux tenants, chacun avec un site, et nettoie après le test."""
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    site_a_id = uuid.uuid4()
    site_b_id = uuid.uuid4()

    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            [
                {"id": tenant_a_id, "name": "Client A", "slug": f"client-a-{tenant_a_id}"},
                {"id": tenant_b_id, "name": "Client B", "slug": f"client-b-{tenant_b_id}"},
            ],
        )

        # Chaque insertion de site se fait avec le contexte du bon tenant :
        # la politique RLS (WITH CHECK) refuserait sinon l'écriture.
        set_tenant_context(connection, tenant_a_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
            {"id": site_a_id, "tenant_id": tenant_a_id, "name": "Site A"},
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
            {"id": site_b_id, "tenant_id": tenant_b_id, "name": "Site B"},
        )

    yield tenant_a_id, tenant_b_id, site_a_id, site_b_id

    # Nettoyage : chaque suppression de site se fait dans le contexte du bon
    # tenant, puisque la politique RLS s'applique aussi aux suppressions.
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a_id)
        connection.execute(text("DELETE FROM sites WHERE tenant_id = :id"), {"id": tenant_a_id})
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b_id)
        connection.execute(text("DELETE FROM sites WHERE tenant_id = :id"), {"id": tenant_b_id})
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM tenants WHERE id IN (:a, :b)"), {"a": tenant_a_id, "b": tenant_b_id}
        )


def test_tenant_only_sees_its_own_site(two_tenants_with_one_site_each) -> None:
    tenant_a_id, tenant_b_id, site_a_id, site_b_id = two_tenants_with_one_site_each

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a_id)
        rows = connection.execute(text("SELECT id FROM sites")).fetchall()

    visible_ids = {row.id for row in rows}
    assert visible_ids == {site_a_id}
    assert site_b_id not in visible_ids


def test_tenant_cannot_see_another_tenant_data_even_by_id(two_tenants_with_one_site_each) -> None:
    tenant_a_id, _tenant_b_id, _site_a_id, site_b_id = two_tenants_with_one_site_each

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a_id)
        row = connection.execute(
            text("SELECT id FROM sites WHERE id = :id"), {"id": site_b_id}
        ).fetchone()

    assert row is None


def test_no_tenant_context_means_no_rows_visible(two_tenants_with_one_site_each) -> None:
    with engine.begin() as connection:
        # Aucun tenant déclaré pour cette transaction : la politique doit
        # bloquer par défaut, jamais laisser tout voir par erreur.
        rows = connection.execute(text("SELECT id FROM sites")).fetchall()

    assert rows == []
