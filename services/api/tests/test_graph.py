import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db import engine
from app.graph import (
    RelationConflict,
    create_relation,
    end_relation,
    list_node_relations,
)
from app.graph_vocabulary import VocabularyError
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_relations_for_tenant

T0 = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)


def _insert_location(connection, *, tenant_id, site_id, code, parent_id=None) -> uuid.UUID:
    location_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO functional_locations (id, tenant_id, site_id, parent_id, code, name) "
            "VALUES (:id, :tenant_id, :site_id, :parent_id, :code, :name)"
        ),
        {
            "id": location_id,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "parent_id": parent_id,
            "code": code,
            "name": code,
        },
    )
    return location_id


def _create_tenant_with_graph(name: str) -> dict:
    """Un site, une CTA avec son ventilateur, un tableau électrique, un exemplaire."""
    tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)

        site_id = uuid.uuid4()
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site')"),
            {"id": site_id, "tenant_id": tenant_id},
        )
        ahu = _insert_location(connection, tenant_id=tenant_id, site_id=site_id, code="cta-01")
        fan = _insert_location(
            connection, tenant_id=tenant_id, site_id=site_id, code="cta-01-vent", parent_id=ahu
        )
        panel = _insert_location(
            connection, tenant_id=tenant_id, site_id=site_id, code="tableau-elec"
        )

        product_model_id = uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO product_models (id, tenant_id, manufacturer, reference, category) "
                "VALUES (:id, :tenant_id, 'Fabricant Demo', 'CTA-X', 'cta')"
            ),
            {"id": product_model_id, "tenant_id": tenant_id},
        )
        unit_id = uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO physical_units (id, tenant_id, product_model_id, serial_number) "
                "VALUES (:id, :tenant_id, :product_model_id, :serial)"
            ),
            {
                "id": unit_id,
                "tenant_id": tenant_id,
                "product_model_id": product_model_id,
                "serial": f"SN-{unit_id}",
            },
        )

    return {
        "tenant_id": tenant_id,
        "site": site_id,
        "ahu": ahu,
        "fan": fan,
        "panel": panel,
        "unit": unit_id,
    }


