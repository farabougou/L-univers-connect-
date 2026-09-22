import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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


class FunctionalLocationOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    parent_id: uuid.UUID | None
    code: str
    name: str
    created_at: datetime


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
