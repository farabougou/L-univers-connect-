import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SiteOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime


class ProductModelCreate(BaseModel):
    manufacturer: str = Field(min_length=1, max_length=200)
    reference: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ProductModelOut(BaseModel):
    id: uuid.UUID
    manufacturer: str
    reference: str
    category: str
    description: str | None
    created_at: datetime


class PhysicalUnitCreate(BaseModel):
    product_model_id: uuid.UUID
    serial_number: str = Field(min_length=1, max_length=200)
    commissioned_at: datetime | None = None


class PhysicalUnitOut(BaseModel):
    id: uuid.UUID
    product_model_id: uuid.UUID
    serial_number: str
    commissioned_at: datetime | None
    created_at: datetime


class FunctionalLocationCreate(BaseModel):
    site_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    code: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["system", "equipment", "component"] | None = None
    space_id: uuid.UUID | None = None


class FunctionalLocationOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    parent_id: uuid.UUID | None
    code: str
    name: str
    kind: str | None
    space_id: uuid.UUID | None
    created_at: datetime


class SpaceCreate(BaseModel):
    site_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    space_type: str = Field(min_length=1, max_length=50)
    code: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    valid_from: AwareDatetime | None = None


class SpaceOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    parent_id: uuid.UUID | None
    space_type: str
    code: str
    name: str
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime


class SpaceClose(BaseModel):
    valid_to: AwareDatetime | None = None
    reason: str = Field(min_length=1, max_length=500)


class LocationSpaceChange(BaseModel):
    """space_id à null : la position est retirée de tout espace."""

    space_id: uuid.UUID | None
    valid_from: AwareDatetime | None = None
    reason: str | None = Field(default=None, max_length=500)


class LocationSpaceHistoryOut(BaseModel):
    id: uuid.UUID
    functional_location_id: uuid.UUID
    space_id: uuid.UUID | None
    valid_from: datetime
    recorded_at: datetime
    changed_by: str
    reason: str | None


class AssignmentCreate(BaseModel):
    physical_unit_id: uuid.UUID
    valid_from: datetime | None = None


class AssignmentOut(BaseModel):
    id: uuid.UUID
    functional_location_id: uuid.UUID
    physical_unit_id: uuid.UUID
    valid_from: datetime


class CurrentOccupantOut(BaseModel):
    functional_location_id: uuid.UUID
    physical_unit_id: uuid.UUID | None


class WorkOrderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    work_order_type: Literal["corrective", "preventive", "predictive", "inspection"] = "corrective"
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    functional_location_id: uuid.UUID | None = None
    physical_unit_id: uuid.UUID | None = None


class WorkOrderOut(BaseModel):
    id: uuid.UUID
    functional_location_id: uuid.UUID | None
    physical_unit_id: uuid.UUID | None
    title: str
    description: str | None
    work_order_type: str
    priority: str
    status: str
    created_by: str
    created_at: datetime


class WorkOrderStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "completed", "cancelled"]
    note: str | None = Field(default=None, max_length=2000)


class WorkOrderStatusHistoryOut(BaseModel):
    id: uuid.UUID
    work_order_id: uuid.UUID
    status: str
    changed_by: str
    note: str | None
    changed_at: datetime


class InterventionCreate(BaseModel):
    work_order_id: uuid.UUID | None = None
    functional_location_id: uuid.UUID | None = None
    physical_unit_id: uuid.UUID | None = None
    intervention_type: Literal["intervention", "ronde"] = "intervention"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    summary: str | None = Field(default=None, max_length=2000)
    checklist: dict = Field(default_factory=dict)


class InterventionOut(BaseModel):
    id: uuid.UUID
    work_order_id: uuid.UUID | None
    functional_location_id: uuid.UUID | None
    physical_unit_id: uuid.UUID | None
    technician: str
    intervention_type: str
    started_at: datetime
    ended_at: datetime | None
    summary: str | None
    checklist: dict
    created_at: datetime


class AlarmCreate(BaseModel):
    severity: Literal["info", "warning", "critical"]
    message: str = Field(min_length=1, max_length=500)
    functional_location_id: uuid.UUID | None = None
    physical_unit_id: uuid.UUID | None = None


class AlarmOut(BaseModel):
    id: uuid.UUID
    functional_location_id: uuid.UUID | None
    physical_unit_id: uuid.UUID | None
    severity: str
    message: str
    status: str
    raised_by: str
    raised_at: datetime


class AlarmStatusUpdate(BaseModel):
    status: Literal["open", "acknowledged", "resolved"]
    note: str | None = Field(default=None, max_length=2000)


class AlarmStatusHistoryOut(BaseModel):
    id: uuid.UUID
    alarm_id: uuid.UUID
    status: str
    changed_by: str
    note: str | None
    changed_at: datetime


class PhotoUploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)


class PhotoUploadUrlOut(BaseModel):
    upload_url: str
    object_key: str


