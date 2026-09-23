import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.assets import assign_physical_unit, get_current_occupant
from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.equipment_status import compute_equipment_status
from app.equipment_vocabulary import (
    EQUIPMENT_TYPES,
    EQUIPMENT_VOCABULARY_VERSION,
    suggest_equipment_type,
)
from app.errors import ApiError, api_error
from app.i18n import load_catalog, negotiate_locale
from app.lifecycle import (
    LifecycleError,
    LifecycleNotFound,
    change_state,
    current_state,
    lifecycle_history,
    record_event,
)
from app.schemas import (
    AssetCodeUpdate,
    AssignmentCreate,
    AssignmentOut,
    CurrentOccupantOut,
    EquipmentStatusOut,
    FunctionalLocationCreate,
    FunctionalLocationOut,
    LifecycleChange,
    LifecycleEventOut,
    PhysicalUnitCreate,
    PhysicalUnitOut,
    ProductModelCreate,
    ProductModelOut,
    SiteCreate,
    SiteOut,
    SiteTimezoneUpdate,
)
from app.spatial import (
    SpatialConflict,
    SpatialNotFound,
    check_space_for_location,
    record_location_space,
)
from app.timezones import check_timezone

router = APIRouter()

_MANAGE_REGISTRY_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


def _read_site(connection: Connection, site_id: uuid.UUID) -> SiteOut:
    row = (
        connection.execute(
            text("SELECT id, name, timezone, created_at FROM sites WHERE id = :id"),
            {"id": site_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "SITE_NOT_FOUND")
    return SiteOut(**row)


@router.post("/sites", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
def create_site(
    body: SiteCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> SiteOut:
    check_timezone(body.timezone)
    site_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO sites (id, tenant_id, name, timezone) "
            "VALUES (:id, :tenant_id, :name, :timezone)"
        ),
        {"id": site_id, "tenant_id": tenant_id, "name": body.name, "timezone": body.timezone},
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="site.created",
        entity_type="site",
        entity_id=str(site_id),
        payload={"name": body.name, "timezone": body.timezone},
    )
    return _read_site(connection, site_id)


@router.put("/sites/{site_id}/timezone", response_model=SiteOut)
def set_site_timezone(
    site_id: uuid.UUID,
    body: SiteTimezoneUpdate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> SiteOut:
    """Renseigne ou corrige le fuseau d'un site ; l'ancienne valeur reste
    dans le journal d'audit."""
    check_timezone(body.timezone)
    previous = _read_site(connection, site_id).timezone
    connection.execute(
        text("UPDATE sites SET timezone = :timezone WHERE id = :id"),
        {"timezone": body.timezone, "id": site_id},
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="site.timezone_set",
        entity_type="site",
        entity_id=str(site_id),
        payload={"previous": previous, "timezone": body.timezone},
    )
    return _read_site(connection, site_id)


@router.get("/sites", response_model=list[SiteOut])
def list_sites(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[SiteOut]:
    rows = (
        connection.execute(
            text("SELECT id, name, timezone, created_at FROM sites ORDER BY created_at")
        )
        .mappings()
        .all()
    )
    return [SiteOut(**row) for row in rows]


_MODEL_COLUMNS = (
    "id, manufacturer, reference, equipment_type, manufacturer_designation, description, "
    "created_at"
)
_UNIT_COLUMNS = (
    "id, product_model_id, serial_number, asset_code, commissioned_at, lifecycle_state, "
    "created_at"
)


@router.get("/equipment-types")
def list_equipment_types(
    request: Request,
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> dict[str, Any]:
    """Types universels d'équipement, libellés dans la langue demandée."""
    labels = load_catalog(negotiate_locale(request.headers.get("accept-language")), "ui")[
        "equipment_type"
    ]
    return {
        "version": EQUIPMENT_VOCABULARY_VERSION,
        "types": [
            {"code": code, "label": labels[code], "brick": equipment.brick}
            for code, equipment in EQUIPMENT_TYPES.items()
        ],
    }


@router.get("/equipment-types/suggestion")
def suggest_equipment_type_route(
    text_to_normalize: Annotated[str, Query(alias="text", min_length=1, max_length=200)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> dict[str, str | None]:
    """Type proposé pour l'appellation d'un fabricant ; `null` si aucune
    correspondance certaine. Une personne confirme toujours le choix."""
    return {"equipment_type": suggest_equipment_type(text_to_normalize)}


@router.post("/product-models", response_model=ProductModelOut, status_code=status.HTTP_201_CREATED)
def create_product_model(
    body: ProductModelCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> ProductModelOut:
    if body.equipment_type not in EQUIPMENT_TYPES:
        raise ApiError(422, "EQUIPMENT_TYPE_UNKNOWN", equipment_type=body.equipment_type)
    product_model_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO product_models (id, tenant_id, manufacturer, reference, equipment_type, "
            "manufacturer_designation, description) VALUES (:id, :tenant_id, :manufacturer, "
            ":reference, :equipment_type, :manufacturer_designation, :description)"
        ),
        {
            "id": product_model_id,
            "tenant_id": tenant_id,
            "manufacturer": body.manufacturer,
            "reference": body.reference,
            "equipment_type": body.equipment_type,
            "manufacturer_designation": body.manufacturer_designation,
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
        payload={
            "manufacturer": body.manufacturer,
            "reference": body.reference,
            "equipment_type": body.equipment_type,
        },
    )
    row = (
        connection.execute(
            text(f"SELECT {_MODEL_COLUMNS} FROM product_models WHERE id = :id"),
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
        connection.execute(text(f"SELECT {_MODEL_COLUMNS} FROM product_models ORDER BY created_at"))
        .mappings()
        .all()
    )
    return [ProductModelOut(**row) for row in rows]


def _check_asset_code_free(connection: Connection, asset_code: str | None) -> None:
    if asset_code is None:
        return
    taken = connection.execute(
        text("SELECT 1 FROM physical_units WHERE asset_code = :code"), {"code": asset_code}
    ).scalar()
    if taken:
        raise ApiError(409, "ASSET_CODE_ALREADY_USED", asset_code=asset_code)


def _read_unit(connection: Connection, unit_id: uuid.UUID) -> PhysicalUnitOut:
    row = (
        connection.execute(
            text(f"SELECT {_UNIT_COLUMNS} FROM physical_units WHERE id = :id"), {"id": unit_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "PHYSICAL_UNIT_NOT_FOUND")
    return PhysicalUnitOut(**row)


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
        raise ApiError(404, "PRODUCT_MODEL_NOT_FOUND")
    _check_asset_code_free(connection, body.asset_code)

    unit_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO physical_units "
            "(id, tenant_id, product_model_id, serial_number, asset_code, commissioned_at) "
            "VALUES (:id, :tenant_id, :product_model_id, :serial_number, :asset_code, "
            ":commissioned_at)"
        ),
        {
            "id": unit_id,
            "tenant_id": tenant_id,
            "product_model_id": body.product_model_id,
            "serial_number": body.serial_number,
            "asset_code": body.asset_code,
            "commissioned_at": body.commissioned_at,
        },
    )
    record_event(
        connection,
        tenant_id=tenant_id,
        physical_unit_id=unit_id,
        from_state=None,
        to_state="in_stock",
        occurred_at=datetime.now(UTC),
        changed_by=_actor(claims),
        note="création dans le registre",
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="physical_unit.created",
        entity_type="physical_unit",
        entity_id=str(unit_id),
        payload={"serial_number": body.serial_number, "asset_code": body.asset_code},
    )
    return _read_unit(connection, unit_id)


@router.put("/physical-units/{physical_unit_id}/asset-code", response_model=PhysicalUnitOut)
def set_asset_code(
    physical_unit_id: uuid.UUID,
    body: AssetCodeUpdate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> PhysicalUnitOut:
    """Renseigne ou corrige le code d'inventaire ; l'ancienne valeur reste dans
    le journal d'audit."""
    previous = _read_unit(connection, physical_unit_id).asset_code
    if previous == body.asset_code:
        return _read_unit(connection, physical_unit_id)
    _check_asset_code_free(connection, body.asset_code)
    connection.execute(
        text("UPDATE physical_units SET asset_code = :code WHERE id = :id"),
        {"code": body.asset_code, "id": physical_unit_id},
    )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="physical_unit.asset_code_set",
        entity_type="physical_unit",
        entity_id=str(physical_unit_id),
        payload={"previous": previous, "asset_code": body.asset_code},
    )
    return _read_unit(connection, physical_unit_id)


@router.get("/physical-units", response_model=list[PhysicalUnitOut])
def list_physical_units(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[PhysicalUnitOut]:
    rows = (
        connection.execute(text(f"SELECT {_UNIT_COLUMNS} FROM physical_units ORDER BY created_at"))
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
        raise ApiError(404, "SITE_NOT_FOUND")
    if body.parent_id is not None:
        # Lecture sous RLS : un parent d'un autre tenant est introuvable. La clé
        # étrangère seule ne suffirait pas, elle ignore l'isolation des tenants.
        parent_site = connection.execute(
            text("SELECT site_id FROM functional_locations WHERE id = :id"),
            {"id": body.parent_id},
        ).scalar()
        if parent_site is None:
            raise ApiError(404, "PARENT_FUNCTIONAL_LOCATION_NOT_FOUND")
        if parent_site != body.site_id:
            raise ApiError(409, "PARENT_FUNCTIONAL_LOCATION_OTHER_SITE")
    if body.space_id is not None:
        try:
            check_space_for_location(connection, space_id=body.space_id, site_id=body.site_id)
        except SpatialNotFound as exc:
            raise api_error(exc, 404) from exc
        except SpatialConflict as exc:
            raise api_error(exc, 409) from exc

    location_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO functional_locations (id, tenant_id, site_id, parent_id, code, name, "
            "kind) VALUES (:id, :tenant_id, :site_id, :parent_id, :code, :name, :kind)"
        ),
        {
            "id": location_id,
            "tenant_id": tenant_id,
            "site_id": body.site_id,
            "parent_id": body.parent_id,
            "code": body.code,
            "name": body.name,
            "kind": body.kind,
        },
    )
    if body.space_id is not None:
        record_location_space(
            connection,
            tenant_id=tenant_id,
            functional_location_id=location_id,
            space_id=body.space_id,
            valid_from=datetime.now(UTC),
            changed_by=_actor(claims),
            reason="emplacement initial",
        )
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="functional_location.created",
        entity_type="functional_location",
        entity_id=str(location_id),
        payload={
            "code": body.code,
            "name": body.name,
            "kind": body.kind,
            "space_id": str(body.space_id) if body.space_id else None,
        },
    )
    row = (
        connection.execute(
            text(
                "SELECT id, site_id, parent_id, code, name, kind, space_id, created_at "
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
                "SELECT id, site_id, parent_id, code, name, kind, space_id, created_at "
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
        raise ApiError(404, "FUNCTIONAL_LOCATION_NOT_FOUND")
    unit_exists = connection.execute(
        text("SELECT 1 FROM physical_units WHERE id = :id"), {"id": body.physical_unit_id}
    ).scalar()
    if not unit_exists:
        raise ApiError(404, "PHYSICAL_UNIT_NOT_FOUND")

    try:
        assignment_id = assign_physical_unit(
            connection,
            tenant_id=tenant_id,
            functional_location_id=functional_location_id,
            physical_unit_id=body.physical_unit_id,
            valid_from=body.valid_from,
            changed_by=_actor(claims),
        )
    except LifecycleError as exc:
        raise api_error(exc, 409) from exc
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
        raise ApiError(404, "FUNCTIONAL_LOCATION_NOT_FOUND")

    occupant = get_current_occupant(connection, functional_location_id=functional_location_id)
    return CurrentOccupantOut(
        functional_location_id=functional_location_id, physical_unit_id=occupant
    )


@router.post(
    "/physical-units/{physical_unit_id}/lifecycle",
    response_model=list[LifecycleEventOut],
)
def change_lifecycle_state(
    physical_unit_id: uuid.UUID,
    body: LifecycleChange,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> list[LifecycleEventOut]:
    """Change l'état de cycle de vie (hors installation et dépose, qui passent
    par l'affectation) et renvoie tout l'historique."""
    try:
        change_state(
            connection,
            tenant_id=tenant_id,
            physical_unit_id=physical_unit_id,
            to_state=body.to_state,
            occurred_at=body.occurred_at or datetime.now(UTC),
            changed_by=_actor(claims),
            note=body.note,
        )
    except LifecycleNotFound as exc:
        raise api_error(exc, 404) from exc
    except LifecycleError as exc:
        raise api_error(exc, 409) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="physical_unit.lifecycle_changed",
        entity_type="physical_unit",
        entity_id=str(physical_unit_id),
        payload={"to_state": body.to_state, "note": body.note},
    )
    return [LifecycleEventOut(**row) for row in lifecycle_history(connection, physical_unit_id)]


@router.get(
    "/physical-units/{physical_unit_id}/lifecycle",
    response_model=list[LifecycleEventOut],
)
def read_lifecycle(
    physical_unit_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[LifecycleEventOut]:
    try:
        current_state(connection, physical_unit_id)
    except LifecycleNotFound as exc:
        raise api_error(exc, 404) from exc
    return [LifecycleEventOut(**row) for row in lifecycle_history(connection, physical_unit_id)]


@router.get(
    "/functional-locations/{functional_location_id}/status", response_model=EquipmentStatusOut
)
def read_equipment_status(
    functional_location_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> EquipmentStatusOut:
    """État de fonctionnement et de communication, calculé à l'instant de la
    demande à partir des points d'état validés."""
    exists = connection.execute(
        text("SELECT 1 FROM functional_locations WHERE id = :id"), {"id": functional_location_id}
    ).scalar()
    if not exists:
        raise ApiError(404, "FUNCTIONAL_LOCATION_NOT_FOUND")
    return EquipmentStatusOut(
        **compute_equipment_status(connection, functional_location_id, datetime.now(UTC))
    )
