import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.schemas import MeasurementCreate, MeasurementOut
from app.telemetry import record_measurement

router = APIRouter()

_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict[str, Any]) -> str:
    return claims.get("sub") or "inconnu"


def _check_targets_exist(
    connection: Connection,
    *,
    functional_location_id: uuid.UUID | None,
    physical_unit_id: uuid.UUID | None,
) -> None:
    if functional_location_id is not None:
        exists = connection.execute(
            text("SELECT 1 FROM functional_locations WHERE id = :id"),
            {"id": functional_location_id},
        ).scalar()
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="position fonctionnelle introuvable"
            )
    if physical_unit_id is not None:
        exists = connection.execute(
            text("SELECT 1 FROM physical_units WHERE id = :id"), {"id": physical_unit_id}
        ).scalar()
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="exemplaire introuvable"
            )


@router.post("/measurements", response_model=MeasurementOut, status_code=status.HTTP_201_CREATED)
def create_measurement(
    body: MeasurementCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> MeasurementOut:
    """Point d'entrée de télémétrie pour le squelette de bout en bout (M2).

    Aucun connecteur réel n'existe encore : ce point sert pour l'instant à
    un point simulé (voir ADR 004). Il ne fait qu'enregistrer une valeur
    déjà mesurée, jamais commander un équipement (règle non négociable 1).
    """
    _check_targets_exist(
        connection,
        functional_location_id=body.functional_location_id,
        physical_unit_id=body.physical_unit_id,
    )

    measurement_id = record_measurement(
        connection,
        tenant_id=tenant_id,
        metric=body.metric,
        value=body.value,
        unit=body.unit,
        source=body.source,
        measured_at=body.measured_at or datetime.now(UTC),
        functional_location_id=body.functional_location_id,
        physical_unit_id=body.physical_unit_id,
    )
    return _read_measurement(connection, measurement_id)


@router.get("/measurements", response_model=list[MeasurementOut])
def list_measurements(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
    functional_location_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[MeasurementOut]:
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="limit doit être entre 1 et 1000"
        )

    query = (
        "SELECT id, functional_location_id, physical_unit_id, metric, value, unit, "
        "source, measured_at, created_at FROM measurements"
    )
    params: dict[str, Any] = {"limit": limit}
    if functional_location_id is not None:
        query += " WHERE functional_location_id = :functional_location_id"
        params["functional_location_id"] = functional_location_id
    query += " ORDER BY measured_at DESC LIMIT :limit"

    rows = connection.execute(text(query), params).mappings().all()
    return [MeasurementOut(**row) for row in rows]


def _read_measurement(connection: Connection, measurement_id: uuid.UUID) -> MeasurementOut:
    row = (
        connection.execute(
            text(
                "SELECT id, functional_location_id, physical_unit_id, metric, value, unit, "
                "source, measured_at, created_at FROM measurements WHERE id = :id"
            ),
            {"id": measurement_id},
        )
        .mappings()
        .one()
    )
    return MeasurementOut(**row)