class PhotoCreate(BaseModel):
    object_key: str = Field(min_length=1, max_length=500)
    caption: str | None = Field(default=None, max_length=500)
    taken_at: datetime | None = None


class PhotoOut(BaseModel):
    id: uuid.UUID
    intervention_id: uuid.UUID
    download_url: str
    caption: str | None
    taken_at: datetime
    uploaded_at: datetime


class GraphNodeOut(BaseModel):
    id: uuid.UUID
    node_type: str
    created_at: datetime


class RelationCreate(BaseModel):
    subject_id: uuid.UUID
    predicate: str = Field(min_length=1, max_length=50)
    object_id: uuid.UUID
    # Date avec fuseau horaire obligatoire : une date « naïve » serait
    # interprétée selon le fuseau du serveur, source d'erreurs silencieuses.
    valid_from: AwareDatetime | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class RelationEnd(BaseModel):
    valid_to: AwareDatetime | None = None
    reason: str = Field(min_length=1, max_length=500)


class RelationOut(BaseModel):
    """Une arête vue depuis un nœud : `label` est le prédicat dans le sens de
    lecture (ex. « isFedBy » vu depuis l'objet d'un « feeds »). `derived`
    signale une relation déduite de la hiérarchie, sans identifiant propre."""

    id: uuid.UUID | None
    subject_id: uuid.UUID
    subject_type: str
    predicate: str
    object_id: uuid.UUID
    object_type: str
    direction: Literal["outgoing", "incoming"]
    label: str
    derived: bool
    valid_from: datetime | None
    valid_to: datetime | None
    origin: str | None
    status: str | None
    confidence: float | None
    vocabulary_version: str | None


class ExternalIdentifierCreate(BaseModel):
    scheme: str = Field(min_length=1, max_length=50)
    external_id: str = Field(min_length=1, max_length=500)


class ExternalIdentifierOut(BaseModel):
    id: uuid.UUID
    node_id: uuid.UUID
    scheme: str
    external_id: str
    created_by: str
    created_at: datetime


class PointCreate(BaseModel):
    code: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    value_type: Literal["number", "boolean", "multistate"]
    point_class: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=30)
    states: dict[str, str] | None = None
    functional_location_id: uuid.UUID | None = None
    space_id: uuid.UUID | None = None
    expected_interval_seconds: int | None = Field(default=None, gt=0)
    min_value: float | None = None
    max_value: float | None = None
    mapping_confidence: float | None = Field(default=None, ge=0, le=1)


class PointUpdate(BaseModel):
    """Identification d'un point encore « proposed » : seuls les champs
    envoyés sont modifiés."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    value_type: Literal["number", "boolean", "multistate"] | None = None
    point_class: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=30)
    states: dict[str, str] | None = None
    functional_location_id: uuid.UUID | None = None
    space_id: uuid.UUID | None = None
    expected_interval_seconds: int | None = Field(default=None, gt=0)
    min_value: float | None = None
    max_value: float | None = None
    mapping_confidence: float | None = Field(default=None, ge=0, le=1)


class PointDecision(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class PointOut(BaseModel):
    id: uuid.UUID
    functional_location_id: uuid.UUID | None
    space_id: uuid.UUID | None
    code: str
    name: str
    point_class: str | None
    kind: str | None
    value_type: str
    unit: str | None
    states: dict[str, str] | None
    expected_interval_seconds: int | None
    min_value: float | None
    max_value: float | None
    is_writable: bool
    mapping_status: str
    mapping_confidence: float | None
    created_by: str
    created_at: datetime


class MeasurementCreate(BaseModel):
    point_id: uuid.UUID
    # Ni infini ni « NaN » : une valeur non finie n'est jamais une mesure.
    value: float = Field(allow_inf_nan=False)
    measured_at: AwareDatetime | None = None
    # « derived » et « estimated » sont réservés aux moteurs de la plateforme.
    origin: Literal["measured", "manual", "simulated"] = "measured"
    source: str = Field(default="api", min_length=1, max_length=50)


class MeasurementItem(BaseModel):
    point_id: uuid.UUID
    value: float = Field(allow_inf_nan=False)
    measured_at: AwareDatetime
    origin: Literal["measured", "manual", "simulated"] = "measured"


class MeasurementBatch(BaseModel):
    source: str = Field(min_length=1, max_length=50)
    items: list[MeasurementItem] = Field(min_length=1, max_length=1000)


class MeasurementBatchError(BaseModel):
    index: int
    point_id: uuid.UUID
    reason: str


class MeasurementBatchResult(BaseModel):
    inserted: int
    duplicates: int
    conflicts: int
    rejected: int
    errors: list[MeasurementBatchError]


class MeasurementOut(BaseModel):
    point_id: uuid.UUID
    measured_at: datetime
    value: float
    origin: str
    source: str
    quality_flags: list[str]
    received_at: datetime
