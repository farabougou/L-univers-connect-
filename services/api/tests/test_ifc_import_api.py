"""Import BIM/IFC (ADR 011, section 2) : envoi, propositions, acceptation
dans l'ordre de la hiérarchie, rejet."""

import uuid
from unittest.mock import patch

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)


def _build_ifc_file() -> bytes:
    f = ifcopenshell.file(schema="IFC4")
    project = ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name="Projet Demo")
    site = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite", name="Site IFC")
    building = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuilding", name="Bâtiment A")
    storey = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuildingStorey", name="Étage 1")
    space = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSpace", name="Chaufferie")
    ahu = ifcopenshell.api.root.create_entity(f, ifc_class="IfcUnitaryEquipment", name="CTA-01")

    ifcopenshell.api.aggregate.assign_object(f, relating_object=project, products=[site])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=site, products=[building])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=building, products=[storey])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=storey, products=[space])
    ifcopenshell.api.spatial.assign_container(f, relating_structure=space, products=[ahu])
    return f.to_string().encode("utf-8")


def _create_tenant(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
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
    return {"tenant_id": tenant_id, "site_id": site_id}


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientIfcImportA")
    tenant_b = _create_tenant("ClientIfcImportB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant["tenant_id"])
            for table in ("ifc_import_proposals", "ifc_import_batches"):
                connection.execute(
                    text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant["tenant_id"]}
                )
        purge_tenant(tenant["tenant_id"])


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(tenant_id=str(tenant['tenant_id']), roles=roles)}"
    }


