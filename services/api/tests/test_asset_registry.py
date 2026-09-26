import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.assets import assign_physical_unit, get_current_occupant, get_occupant_as_of
from app.db import engine
from app.tenancy import set_tenant_context


def _create_tenant_with_asset(connection, *, tenant_name: str) -> dict:
    tenant_id = uuid.uuid4()
    connection.execute(
        text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
        {"id": tenant_id, "name": tenant_name, "slug": f"{tenant_name.lower()}-{tenant_id}"},
    )

    set_tenant_context(connection, tenant_id)

    site_id = uuid.uuid4()
    connection.execute(
        text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
        {"id": site_id, "tenant_id": tenant_id, "name": "Site principal"},
    )

    product_model_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO product_models (id, tenant_id, manufacturer, reference, equipment_type) "
            "VALUES (:id, :tenant_id, :manufacturer, :reference, :equipment_type)"
        ),
        {
            "id": product_model_id,
            "tenant_id": tenant_id,
            "manufacturer": "Fabricant Demo",
            "reference": "PAC-100",
            "equipment_type": "heat_pump",
        },
    )

    functional_location_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
            "VALUES (:id, :tenant_id, :site_id, :code, :name)"
        ),
        {
            "id": functional_location_id,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "code": "sous-station-1",
            "name": "Sous-station 1",
        },
    )

    return {
        "tenant_id": tenant_id,
        "site_id": site_id,
        "product_model_id": product_model_id,
        "functional_location_id": functional_location_id,
    }


def _create_physical_unit(
    connection, *, tenant_id: uuid.UUID, product_model_id: uuid.UUID
) -> uuid.UUID:
    unit_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO physical_units (id, tenant_id, product_model_id, serial_number) "
            "VALUES (:id, :tenant_id, :product_model_id, :serial_number)"
        ),
        {
            "id": unit_id,
            "tenant_id": tenant_id,
            "product_model_id": product_model_id,
            "serial_number": f"SN-{unit_id}",
        },
    )
    return unit_id


@pytest.fixture
def two_tenants_with_assets():
    with engine.begin() as connection:
        tenant_a = _create_tenant_with_asset(connection, tenant_name="ClientA")
        set_tenant_context(connection, tenant_a["tenant_id"])
        tenant_a["unit_1"] = _create_physical_unit(
            connection,
            tenant_id=tenant_a["tenant_id"],
            product_model_id=tenant_a["product_model_id"],
        )
        tenant_a["unit_2"] = _create_physical_unit(
            connection,
            tenant_id=tenant_a["tenant_id"],
            product_model_id=tenant_a["product_model_id"],
        )

    with engine.begin() as connection:
        tenant_b = _create_tenant_with_asset(connection, tenant_name="ClientB")
        set_tenant_context(connection, tenant_b["tenant_id"])
        tenant_b["unit_1"] = _create_physical_unit(
            connection,
            tenant_id=tenant_b["tenant_id"],
            product_model_id=tenant_b["product_model_id"],
        )

    yield tenant_a, tenant_b

    for tenant in (tenant_a, tenant_b):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant["tenant_id"])
            connection.execute(
                text("DELETE FROM functional_location_assignments WHERE tenant_id = :id"),
                {"id": tenant["tenant_id"]},
            )
            connection.execute(
                text("DELETE FROM physical_unit_lifecycle_events WHERE tenant_id = :id"),
                {"id": tenant["tenant_id"]},
            )
            connection.execute(
                text("DELETE FROM physical_units WHERE tenant_id = :id"),
                {"id": tenant["tenant_id"]},
            )
            connection.execute(
                text("DELETE FROM functional_locations WHERE tenant_id = :id"),
                {"id": tenant["tenant_id"]},
            )
            connection.execute(
                text("DELETE FROM product_models WHERE tenant_id = :id"),
                {"id": tenant["tenant_id"]},
            )
            connection.execute(
                text("DELETE FROM sites WHERE tenant_id = :id"), {"id": tenant["tenant_id"]}
            )
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM tenants WHERE id = :id"), {"id": tenant["tenant_id"]}
            )


