"""Energy Intelligence Core (M5) : contexte météo, calcul de performance
normalisée et comparaison. Voir app/energy/__init__.py pour la frontière
avec les futures couches réglementaires (OPERAT, BACS, ESG), non traitées
ici.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError
from sqlalchemy.engine import Connection

from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.energy.aggregation import EnergyDataInsufficient
from app.energy.comparison import compare_results
from app.energy.normalization import (
    EnergyBaselineNotFound,
    compute_normalized_performance,
    get_normalized_result,
    list_normalized_results,
)
from app.energy.weather import (
    list_weather_observations,
    record_weather_observation,
)
from app.errors import ApiError, api_error

router = APIRouter(prefix="/energy", tags=["energy"])

_FIELD_ROLES = ("technicien", "responsable_exploitation", "admin_tenant")


def _actor(claims: dict) -> str:
    return claims.get("sub") or "inconnu"


class WeatherObservationCreate(BaseModel):
    site_id: uuid.UUID
    observed_date: date
    mean_temperature_celsius: float = Field(ge=-60, le=60)
    station_ref: str | None = Field(default=None, max_length=200)


class WeatherObservationOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    site_id: uuid.UUID
    observed_date: date
    mean_temperature_celsius: float
    source: str
    station_ref: str | None
    created_by: str
    created_at: datetime


class NormalizedResultCompute(BaseModel):
    baseline_config_version_id: uuid.UUID
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.period_start > self.period_end:
            raise PydanticCustomError(
                "energy_period_reversed", "period_start must not be after period_end"
            )
        return self


class NormalizedResultOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    functional_location_id: uuid.UUID
    point_id: uuid.UUID
    baseline_config_version_id: uuid.UUID
    period_start: date
    period_end: date
    method: str
    method_version: str
    parameters: dict
    raw_consumption: float
    raw_consumption_unit: str
    measurement_count: int
    data_completeness: float | None
    quality_flags: dict
    degree_days: float | None
    degree_day_base_temperature_celsius: float
    degree_day_kind: str
    weather_source: str | None
    weather_days_missing: int | None
    normalization_status: str
    normalized_consumption: float | None
    evidence: dict
    computed_at: datetime
    computed_by: str
    created_at: datetime


class ComparisonOut(BaseModel):
    comparable: bool
    reason: str | None = None
    reference_result_id: uuid.UUID
    analyzed_result_id: uuid.UUID
    reference_normalized_consumption: float | None = None
    analyzed_normalized_consumption: float | None = None
    absolute_deviation: float | None = None
    percent_deviation: float | None = None
    reduced: bool | None = None


def _require_result(connection: Connection, result_id: uuid.UUID) -> dict:
    result = get_normalized_result(connection, result_id)
    if result is None:
        raise ApiError(404, "ENERGY_NORMALIZED_RESULT_NOT_FOUND")
    return result


@router.post(
    "/weather-observations",
    response_model=WeatherObservationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_weather_observation_route(
    body: WeatherObservationCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> WeatherObservationOut:
    """Une observation par site et par jour : une nouvelle saisie pour un
    jour déjà renseigné corrige la précédente (voir app/energy/weather.py)."""
    observation_id = record_weather_observation(
        connection,
        tenant_id=tenant_id,
        site_id=body.site_id,
        observed_date=body.observed_date,
        mean_temperature_celsius=body.mean_temperature_celsius,
        created_by=_actor(claims),
        station_ref=body.station_ref,
    )
    observations = list_weather_observations(
        connection,
        site_id=body.site_id,
        period_start=body.observed_date,
        period_end=body.observed_date,
    )
    return WeatherObservationOut(**next(o for o in observations if o["id"] == observation_id))


@router.get("/weather-observations", response_model=list[WeatherObservationOut])
def list_weather_observations_route(
    site_id: uuid.UUID,
    period_start: date,
    period_end: date,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[WeatherObservationOut]:
    observations = list_weather_observations(
        connection, site_id=site_id, period_start=period_start, period_end=period_end
    )
    return [WeatherObservationOut(**observation) for observation in observations]


@router.post(
    "/normalized-results",
    response_model=NormalizedResultOut,
    status_code=status.HTTP_201_CREATED,
)
def compute_normalized_result_route(
    body: NormalizedResultCompute,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> NormalizedResultOut:
    """Calcule et persiste un résultat de performance normalisée pour la
    période demandée, selon la référence énergétique désignée (voir
    app/energy/normalization.py). Rien n'est écrasé : un nouvel appel pour
    la même période crée une nouvelle ligne, jamais une mise à jour."""
    try:
        result = compute_normalized_performance(
            connection,
            tenant_id=tenant_id,
            baseline_config_version_id=body.baseline_config_version_id,
            period_start=body.period_start,
            period_end=body.period_end,
            computed_by=_actor(claims),
            at=datetime.now(UTC),
        )
    except EnergyBaselineNotFound as exc:
        raise api_error(exc, exc.status) from exc
    except EnergyDataInsufficient as exc:
        raise api_error(exc, exc.status) from exc
    return NormalizedResultOut(**result)


@router.get("/normalized-results", response_model=list[NormalizedResultOut])
def list_normalized_results_route(
    functional_location_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> list[NormalizedResultOut]:
    results = list_normalized_results(connection, functional_location_id=functional_location_id)
    return [NormalizedResultOut(**result) for result in results]


@router.get("/normalized-results/{result_id}", response_model=NormalizedResultOut)
def get_normalized_result_route(
    result_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> NormalizedResultOut:
    return NormalizedResultOut(**_require_result(connection, result_id))


@router.get("/comparison", response_model=ComparisonOut)
def compare_normalized_results_route(
    reference_result_id: uuid.UUID,
    analyzed_result_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_FIELD_ROLES))],
) -> ComparisonOut:
    """Mise en regard pure de deux résultats déjà calculés — aucun nouveau
    calcul, aucune écriture (voir app/energy/comparison.py)."""
    reference = _require_result(connection, reference_result_id)
    analyzed = _require_result(connection, analyzed_result_id)
    return ComparisonOut(**compare_results(reference, analyzed))
