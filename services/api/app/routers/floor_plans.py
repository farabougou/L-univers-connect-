"""Plans 2D (ADR 011, étape S3) : envoi, versions, lecture. Un plan référence
un espace du registre ; il ne copie jamais son nom ni ses caractéristiques.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.errors import ApiError, api_error
from app.floor_plans import (
    FloorPlanConflict,
    FloorPlanInvalid,
    get_floor_plan,
    list_floor_plans,
    list_portfolio_floor_plans,
    record_floor_plan,
)
from app.monitoring import evaluate_data_freshness
from app.plan_placements import (
    PlacementConflict,
    PlacementInvalid,
    PlacementNotFound,
    delete_placement,
    get_placement,
    list_placements,
    record_placement,
    validate_placement,
)
from app.points import get_point
from app.schemas import (
    FloorPlanCreate,
    FloorPlanOut,
    FloorPlanUploadUrlOut,
    FloorPlanUploadUrlRequest,
    PlanPlacementCreate,
    PlanPlacementLiveOut,
    PlanPlacementOut,
    PortfolioFloorPlanOut,
)
from app.spatial import get_space
from app.storage import (
    build_floor_plan_object_key,
    create_presigned_download_url,
    create_presigned_upload_url,
    floor_plan_key_belongs_to,
)
from app.telemetry import list_measurements
from app.trust import compute_trust

router = APIRouter()

_MANAGE_REGISTRY_ROLES = ("responsable_exploitation", "admin_tenant")
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict) -> str:
    return claims.get("sub") or "inconnu"


def _check_space_exists(connection: Connection, space_id: uuid.UUID) -> None:
    if get_space(connection, space_id) is None:
        raise ApiError(404, "SPACE_NOT_FOUND")


def _check_floor_plan_exists(connection: Connection, floor_plan_id: uuid.UUID) -> None:
    if get_floor_plan(connection, floor_plan_id) is None:
        raise ApiError(404, "FLOOR_PLAN_NOT_FOUND")


def _check_placement_target_exists(
    connection: Connection,
    *,
    space_id: uuid.UUID | None,
    functional_location_id: uuid.UUID | None,
    point_id: uuid.UUID | None,
) -> None:
    if space_id is not None:
        _check_space_exists(connection, space_id)
    elif functional_location_id is not None:
        exists = connection.execute(
            text("SELECT 1 FROM functional_locations WHERE id = :id"),
            {"id": functional_location_id},
        ).scalar()
        if not exists:
            raise ApiError(404, "FUNCTIONAL_LOCATION_NOT_FOUND")
    elif point_id is not None:
        exists = connection.execute(
            text("SELECT 1 FROM points WHERE id = :id"), {"id": point_id}
        ).scalar()
        if not exists:
            raise ApiError(404, "POINT_NOT_FOUND")


def _placement_to_out(row: dict) -> PlanPlacementOut:
    return PlanPlacementOut(
        id=row["id"],
        floor_plan_id=row["floor_plan_id"],
        space_id=row["space_id"],
        functional_location_id=row["functional_location_id"],
        point_id=row["point_id"],
        x_ratio=float(row["x_ratio"]),
        y_ratio=float(row["y_ratio"]),
        status=row["status"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        validated_by=row["validated_by"],
        validated_at=row["validated_at"],
    )


def _to_out(row: dict) -> FloorPlanOut:
    return FloorPlanOut(
        id=row["id"],
        space_id=row["space_id"],
        version=row["version"],
        filename=row["filename"],
        content_type=row["content_type"],
        download_url=create_presigned_download_url(row["storage_key"]),
        uploaded_by=row["uploaded_by"],
        uploaded_at=row["uploaded_at"],
    )


@router.post(
    "/spaces/{space_id}/floor-plans/upload-url",
    response_model=FloorPlanUploadUrlOut,
)
def create_floor_plan_upload_url(
    space_id: uuid.UUID,
    body: FloorPlanUploadUrlRequest,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> FloorPlanUploadUrlOut:
    """Donne une URL temporaire pour envoyer le fichier directement au
    stockage (voir ADR 006), sans jamais transmettre les identifiants
    d'accès. Le plan n'est enregistré en base qu'une fois l'envoi terminé,
    via POST .../floor-plans."""
    _check_space_exists(connection, space_id)

    object_key = build_floor_plan_object_key(
        tenant_id=tenant_id, space_id=space_id, filename=body.filename
    )
    upload_url = create_presigned_upload_url(object_key, content_type=body.content_type)
    return FloorPlanUploadUrlOut(upload_url=upload_url, object_key=object_key)


@router.post(
    "/spaces/{space_id}/floor-plans",
    response_model=FloorPlanOut,
    status_code=status.HTTP_201_CREATED,
)
def create_floor_plan(
    space_id: uuid.UUID,
    body: FloorPlanCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> FloorPlanOut:
    _check_space_exists(connection, space_id)
    if not floor_plan_key_belongs_to(body.object_key, tenant_id=tenant_id, space_id=space_id):
        raise ApiError(422, "FLOOR_PLAN_STORAGE_KEY_FOREIGN")

    try:
        floor_plan_id = record_floor_plan(
            connection,
            tenant_id=tenant_id,
            space_id=space_id,
            storage_key=body.object_key,
            content_type=body.content_type,
            filename=body.filename,
            sha256=body.sha256,
            uploaded_by=_actor(claims),
        )
    except (FloorPlanInvalid, FloorPlanConflict) as exc:
        raise api_error(exc, exc.status) from exc

    row = get_floor_plan(connection, floor_plan_id)
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="floor_plan.uploaded",
        entity_type="floor_plan",
        entity_id=str(floor_plan_id),
        payload={"space_id": str(space_id), "version": row["version"]},
    )
    return _to_out(row)


@router.get("/spaces/{space_id}/floor-plans", response_model=list[FloorPlanOut])
def list_floor_plans_route(
    space_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[FloorPlanOut]:
    _check_space_exists(connection, space_id)
    return [_to_out(row) for row in list_floor_plans(connection, space_id)]


def _portfolio_out(row: dict) -> PortfolioFloorPlanOut:
    return PortfolioFloorPlanOut(
        id=row["id"],
        space_id=row["space_id"],
        space_code=row["space_code"],
        space_name=row["space_name"],
        site_id=row["site_id"],
        site_name=row["site_name"],
        version=row["version"],
        filename=row["filename"],
        content_type=row["content_type"],
        download_url=create_presigned_download_url(row["storage_key"]),
        uploaded_by=row["uploaded_by"],
        uploaded_at=row["uploaded_at"],
        validated_placement_count=row["validated_placement_count"],
    )


@router.get("/floor-plans/portfolio", response_model=list[PortfolioFloorPlanOut])
def list_portfolio_floor_plans_route(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[PortfolioFloorPlanOut]:
    """Dernière version de chaque plan de tout le portefeuille (page
    Spatial/BIM, section 36, point 12), avec le site et l'espace visés."""
    return [_portfolio_out(row) for row in list_portfolio_floor_plans(connection)]


