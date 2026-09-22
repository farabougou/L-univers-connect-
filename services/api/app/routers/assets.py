import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.assets import assign_physical_unit, get_current_occupant
from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.schemas import (
    AssignmentCreate,
    AssignmentOut,
    CurrentOccupantOut,
    FunctionalLocationCreate,
    FunctionalLocationOut,
    PhysicalUnitCreate,
    PhysicalUnitOut,
    ProductModelCreate,
    ProductModelOut,
    SiteCreate,
    SiteOut,
)

router = APIRouter()

_MANAGE_REGISTRY_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


@router.post("/sites", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
def create_site(
    body: SiteCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> SiteOut:
    site_id = uuid.uuid4()
    connection.execute(
        text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, :name)"),
        {"id": site_id, "tenant_id": tenant_id, "name": body.name},
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="site.created",
        entity_type="site",
        entity_id=str(site_id),
        payload={"name": body.name},
    )
    row = (
        connection.execute(
            text("SELECT id, name, created_at FROM sites WHERE id = :id"), {"id": site_id}
        )
        .mappings()
        .one()
    )
    return SiteOut(**row)


@router.get("/sites", response_model=list[SiteOut])
def list_sites(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[SiteOut]:
    rows = (
        connection.execute(text("SELECT id, name, created_at FROM sites ORDER BY created_at"))
        .mappings()
        .all()
    )
    return [SiteOut(**row) for row in rows]


@router.post("/product-models", response_model=ProductModelOut, status_code=status.HTTP_201_CREATED)
def create_product_model(
    body: ProductModelCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> ProductModelOut:
    product_model_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO product_models "
            "(id, tenant_id, manufacturer, reference, category, description) "
            "VALUES (:id, :tenant_id, :manufacturer, :reference, :category, :description)"
        ),
        {
            "id": product_model_id,
            "tenant_id": tenant_id,
            "manufacturer": body.manufacturer,
            "reference": body.reference,
            "category": body.category,
            "description": body.description,
        },
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="product_model.created",
        entity_type="product_model",
        entity_id=str(product_model_id),
        payload={"manufacturer": body.manufacturer, "reference": body.reference},
    )
    row = (
        connection.execute(
            text(
                "SELECT id, manufacturer, reference, category, description, created_at "
                "FROM product_models WHERE id = :id"
            ),
            {"id": product_model_id},
        )
        .mappings()
        .one()
    )
    return ProductModelOut(**row)


@router.get("/product-models", response_model=list[ProductModelOut])
def list_product_models(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[ProductModelOut]:
    rows = (
        connection.execute(
            text(
                "SELECT id, manufacturer, reference, category, description, created_at "
                "FROM product_models ORDER BY created_at"
            )
        )
        .mappings()
        .all()
    )
    return [ProductModelOut(**row) for row in rows]


@router.post("/physical-units", response_model=PhysicalUnitOut, status_code=status.HTTP_201_CREATED)
def create_physical_unit(
    body: PhysicalUnitCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> PhysicalUnitOut:
    model_exists = connection.execute(
        text("SELECT 1 FROM product_models WHERE id = :id"), {"id": body.product_model_id}
    ).scalar()
    if not model_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="modèle catalogue introuvable"
        )

    unit_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO physical_units "
            "(id, tenant_id, product_model_id, serial_number, commissioned_at) "
            "VALUES (:id, :tenant_id, :product_model_id, :serial_number, :commissioned_at)"
        ),
        {
            "id": unit_id,
            "tenant_id": tenant_id,
            "product_model_id": body.product_model_id,
            "serial_number": body.serial_number,
            "commissioned_at": body.commissioned_at,
        },
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="physical_unit.created",
        entity_type="physical_unit",
        entity_id=str(unit_id),
        payload={"serial_number": body.serial_number},
    )
    row = (
        connection.execute(
            text(
                "SELECT id, product_model_id, serial_number, commissioned_at, created_at "
                "FROM physical_units WHERE id = :id"
            ),
            {"id": unit_id},
        )
        .mappings()
        .one()
    )
    return PhysicalUnitOut(**row)


