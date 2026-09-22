import uuid
from datetime import datetime

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