def _cleanup_tenant(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    purge_relations_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("physical_units", "functional_locations", "product_models", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant_with_graph("ClientGraphA")
    tenant_b = _create_tenant_with_graph("ClientGraphB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        _cleanup_tenant(tenant)


def _node_types(tenant_id) -> dict:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        rows = connection.execute(text("SELECT id, node_type FROM graph_nodes")).all()
    return {row.id: row.node_type for row in rows}


def _relate(connection, tenant: dict, **overrides) -> uuid.UUID:
    params = {
        "tenant_id": tenant["tenant_id"],
        "subject_id": tenant["panel"],
        "predicate": "poweredBy",
        "object_id": tenant["ahu"],
        "created_by": "responsable-test",
        "valid_from": T0,
    }
    params.update(overrides)
    return create_relation(connection, **params)


# --- Registre d'identité ------------------------------------------------


def test_inserting_asset_rows_registers_graph_nodes(two_tenants) -> None:
    tenant_a, _ = two_tenants

    node_types = _node_types(tenant_a["tenant_id"])

    assert node_types[tenant_a["site"]] == "site"
    assert node_types[tenant_a["ahu"]] == "functional_location"
    assert node_types[tenant_a["unit"]] == "physical_unit"


def test_deleting_an_asset_row_unregisters_its_node(two_tenants) -> None:
    tenant_a, _ = two_tenants

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        connection.execute(
            text("DELETE FROM physical_units WHERE id = :id"), {"id": tenant_a["unit"]}
        )

    assert tenant_a["unit"] not in _node_types(tenant_a["tenant_id"])


def test_tenant_isolation_on_graph_nodes(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants

    visible_to_b = _node_types(tenant_b["tenant_id"])

    for key in ("site", "ahu", "fan", "panel", "unit"):
        assert tenant_a[key] not in visible_to_b


def test_no_tenant_context_means_no_node_visible(two_tenants) -> None:
    with engine.begin() as connection:
        rows = connection.execute(text("SELECT id FROM graph_nodes")).fetchall()
    assert rows == []


# --- Relations ------------------------------------------------


def test_tenant_isolation_on_relations(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        _relate(connection, tenant_a)

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b["tenant_id"])
        rows = connection.execute(text("SELECT id FROM relations")).fetchall()

    assert rows == []


def test_cross_tenant_relation_is_impossible_at_database_level(two_tenants) -> None:
    """Même si le code applicatif oubliait une vérification, la base refuse de
    relier un nœud du client A à un nœud du client B (clés composées)."""
    tenant_a, tenant_b = two_tenants

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            connection.execute(
                text(
                    "INSERT INTO relations (id, tenant_id, subject_id, predicate, object_id, "
                    "valid_from, vocabulary_version, created_by) "
                    "VALUES (:id, :tenant_id, :subject_id, 'feeds', :object_id, now(), 'test', "
                    "'test')"
                ),
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_a["tenant_id"],
                    "subject_id": tenant_a["ahu"],
                    "object_id": tenant_b["ahu"],
                },
            )


def test_other_tenant_node_is_not_found_by_the_application(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants

    with pytest.raises(LookupError):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            _relate(connection, tenant_a, object_id=tenant_b["ahu"])


def test_a_node_cannot_be_related_to_itself(two_tenants) -> None:
    tenant_a, _ = two_tenants

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            connection.execute(
                text(
                    "INSERT INTO relations (id, tenant_id, subject_id, predicate, object_id, "
                    "valid_from, vocabulary_version, created_by) "
                    "VALUES (:id, :tenant_id, :node, 'feeds', :node, now(), 'test', 'test')"
                ),
                {"id": uuid.uuid4(), "tenant_id": tenant_a["tenant_id"], "node": tenant_a["ahu"]},
            )


def test_vocabulary_is_enforced_on_creation(two_tenants) -> None:
    tenant_a, _ = two_tenants

    with pytest.raises(VocabularyError):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            _relate(connection, tenant_a, predicate="feeds", subject_id=tenant_a["unit"])


def test_same_open_relation_cannot_exist_twice(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        _relate(connection, tenant_a)

    with pytest.raises(RelationConflict):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            _relate(connection, tenant_a)


def test_symmetric_relation_is_not_duplicated_in_reverse(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        _relate(connection, tenant_a, predicate="connectedTo")

    with pytest.raises(RelationConflict, match="autre sens"):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            _relate(
                connection,
                tenant_a,
                predicate="connectedTo",
                subject_id=tenant_a["ahu"],
                object_id=tenant_a["panel"],
            )


def test_ending_a_relation_keeps_it_in_history_and_allows_a_new_one(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        first = _relate(connection, tenant_a)
        end_relation(connection, relation_id=first, valid_to=T0 + timedelta(days=30))
        second = _relate(connection, tenant_a, valid_from=T0 + timedelta(days=30))

        current = list_node_relations(connection, tenant_a["panel"])
        history = list_node_relations(connection, tenant_a["panel"], include_ended=True)

    current_ids = {edge["id"] for edge in current if not edge["derived"]}
    history_ids = {edge["id"] for edge in history if not edge["derived"]}
    assert current_ids == {second}
    assert history_ids == {first, second}


def test_end_date_must_follow_start_date(two_tenants) -> None:
    tenant_a, _ = two_tenants

    with pytest.raises(ValueError, match="postérieure"):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            relation_id = _relate(connection, tenant_a)
            end_relation(connection, relation_id=relation_id, valid_to=T0)


def test_relation_core_fields_cannot_be_rewritten(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        relation_id = _relate(connection, tenant_a)

    with pytest.raises(DBAPIError, match="non modifiable"):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            connection.execute(
                text("UPDATE relations SET predicate = 'feeds' WHERE id = :id"),
                {"id": relation_id},
            )


def test_a_closed_relation_cannot_be_reopened(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        relation_id = _relate(connection, tenant_a)
        end_relation(connection, relation_id=relation_id, valid_to=T0 + timedelta(days=1))

    with pytest.raises(DBAPIError, match="déjà close"):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            connection.execute(
                text("UPDATE relations SET valid_to = NULL WHERE id = :id"), {"id": relation_id}
            )


def test_a_relation_cannot_be_deleted(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        relation_id = _relate(connection, tenant_a)

    with pytest.raises(DBAPIError, match="suppression interdite"):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            connection.execute(text("DELETE FROM relations WHERE id = :id"), {"id": relation_id})


def test_a_node_with_relations_cannot_be_deleted(two_tenants) -> None:
    """Supprimer un actif relié casserait le graphe : la base l'empêche."""
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        _relate(connection, tenant_a)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            connection.execute(
                text("DELETE FROM functional_locations WHERE id = :id"), {"id": tenant_a["panel"]}
            )


# --- Relations déduites de la hiérarchie ------------------------------------------------


def test_hierarchy_is_exposed_as_derived_relations(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        site_edges = list_node_relations(connection, tenant_a["site"])
        ahu_edges = list_node_relations(connection, tenant_a["ahu"])
        fan_edges = list_node_relations(connection, tenant_a["fan"])

    assert {(e["label"], e["object_id"]) for e in site_edges} == {
        ("contains", tenant_a["ahu"]),
        ("contains", tenant_a["panel"]),
    }
    assert ("isContainedIn", tenant_a["site"]) in {(e["label"], e["subject_id"]) for e in ahu_edges}
    assert ("hasPart", tenant_a["fan"]) in {(e["label"], e["object_id"]) for e in ahu_edges}
    assert [(e["label"], e["subject_id"], e["derived"]) for e in fan_edges] == [
        ("isPartOf", tenant_a["ahu"], True)
    ]


def test_stored_relation_is_seen_from_both_ends(two_tenants) -> None:
    tenant_a, _ = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        _relate(
            connection,
            tenant_a,
            predicate="feeds",
            subject_id=tenant_a["ahu"],
            object_id=tenant_a["panel"],
        )
        from_ahu = [e for e in list_node_relations(connection, tenant_a["ahu"]) if not e["derived"]]
        from_panel = [
            e for e in list_node_relations(connection, tenant_a["panel"]) if not e["derived"]
        ]

    assert [(e["label"], e["direction"]) for e in from_ahu] == [("feeds", "outgoing")]
    assert [(e["label"], e["direction"]) for e in from_panel] == [("isFedBy", "incoming")]
