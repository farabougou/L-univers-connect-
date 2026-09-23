import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db import engine
from app.graph import create_relation, list_node_relations
from app.spatial import (
    SpatialConflict,
    SpatialNotFound,
    close_space,
    create_space,
    location_space_history,
    record_location_space,
)
from app.spatial_vocabulary import SpatialVocabularyError
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_relations_for_tenant

T0 = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)


def _insert_site(connection, tenant_id, name) -> uuid.UUID:
    site_id = uuid.uuid4()
    connection.execute(
        text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
        {"id": site_id, "tenant_id": tenant_id, "name": name},
    )
    return site_id


def _insert_location(connection, tenant_id, site_id, code) -> uuid.UUID:
    location_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
            "VALUES (:id, :tenant_id, :site_id, :code, :code)"
        ),
        {"id": location_id, "tenant_id": tenant_id, "site_id": site_id, "code": code},
    )
    return location_id


def _create_tenant(name: str) -> dict:
    """Deux sites ; sur le premier : bâtiment → étage → pièce, et une CTA."""
    tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        site = _insert_site(connection, tenant_id, "Site 1")
        other_site = _insert_site(connection, tenant_id, "Site 2")
        ahu = _insert_location(connection, tenant_id, site, "cta-01")
        other_site_location = _insert_location(connection, tenant_id, other_site, "pac-01")

        def space(space_type, code, parent_id=None, site_id=site):
            return create_space(
                connection,
                tenant_id=tenant_id,
                site_id=site_id,
                parent_id=parent_id,
                space_type=space_type,
                code=code,
                name=code,
                valid_from=T0,
            )

        building = space("building", "BAT-A")
        floor = space("floor", "BAT-A-E1", building)
        room = space("room", "BAT-A-E1-104", floor)
        other_building = space("building", "BAT-Z", site_id=other_site)

    return {
        "tenant_id": tenant_id,
        "site": site,
        "other_site": other_site,
        "ahu": ahu,
        "other_site_location": other_site_location,
        "building": building,
        "floor": floor,
        "room": room,
        "other_building": other_building,
    }


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    purge_relations_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "functional_location_space_history",
            "functional_locations",
            "spaces",
            "sites",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientSpatialA")
    tenant_b = _create_tenant("ClientSpatialB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        _cleanup(tenant)


@contextmanager
def _in_tenant(tenant):
    """Transaction positionnée sur le tenant donné."""
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        yield connection


def _place(connection, tenant, location, space_id, when):
    record_location_space(
        connection,
        tenant_id=tenant["tenant_id"],
        functional_location_id=location,
        space_id=space_id,
        valid_from=when,
        changed_by="responsable-test",
        reason=None,
    )


# --- Isolation et registre ------------------------------------------------


def test_spaces_are_registered_as_graph_nodes(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        node_type = connection.execute(
            text("SELECT node_type FROM graph_nodes WHERE id = :id"), {"id": tenant_a["room"]}
        ).scalar()
    assert node_type == "space"


@pytest.mark.parametrize("table", ["spaces", "functional_location_space_history"])
def test_tenant_isolation_on_spatial_tables(two_tenants, table) -> None:
    tenant_a, tenant_b = two_tenants
    query = text(f"SELECT 1 FROM {table} WHERE tenant_id = :id")
    with _in_tenant(tenant_a) as connection:
        _place(connection, tenant_a, tenant_a["ahu"], tenant_a["room"], T0)
        seen_by_a = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()

    with _in_tenant(tenant_b) as connection:
        seen_by_b = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()

    assert seen_by_a
    assert seen_by_b == []


def test_parent_of_another_tenant_is_not_found(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with pytest.raises(SpatialNotFound):
        with _in_tenant(tenant_a) as connection:
            create_space(
                connection,
                tenant_id=tenant_a["tenant_id"],
                site_id=tenant_a["site"],
                parent_id=tenant_b["floor"],
                space_type="room",
                code="piege",
                name="piege",
                valid_from=T0,
            )


# --- Règles de l'arbre spatial ------------------------------------------------


@pytest.mark.parametrize(
    ("space_type", "parent_key", "message"),
    [
        ("room", None, "directement sous le site"),
        ("building", "floor", "dans un « floor »"),
        ("piscine", None, "inconnu"),
    ],
)
def test_space_placement_rules(two_tenants, space_type, parent_key, message) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(SpatialVocabularyError, match=message):
        with _in_tenant(tenant_a) as connection:
            create_space(
                connection,
                tenant_id=tenant_a["tenant_id"],
                site_id=tenant_a["site"],
                parent_id=tenant_a[parent_key] if parent_key else None,
                space_type=space_type,
                code="X",
                name="X",
                valid_from=T0,
            )


def test_parent_on_another_site_is_rejected_by_the_application(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(SpatialConflict, match="autre site"):
        with _in_tenant(tenant_a) as connection:
            create_space(
                connection,
                tenant_id=tenant_a["tenant_id"],
                site_id=tenant_a["other_site"],
                parent_id=tenant_a["building"],
                space_type="floor",
                code="E9",
                name="E9",
                valid_from=T0,
            )


def test_parent_on_another_site_is_rejected_by_the_database(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(IntegrityError):
        with _in_tenant(tenant_a) as connection:
            connection.execute(
                text(
                    "INSERT INTO spaces (id, tenant_id, site_id, parent_id, space_type, code, "
                    "name, valid_from) VALUES (:id, :tenant_id, :site_id, :parent_id, 'floor', "
                    "'E9', 'E9', now())"
                ),
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_a["tenant_id"],
                    "site_id": tenant_a["other_site"],
                    "parent_id": tenant_a["building"],
                },
            )


def test_open_code_is_unique_per_site_but_reusable_after_closing(two_tenants) -> None:
    tenant_a, _ = two_tenants

    def new_building(connection):
        return create_space(
            connection,
            tenant_id=tenant_a["tenant_id"],
            site_id=tenant_a["site"],
            parent_id=None,
            space_type="building",
            code="BAT-B",
            name="Bâtiment B",
            valid_from=T0,
        )

    with _in_tenant(tenant_a) as connection:
        first = new_building(connection)
    with pytest.raises(SpatialConflict, match="déjà utilisé"):
        with _in_tenant(tenant_a) as connection:
            new_building(connection)
    with _in_tenant(tenant_a) as connection:
        close_space(connection, space_id=first, valid_to=T0 + timedelta(days=1))
        second = new_building(connection)
    assert second != first


def test_space_structure_cannot_be_rewritten(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(DBAPIError, match="non modifiable"):
        with _in_tenant(tenant_a) as connection:
            connection.execute(
                text("UPDATE spaces SET name = 'Renommé' WHERE id = :id"),
                {"id": tenant_a["room"]},
            )


def test_closed_space_cannot_be_reopened(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        close_space(connection, space_id=tenant_a["room"], valid_to=T0 + timedelta(days=1))
    with pytest.raises(DBAPIError, match="déjà close"):
        with _in_tenant(tenant_a) as connection:
            connection.execute(
                text("UPDATE spaces SET valid_to = NULL WHERE id = :id"), {"id": tenant_a["room"]}
            )


def test_space_with_open_children_cannot_be_closed(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(SpatialConflict, match="espaces ouverts"):
        with _in_tenant(tenant_a) as connection:
            close_space(connection, space_id=tenant_a["building"], valid_to=T0 + timedelta(days=1))


def test_space_holding_a_location_cannot_be_closed(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(SpatialConflict, match="positions fonctionnelles"):
        with _in_tenant(tenant_a) as connection:
            _place(connection, tenant_a, tenant_a["ahu"], tenant_a["room"], T0)
            close_space(connection, space_id=tenant_a["room"], valid_to=T0 + timedelta(days=1))


# --- Emplacement des positions fonctionnelles ------------------------------------------------


def test_moving_a_location_keeps_the_full_history(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        _place(connection, tenant_a, tenant_a["ahu"], tenant_a["room"], T0)
        _place(connection, tenant_a, tenant_a["ahu"], tenant_a["floor"], T0 + timedelta(days=10))
        _place(connection, tenant_a, tenant_a["ahu"], None, T0 + timedelta(days=20))

        current = connection.execute(
            text("SELECT space_id FROM functional_locations WHERE id = :id"),
            {"id": tenant_a["ahu"]},
        ).scalar()
        history = location_space_history(connection, tenant_a["ahu"])

    assert current is None
    assert [row["space_id"] for row in history] == [tenant_a["room"], tenant_a["floor"], None]


def test_a_move_cannot_be_dated_before_the_previous_one(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(ValueError, match="précédent changement"):
        with _in_tenant(tenant_a) as connection:
            _place(connection, tenant_a, tenant_a["ahu"], tenant_a["room"], T0)
            _place(connection, tenant_a, tenant_a["ahu"], tenant_a["floor"], T0 - timedelta(days=1))


def test_placing_in_the_same_space_again_is_refused(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(SpatialConflict, match="déjà à cet emplacement"):
        with _in_tenant(tenant_a) as connection:
            _place(connection, tenant_a, tenant_a["ahu"], tenant_a["room"], T0)
            _place(connection, tenant_a, tenant_a["ahu"], tenant_a["room"], T0 + timedelta(days=1))


def test_location_cannot_be_placed_on_another_site(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(SpatialConflict, match="autre site"):
        with _in_tenant(tenant_a) as connection:
            _place(connection, tenant_a, tenant_a["ahu"], tenant_a["other_building"], T0)


def test_location_on_another_site_is_rejected_by_the_database(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(IntegrityError):
        with _in_tenant(tenant_a) as connection:
            connection.execute(
                text("UPDATE functional_locations SET space_id = :space WHERE id = :id"),
                {"space": tenant_a["other_building"], "id": tenant_a["ahu"]},
            )


def test_location_cannot_be_placed_in_a_closed_space(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with pytest.raises(SpatialConflict, match="clos"):
        with _in_tenant(tenant_a) as connection:
            close_space(connection, space_id=tenant_a["room"], valid_to=T0 + timedelta(days=1))
            _place(connection, tenant_a, tenant_a["ahu"], tenant_a["room"], T0 + timedelta(days=2))


# --- Graphe ------------------------------------------------


def test_spatial_hierarchy_and_location_appear_in_the_graph(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        _place(connection, tenant_a, tenant_a["ahu"], tenant_a["room"], T0)
        site_edges = list_node_relations(connection, tenant_a["site"])
        floor_edges = list_node_relations(connection, tenant_a["floor"])
        room_edges = list_node_relations(connection, tenant_a["room"])
        ahu_edges = list_node_relations(connection, tenant_a["ahu"])

    def labels(edges):
        return {
            (e["label"], e["object_id"] if e["direction"] == "outgoing" else e["subject_id"])
            for e in edges
        }

    assert labels(site_edges) == {
        ("contains", tenant_a["building"]),
        ("contains", tenant_a["ahu"]),
    }
    assert labels(floor_edges) == {
        ("isPartOf", tenant_a["building"]),
        ("hasPart", tenant_a["room"]),
    }
    assert ("isLocationOf", tenant_a["ahu"]) in labels(room_edges)
    assert ("locatedIn", tenant_a["room"]) in labels(ahu_edges)


def test_transverse_relations_with_spaces(two_tenants) -> None:
    """Une pièce desservie par une zone CVC, elle-même alimentée par la CTA."""
    tenant_a, _ = two_tenants
    with _in_tenant(tenant_a) as connection:
        hvac_zone = create_space(
            connection,
            tenant_id=tenant_a["tenant_id"],
            site_id=tenant_a["site"],
            parent_id=tenant_a["building"],
            space_type="zone",
            code="ZONE-CVC-NORD",
            name="Zone CVC nord",
            valid_from=T0,
        )
        common = {"tenant_id": tenant_a["tenant_id"], "created_by": "test", "valid_from": T0}
        create_relation(
            connection,
            subject_id=tenant_a["room"],
            predicate="servedBy",
            object_id=hvac_zone,
            **common,
        )
        create_relation(
            connection, subject_id=tenant_a["ahu"], predicate="feeds", object_id=hvac_zone, **common
        )
        zone_edges = list_node_relations(connection, hvac_zone)

    stored = {(e["label"], e["derived"]) for e in zone_edges if not e["derived"]}
    assert stored == {("serves", False), ("isFedBy", False)}