@router.get("/physical-units", response_model=list[PhysicalUnitOut])
def list_physical_units(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[PhysicalUnitOut]:
    rows = (
        connection.execute(
            text(
                "SELECT id, product_model_id, serial_number, commissioned_at, created_at "
                "FROM physical_units ORDER BY created_at"
            )
        )
        .mappings()
        .all()
    )
    return [PhysicalUnitOut(**row) for row in rows]


@router.post(
    "/functional-locations",
    response_model=FunctionalLocationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_functional_location(
    body: FunctionalLocationCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> FunctionalLocationOut:
    site_exists = connection.execute(
        text("SELECT 1 FROM sites WHERE id = :id"), {"id": body.site_id}
    ).scalar()
    if not site_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="site introuvable")

    location_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO functional_locations (id, tenant_id, site_id, parent_id, code, name) "
            "VALUES (:id, :tenant_id, :site_id, :parent_id, :code, :name)"
        ),
        {
            "id": location_id,
            "tenant_id": tenant_id,
            "site_id": body.site_id,
            "parent_id": body.parent_id,
            "code": body.code,
            "name": body.name,
        },
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="functional_location.created",
        entity_type="functional_location",
        entity_id=str(location_id),
        payload={"code": body.code, "name": body.name},
    )
    row = (
        connection.execute(
            text(
                "SELECT id, site_id, parent_id, code, name, created_at "
                "FROM functional_locations WHERE id = :id"
            ),
            {"id": location_id},
        )
        .mappings()
        .one()
    )
    return FunctionalLocationOut(**row)


@router.get("/functional-locations", response_model=list[FunctionalLocationOut])
def list_functional_locations(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[FunctionalLocationOut]:
    rows = (
        connection.execute(
            text(
                "SELECT id, site_id, parent_id, code, name, created_at "
                "FROM functional_locations ORDER BY created_at"
            )
        )
        .mappings()
        .all()
    )
    return [FunctionalLocationOut(**row) for row in rows]


@router.post(
    "/functional-locations/{functional_location_id}/assignment",
    response_model=AssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    functional_location_id: uuid.UUID,
    body: AssignmentCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> AssignmentOut:
    location_exists = connection.execute(
        text("SELECT 1 FROM functional_locations WHERE id = :id"), {"id": functional_location_id}
    ).scalar()
    if not location_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="position fonctionnelle introuvable"
        )
    unit_exists = connection.execute(
        text("SELECT 1 FROM physical_units WHERE id = :id"), {"id": body.physical_unit_id}
    ).scalar()
    if not unit_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="exemplaire introuvable")

    assignment_id = assign_physical_unit(
        connection,
        tenant_id=tenant_id,
        functional_location_id=functional_location_id,
        physical_unit_id=body.physical_unit_id,
        valid_from=body.valid_from,
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="functional_location.assignment_changed",
        entity_type="functional_location",
        entity_id=str(functional_location_id),
        payload={"physical_unit_id": str(body.physical_unit_id)},
    )
    row = (
        connection.execute(
            text(
                "SELECT id, functional_location_id, physical_unit_id, valid_from "
                "FROM functional_location_assignments WHERE id = :id"
            ),
            {"id": assignment_id},
        )
        .mappings()
        .one()
    )
    return AssignmentOut(**row)


@router.get(
    "/functional-locations/{functional_location_id}/current-occupant",
    response_model=CurrentOccupantOut,
)
def read_current_occupant(
    functional_location_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> CurrentOccupantOut:
    location_exists = connection.execute(
        text("SELECT 1 FROM functional_locations WHERE id = :id"), {"id": functional_location_id}
    ).scalar()
    if not location_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="position fonctionnelle introuvable"
        )

    occupant = get_current_occupant(connection, functional_location_id=functional_location_id)
    return CurrentOccupantOut(
        functional_location_id=functional_location_id, physical_unit_id=occupant
    )