def test_replacing_a_unit_keeps_the_history(two_tenants_with_assets) -> None:
    tenant_a, _tenant_b = two_tenants_with_assets
    t0 = datetime.now(UTC) - timedelta(days=10)
    t1 = datetime.now(UTC) - timedelta(days=5)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        assign_physical_unit(
            connection,
            tenant_id=tenant_a["tenant_id"],
            functional_location_id=tenant_a["functional_location_id"],
            physical_unit_id=tenant_a["unit_1"],
            valid_from=t0,
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        # Remplacement : unit_1 est retiré, unit_2 le remplace.
        assign_physical_unit(
            connection,
            tenant_id=tenant_a["tenant_id"],
            functional_location_id=tenant_a["functional_location_id"],
            physical_unit_id=tenant_a["unit_2"],
            valid_from=t1,
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        current = get_current_occupant(
            connection, functional_location_id=tenant_a["functional_location_id"]
        )
        before_replacement = get_occupant_as_of(
            connection,
            functional_location_id=tenant_a["functional_location_id"],
            as_of=t0 + timedelta(days=1),
        )
        after_replacement = get_occupant_as_of(
            connection,
            functional_location_id=tenant_a["functional_location_id"],
            as_of=t1 + timedelta(days=1),
        )

    assert current == tenant_a["unit_2"]
    assert before_replacement == tenant_a["unit_1"]
    assert after_replacement == tenant_a["unit_2"]


def test_two_open_assignments_on_same_location_are_rejected(two_tenants_with_assets) -> None:
    tenant_a, _tenant_b = two_tenants_with_assets

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        assign_physical_unit(
            connection,
            tenant_id=tenant_a["tenant_id"],
            functional_location_id=tenant_a["functional_location_id"],
            physical_unit_id=tenant_a["unit_1"],
        )

    # On contourne la fonction applicative pour tenter d'insérer une seconde
    # affectation ouverte sur la même position : l'index partiel unique doit
    # bloquer, quel que soit le chemin de code emprunté.
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            connection.execute(
                text(
                    "INSERT INTO functional_location_assignments "
                    "(id, tenant_id, functional_location_id, physical_unit_id, valid_from) "
                    "VALUES (:id, :tenant_id, :functional_location_id, :physical_unit_id, now())"
                ),
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_a["tenant_id"],
                    "functional_location_id": tenant_a["functional_location_id"],
                    "physical_unit_id": tenant_a["unit_2"],
                },
            )


@pytest.mark.parametrize(
    "table",
    ["product_models", "physical_units", "functional_locations"],
)
def test_tenant_isolation_on_asset_registry_tables(two_tenants_with_assets, table) -> None:
    tenant_a, tenant_b = two_tenants_with_assets

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        rows = connection.execute(text(f"SELECT tenant_id FROM {table}")).fetchall()

    seen_tenant_ids = {row.tenant_id for row in rows}
    assert seen_tenant_ids == {tenant_a["tenant_id"]}
    assert tenant_b["tenant_id"] not in seen_tenant_ids


def test_tenant_isolation_on_functional_location_assignments(two_tenants_with_assets) -> None:
    tenant_a, tenant_b = two_tenants_with_assets

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        assign_physical_unit(
            connection,
            tenant_id=tenant_a["tenant_id"],
            functional_location_id=tenant_a["functional_location_id"],
            physical_unit_id=tenant_a["unit_1"],
        )
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b["tenant_id"])
        assign_physical_unit(
            connection,
            tenant_id=tenant_b["tenant_id"],
            functional_location_id=tenant_b["functional_location_id"],
            physical_unit_id=tenant_b["unit_1"],
        )

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        rows = connection.execute(
            text("SELECT tenant_id FROM functional_location_assignments")
        ).fetchall()

    seen_tenant_ids = {row.tenant_id for row in rows}
    assert seen_tenant_ids == {tenant_a["tenant_id"]}
    assert tenant_b["tenant_id"] not in seen_tenant_ids
