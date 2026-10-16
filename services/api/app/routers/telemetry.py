import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.engine import Connection

from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.errors import ApiError, api_error
from app.i18n import negotiate_locale, render
from app.points import get_point
from app.schemas import (
    MeasurementBatch,
    MeasurementBatchResult,
    MeasurementCreate,
    MeasurementOut,
)
from app.telemetry import (
    MeasurementConflict,
    MeasurementRejected,
    ingest_measurements,
    list_measurements,
    read_measurement,
    record_measurement,
)

router = APIRouter()

# Tant qu'aucune identité machine n'existe (M3, ADR 012 §2.10), l'ingestion
# passe par ces rôles humains : acceptable pour le simulateur, jamais pour
# un vrai appareil.
_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


# L'ingestion de mesures n'écrit pas dans le journal d'audit : ce n'est pas
# une action sensible, et son volume saturerait une chaîne conçue pour les
# actions humaines (ADR 012, risque 9). La traçabilité est portée par
# `source`, `origin` et `received_at` sur chaque mesure.


@router.post("/measurements", response_model=MeasurementOut, status_code=status.HTTP_201_CREATED)
def create_measurement(
    body: MeasurementCreate,
    response: Response,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> MeasurementOut:
    """Un relevé. 201 s'il est nouveau, 200 s'il était déjà reçu à l'identique
    (renvoi après coupure), 409 si une autre valeur existe à cet instant."""
    point = get_point(connection, body.point_id)
    if point is None:
        raise ApiError(404, "POINT_NOT_FOUND")

    received_at = datetime.now(UTC)
    measured_at = body.measured_at or received_at
    try:
        outcome = record_measurement(
            connection,
            tenant_id=tenant_id,
            point=point,
            value=body.value,
            measured_at=measured_at,
            origin=body.origin,
            source=body.source,
            received_at=received_at,
        )
    except MeasurementRejected as exc:
        raise api_error(exc, 400) from exc
    except MeasurementConflict as exc:
        raise api_error(exc, 409) from exc

    if outcome == "duplicate":
        response.status_code = status.HTTP_200_OK
    return MeasurementOut(**read_measurement(connection, body.point_id, measured_at))


@router.post("/measurements/batch", response_model=MeasurementBatchResult)
def create_measurements_batch(
    body: MeasurementBatch,
    request: Request,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> MeasurementBatchResult:
    """Envoi groupé (jusqu'à 1000 relevés), rejouable sans risque de doublon."""
    summary = ingest_measurements(
        connection,
        tenant_id=tenant_id,
        items=[item.model_dump() for item in body.items],
        source=body.source,
        received_at=datetime.now(UTC),
    )
    # Chaque ligne refusée porte son code (qui fait foi) et sa raison traduite.
    locale = negotiate_locale(request.headers.get("accept-language"))
    for error in summary["errors"]:
        error["reason"] = render(error["code"], error["params"], locale)
    return MeasurementBatchResult(**summary)


@router.get("/measurements", response_model=list[MeasurementOut])
def list_measurements_route(
    point_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    since: datetime | None = None,
    limit: int = 100,
) -> list[MeasurementOut]:
    if limit < 1 or limit > 1000:
        raise ApiError(400, "QUERY_LIMIT_OUT_OF_RANGE", minimum=1, maximum=1000)
    if since is not None and since.tzinfo is None:
        raise ApiError(400, "QUERY_SINCE_TIMEZONE_REQUIRED")
    if get_point(connection, point_id) is None:
        raise ApiError(404, "POINT_NOT_FOUND")
    rows = list_measurements(connection, point_id=point_id, since=since, limit=limit)
    return [MeasurementOut(**row) for row in rows]