def _call(method, path, headers, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def _manager(tenant):
    return _headers(tenant, ["responsable_exploitation"])


def _tech(tenant):
    return _headers(tenant, ["technicien"])


def _upload_and_confirm(tenant, headers, content: bytes = None):
    upload_url = _call(
        "POST",
        f"/sites/{tenant['site_id']}/ifc-imports/upload-url",
        headers,
        json={"filename": "batiment-a.ifc"},
    )
    assert upload_url.status_code == 200, upload_url.text
    object_key = upload_url.json()["object_key"]

    with patch(
        "app.routers.ifc_import.download_object_bytes",
        return_value=content if content is not None else _build_ifc_file(),
    ):
        confirmed = _call(
            "POST",
            f"/sites/{tenant['site_id']}/ifc-imports",
            headers,
            json={"object_key": object_key, "filename": "batiment-a.ifc", "sha256": "a" * 64},
        )
    return confirmed


def test_upload_url_is_scoped_to_the_tenant_and_site(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call(
        "POST",
        f"/sites/{tenant_a['site_id']}/ifc-imports/upload-url",
        _manager(tenant_a),
        json={"filename": "modele.ifc"},
    )
    assert response.status_code == 200, response.text
    object_key = response.json()["object_key"]
    assert str(tenant_a["tenant_id"]) in object_key
    assert str(tenant_a["site_id"]) in object_key


def test_confirm_parses_and_stores_proposals(two_tenants) -> None:
    tenant_a, _ = two_tenants
    batch = _upload_and_confirm(tenant_a, _manager(tenant_a))

    assert batch.status_code == 201, batch.text
    body = batch.json()
    assert body["status"] == "ready"
    assert body["ifc_schema"] == "IFC4"
    assert body["space_proposal_count"] == 3
    assert body["equipment_proposal_count"] == 1

    proposals = _call(
        "GET", f"/ifc-imports/{body['id']}/proposals", _tech(tenant_a)
    ).json()
    assert len(proposals) == 4
    assert {p["status"] for p in proposals} == {"proposed"}


def test_confirm_with_an_invalid_file_marks_the_batch_failed(two_tenants) -> None:
    tenant_a, _ = two_tenants
    batch = _upload_and_confirm(tenant_a, _manager(tenant_a), content=b"pas de tout un fichier ifc")

    assert batch.status_code == 201, batch.text
    body = batch.json()
    assert body["status"] == "failed"
    assert body["error_code"] == "IFC_IMPORT_INVALID_FORMAT"


def test_accepting_proposals_in_hierarchy_order_creates_real_spaces_and_equipment(
    two_tenants,
) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    batch = _upload_and_confirm(tenant_a, manager).json()
    proposals = _call(
        "GET", f"/ifc-imports/{batch['id']}/proposals", manager
    ).json()
    by_class = {p["ifc_class"]: p for p in proposals}

    building = _call(
        "POST", f"/ifc-import-proposals/{by_class['IfcBuilding']['id']}/accept", manager
    )
    storey = _call(
        "POST", f"/ifc-import-proposals/{by_class['IfcBuildingStorey']['id']}/accept", manager
    )
    space = _call(
        "POST", f"/ifc-import-proposals/{by_class['IfcSpace']['id']}/accept", manager
    )
    equipment = _call(
        "POST", f"/ifc-import-proposals/{by_class['IfcUnitaryEquipment']['id']}/accept", manager
    )

    assert building.status_code == 200, building.text
    assert storey.status_code == 200, storey.text
    assert space.status_code == 200, space.text
    assert equipment.status_code == 200, equipment.text

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        created_space = connection.execute(
            text("SELECT space_type, parent_id FROM spaces WHERE id = :id"),
            {"id": space.json()["created_node_id"]},
        ).mappings().one()
        created_storey = connection.execute(
            text("SELECT parent_id FROM spaces WHERE id = :id"),
            {"id": storey.json()["created_node_id"]},
        ).mappings().one()
        created_location = connection.execute(
            text("SELECT space_id, kind FROM functional_locations WHERE id = :id"),
            {"id": equipment.json()["created_node_id"]},
        ).mappings().one()

    assert created_space["space_type"] == "room"
    assert str(created_space["parent_id"]) == storey.json()["created_node_id"]
    assert str(created_storey["parent_id"]) == building.json()["created_node_id"]
    assert str(created_location["space_id"]) == space.json()["created_node_id"]
    assert created_location["kind"] == "equipment"


def test_accepting_out_of_order_is_refused(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    batch = _upload_and_confirm(tenant_a, manager).json()
    proposals = _call("GET", f"/ifc-imports/{batch['id']}/proposals", manager).json()
    storey_id = next(p["id"] for p in proposals if p["ifc_class"] == "IfcBuildingStorey")

    response = _call("POST", f"/ifc-import-proposals/{storey_id}/accept", manager)

    assert response.status_code == 422
    assert response.json()["code"] == "IFC_IMPORT_PARENT_NOT_ACCEPTED"


def test_accepting_twice_is_a_conflict(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    batch = _upload_and_confirm(tenant_a, manager).json()
    proposals = _call("GET", f"/ifc-imports/{batch['id']}/proposals", manager).json()
    building_id = next(p["id"] for p in proposals if p["ifc_class"] == "IfcBuilding")

    first = _call("POST", f"/ifc-import-proposals/{building_id}/accept", manager)
    second = _call("POST", f"/ifc-import-proposals/{building_id}/accept", manager)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "IFC_IMPORT_PROPOSAL_ALREADY_DECIDED"


def test_rejecting_a_proposal(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _manager(tenant_a)
    batch = _upload_and_confirm(tenant_a, manager).json()
    proposals = _call("GET", f"/ifc-imports/{batch['id']}/proposals", manager).json()
    building_id = next(p["id"] for p in proposals if p["ifc_class"] == "IfcBuilding")

    response = _call(
        "POST",
        f"/ifc-import-proposals/{building_id}/reject",
        manager,
        json={"reason": "Bâtiment déjà connu, doublon"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"
    assert response.json()["rejection_reason"] == "Bâtiment déjà connu, doublon"


def test_technician_can_read_but_not_upload_or_decide(two_tenants) -> None:
    tenant_a, _ = two_tenants
    tech = _tech(tenant_a)

    upload = _call(
        "POST",
        f"/sites/{tenant_a['site_id']}/ifc-imports/upload-url",
        tech,
        json={"filename": "x.ifc"},
    )
    assert upload.status_code == 403


def test_batch_and_proposals_of_another_tenant_are_not_found(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    batch = _upload_and_confirm(tenant_a, _manager(tenant_a)).json()

    other_batch = _call("GET", f"/ifc-imports/{batch['id']}", _tech(tenant_b))
    other_proposals = _call(
        "GET", f"/ifc-imports/{batch['id']}/proposals", _tech(tenant_b)
    )

    assert other_batch.status_code == 404
    assert other_proposals.status_code == 404