@router.get("/floor-plans/{floor_plan_id}", response_model=FloorPlanOut)
def get_floor_plan_route(
    floor_plan_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> FloorPlanOut:
    row = get_floor_plan(connection, floor_plan_id)
    if row is None:
        raise ApiError(404, "FLOOR_PLAN_NOT_FOUND")
    return _to_out(row)


@router.post(
    "/floor-plans/{floor_plan_id}/placements",
    response_model=PlanPlacementOut,
    status_code=status.HTTP_201_CREATED,
)
def create_placement(
    floor_plan_id: uuid.UUID,
    body: PlanPlacementCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> PlanPlacementOut:
    """Propose un placement (statut "proposed") : voir validate_placement
    pour le confirmer. Le plan référence, il ne copie jamais un nom ni une
    caractéristique de l'actif visé (ADR 011, section 3)."""
    _check_floor_plan_exists(connection, floor_plan_id)
    _check_placement_target_exists(
        connection,
        space_id=body.space_id,
        functional_location_id=body.functional_location_id,
        point_id=body.point_id,
    )

    try:
        placement_id = record_placement(
            connection,
            tenant_id=tenant_id,
            floor_plan_id=floor_plan_id,
            space_id=body.space_id,
            functional_location_id=body.functional_location_id,
            point_id=body.point_id,
            x_ratio=body.x_ratio,
            y_ratio=body.y_ratio,
            created_by=_actor(claims),
        )
    except PlacementInvalid as exc:
        raise api_error(exc, exc.status) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="plan_placement.proposed",
        entity_type="plan_placement",
        entity_id=str(placement_id),
        payload={"floor_plan_id": str(floor_plan_id)},
    )
    return _placement_to_out(get_placement(connection, placement_id))


@router.get("/floor-plans/{floor_plan_id}/placements", response_model=list[PlanPlacementOut])
def list_placements_route(
    floor_plan_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[PlanPlacementOut]:
    _check_floor_plan_exists(connection, floor_plan_id)
    return [_placement_to_out(row) for row in list_placements(connection, floor_plan_id)]


def _live_placement_out(
    connection: Connection, tenant_id: uuid.UUID, row: dict, at: datetime
) -> PlanPlacementLiveOut:
    """Enrichit un placement validé avec la dernière valeur connue du point
    visé, quand il en vise un : dernière valeur mesurée, pas une commande, et
    jamais présentée comme plus fraîche que sa date de mesure (ADR 013)."""
    point_value: float | None = None
    point_value_type: str | None = None
    point_unit: str | None = None
    point_states: dict[str, str] | None = None
    point_measured_at: datetime | None = None
    point_trust_score: int | None = None

    if row["point_id"] is not None:
        point = get_point(connection, row["point_id"])
        if point is not None:
            point_value_type = point["value_type"]
            point_unit = point["unit"]
            point_states = point["states"]
            latest = list_measurements(connection, point_id=point["id"], limit=1)
            if latest:
                point_value = latest[0]["value"]
                point_measured_at = latest[0]["measured_at"]
            trust = compute_trust(connection, point, at)
            evaluate_data_freshness(
                connection, tenant_id=tenant_id, point=point, trust=trust, at=at
            )
            point_trust_score = trust["score"]

    return PlanPlacementLiveOut(
        id=row["id"],
        floor_plan_id=row["floor_plan_id"],
        space_id=row["space_id"],
        functional_location_id=row["functional_location_id"],
        point_id=row["point_id"],
        x_ratio=float(row["x_ratio"]),
        y_ratio=float(row["y_ratio"]),
        point_value=point_value,
        point_value_type=point_value_type,
        point_unit=point_unit,
        point_states=point_states,
        point_measured_at=point_measured_at,
        point_trust_score=point_trust_score,
    )


@router.get(
    "/floor-plans/{floor_plan_id}/placements/live",
    response_model=list[PlanPlacementLiveOut],
)
def list_live_placements_route(
    floor_plan_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[PlanPlacementLiveOut]:
    """Affichage temps réel sur plan (matrice de comparaison) : seuls les
    placements validés sont montrés — un placement encore proposé n'a pas
    été confirmé comme correct, on ne l'affiche jamais comme une réalité."""
    _check_floor_plan_exists(connection, floor_plan_id)
    at = datetime.now(UTC)
    validated = [
        row for row in list_placements(connection, floor_plan_id) if row["status"] == "validated"
    ]
    return [_live_placement_out(connection, tenant_id, row, at) for row in validated]


@router.post("/placements/{placement_id}/validate", response_model=PlanPlacementOut)
def validate_placement_route(
    placement_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> PlanPlacementOut:
    try:
        validate_placement(connection, placement_id=placement_id, validated_by=_actor(claims))
    except (PlacementNotFound, PlacementConflict) as exc:
        raise api_error(exc, exc.status) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="plan_placement.validated",
        entity_type="plan_placement",
        entity_id=str(placement_id),
    )
    return _placement_to_out(get_placement(connection, placement_id))


@router.delete("/placements/{placement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_placement_route(
    placement_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_REGISTRY_ROLES))],
) -> None:
    try:
        delete_placement(connection, placement_id)
    except PlacementNotFound as exc:
        raise api_error(exc, exc.status) from exc

    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="plan_placement.deleted",
        entity_type="plan_placement",
        entity_id=str(placement_id),
    )
