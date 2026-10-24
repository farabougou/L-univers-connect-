"""Adaptateur d'import IFC (ADR 011) : seul module autorisé à manipuler
ifcopenshell directement — ces tests ne touchent jamais la base."""

import gc

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import pytest

from app.importers.ifc_parser import MAX_FILE_SIZE_BYTES, IfcParseError, parse_ifc_bytes


def _build_model() -> bytes:
    """Site > Bâtiment > Étage > Chaufferie, avec une CTA, une pompe, et un
    mur (jamais un candidat) directement dans l'étage."""
    f = ifcopenshell.file(schema="IFC4")
    project = ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name="Projet Demo")
    site = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite", name="Site A")
    building = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuilding", name="Bâtiment A")
    storey = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuildingStorey", name="Étage 1")
    space = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSpace", name="Chaufferie")
    ahu = ifcopenshell.api.root.create_entity(f, ifc_class="IfcUnitaryEquipment", name="CTA-01")
    pump = ifcopenshell.api.root.create_entity(f, ifc_class="IfcPump", name="Pompe 1")
    wall = ifcopenshell.api.root.create_entity(f, ifc_class="IfcWall", name="Mur")

    ifcopenshell.api.aggregate.assign_object(f, relating_object=project, products=[site])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=site, products=[building])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=building, products=[storey])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=storey, products=[space])
    ifcopenshell.api.spatial.assign_container(f, relating_structure=space, products=[ahu, pump])
    ifcopenshell.api.spatial.assign_container(f, relating_structure=storey, products=[wall])

    return f.to_string().encode("utf-8"), {
        "site": site.GlobalId,
        "building": building.GlobalId,
        "storey": storey.GlobalId,
        "space": space.GlobalId,
        "ahu": ahu.GlobalId,
        "pump": pump.GlobalId,
    }


def test_extracts_the_spatial_hierarchy_with_correct_parents() -> None:
    content, ids = _build_model()
    result = parse_ifc_bytes(content)

    by_class = {s.ifc_class: s for s in result.spaces}
    assert set(by_class) == {"IfcBuilding", "IfcBuildingStorey", "IfcSpace"}
    assert by_class["IfcBuilding"].space_type == "building"
    assert by_class["IfcBuilding"].parent_ifc_global_id == ids["site"]
    assert by_class["IfcBuildingStorey"].space_type == "floor"
    assert by_class["IfcBuildingStorey"].parent_ifc_global_id == ids["building"]
    assert by_class["IfcSpace"].space_type == "room"
    assert by_class["IfcSpace"].parent_ifc_global_id == ids["storey"]


def test_only_relevant_equipment_classes_are_proposed() -> None:
    content, ids = _build_model()
    result = parse_ifc_bytes(content)

    by_class = {e.ifc_class: e for e in result.equipment}
    assert set(by_class) == {"IfcUnitaryEquipment", "IfcPump"}
    assert by_class["IfcUnitaryEquipment"].containing_space_ifc_global_id == ids["space"]
    assert by_class["IfcPump"].containing_space_ifc_global_id == ids["space"]
    # Le mur est vu (IfcElement) mais jamais proposé.
    assert result.skipped_element_count == 1


def test_ifc_zone_is_never_proposed_as_a_space() -> None:
    f = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.root.create_entity(f, ifc_class="IfcZone", name="Zone chauffage")
    result = parse_ifc_bytes(f.to_string().encode("utf-8"))
    assert result.spaces == []


def test_rejects_a_file_without_the_step_header() -> None:
    with pytest.raises(IfcParseError) as exc_info:
        parse_ifc_bytes(b"n'importe quoi")
    assert exc_info.value.code == "IFC_IMPORT_INVALID_FORMAT"


def test_rejects_a_corrupted_file_with_a_valid_header() -> None:
    with pytest.raises(IfcParseError) as exc_info:
        parse_ifc_bytes(b"ISO-10303-21;\nCECI N'EST PAS DE L'IFC VALIDE")
    assert exc_info.value.code == "IFC_IMPORT_PARSE_FAILED"
    # ifcopenshell laisse un objet interne partiellement construit après un
    # échec de lecture ; le ramasse-miettes force sa purge ici, plutôt que
    # de laisser l'avertissement de sa destruction tardive polluer un autre
    # test au hasard de l'ordre d'exécution.
    gc.collect()


def test_rejects_a_file_above_the_size_limit() -> None:
    with pytest.raises(IfcParseError) as exc_info:
        parse_ifc_bytes(b"0" * (MAX_FILE_SIZE_BYTES + 1))
    assert exc_info.value.code == "IFC_IMPORT_FILE_TOO_LARGE"
