import uuid
from datetime import datetime, time
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    # Fuseau IANA, obligatoire : les heures du site s'affichent dans ce fuseau.
    timezone: str = Field(min_length=1, max_length=64)


class SiteTimezoneUpdate(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)


class SiteOut(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str | None
    created_at: datetime
    archived_at: datetime | None


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=50)


class ProviderUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=50)


class ProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    created_by: str
    created_at: datetime


class ProductModelCreate(BaseModel):
    manufacturer: str = Field(min_length=1, max_length=200)
    reference: str = Field(min_length=1, max_length=200)
    # Code du vocabulaire universel (GET /equipment-types).
    equipment_type: str = Field(min_length=1, max_length=40)
    # Appellation du fabricant, conservée telle quelle.
    manufacturer_designation: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)


class ProductModelOut(BaseModel):
    id: uuid.UUID
    manufacturer: str
    reference: str
    equipment_type: str
    manufacturer_designation: str | None
    description: str | None
    created_at: datetime


class PhysicalUnitCreate(BaseModel):
    product_model_id: uuid.UUID
    serial_number: str = Field(min_length=1, max_length=200)
    asset_code: str | None = Field(default=None, min_length=1, max_length=100)
    commissioned_at: datetime | None = None


class AssetCodeUpdate(BaseModel):
    asset_code: str = Field(min_length=1, max_length=100)


class PhysicalUnitOut(BaseModel):
    id: uuid.UUID
    product_model_id: uuid.UUID
    serial_number: str
    asset_code: str | None
    commissioned_at: datetime | None
    lifecycle_state: str
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
    archived_at: datetime | None


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


class FindingWorkOrderCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    work_order_type: Literal["corrective", "preventive", "predictive", "inspection"] = "corrective"
    priority: Literal["low", "medium", "high", "urgent"] | None = None


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


class TimelineEntryOut(BaseModel):
    kind: Literal["intervention", "work_order", "alarm", "finding", "lifecycle"]
    at: datetime
    reference_id: uuid.UUID
    title: str | None
    field: str | None
    status: str | None
    changed_by: str | None
    note: str | None


class PortfolioTimelineEntryOut(BaseModel):
    """Comme `TimelineEntryOut`, pour le bloc « Activité récente » du Global
    Command Center (un portefeuille entier, pas un seul équipement) : sans
    `lifecycle` (propre à un exemplaire physique, pas au portefeuille), avec
    `functional_location_id` en plus pour le lien de chaque ligne."""

    kind: Literal["intervention", "work_order", "alarm", "finding"]
    at: datetime
    functional_location_id: uuid.UUID | None
    reference_id: uuid.UUID
    title: str | None
    field: str | None
    status: str | None
    changed_by: str | None
    note: str | None


# Référence fournie par le client pour rejouer un envoi sans doublon :
# identifiant local de la file hors ligne, sans espace ni accent.
CLIENT_REF_PATTERN = r"^[A-Za-z0-9._:-]{8,100}$"


class InterventionCreate(BaseModel):
    work_order_id: uuid.UUID | None = None
    functional_location_id: uuid.UUID | None = None
    physical_unit_id: uuid.UUID | None = None
    intervention_type: Literal["intervention", "ronde"] = "intervention"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    summary: str | None = Field(default=None, max_length=2000)
    checklist: dict = Field(default_factory=dict)
    client_ref: str | None = Field(default=None, pattern=CLIENT_REF_PATTERN)

    @model_validator(mode="after")
    def _replayable_needs_its_date(self) -> "InterventionCreate":
        # Un envoi rejouable porte sa propre date avec son fuseau : sinon le
        # serveur prendrait l'heure du renvoi et le prendrait pour un autre.
        if self.client_ref is not None and (
            self.started_at is None or self.started_at.tzinfo is None
        ):
            # Le type d'erreur sert de code stable dans la réponse (champ « reason »).
            raise PydanticCustomError(
                "client_ref_requires_aware_started_at",
                "client_ref requires started_at with its time zone",
            )
        return self


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
    client_ref: str | None = None


Severity = Literal["info", "warning", "major", "critical"]
HandlingStatus = Literal["open", "in_progress", "closed", "false_positive"]


class AlarmCreate(BaseModel):
    severity: Severity
    message: str = Field(min_length=1, max_length=500)
    functional_location_id: uuid.UUID | None = None
    physical_unit_id: uuid.UUID | None = None


class AlarmOut(BaseModel):
    id: uuid.UUID
    functional_location_id: uuid.UUID | None
    physical_unit_id: uuid.UUID | None
    severity: str
    message: str
    condition_state: str
    ack_state: str
    handling_status: str
    raised_by: str
    raised_at: datetime


class SignalNote(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class SignalHandlingUpdate(BaseModel):
    handling_status: HandlingStatus
    note: str | None = Field(default=None, max_length=2000)


class FindingConfirmation(BaseModel):
    # Une confirmation dit ce qui a été vérifié : la note est obligatoire.
    note: str = Field(min_length=1, max_length=2000)


class SignalHistoryOut(BaseModel):
    id: uuid.UUID
    signal_id: uuid.UUID
    # Champ modifié ; vide pour les lignes antérieures à l'ADR 013 (ancien
    # statut unique, conservé tel quel).
    field: str | None
    value: str
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
    client_ref: str | None = Field(default=None, pattern=CLIENT_REF_PATTERN)


class PhotoOut(BaseModel):
    id: uuid.UUID
    intervention_id: uuid.UUID
    download_url: str
    caption: str | None
    taken_at: datetime
    uploaded_at: datetime


class FloorPlanUploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)


class FloorPlanUploadUrlOut(BaseModel):
    upload_url: str
    object_key: str


class FloorPlanCreate(BaseModel):
    object_key: str = Field(min_length=1, max_length=500)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class FloorPlanOut(BaseModel):
    id: uuid.UUID
    space_id: uuid.UUID
    version: int
    filename: str
    content_type: str
    download_url: str
    uploaded_by: str
    uploaded_at: datetime


class DocumentUploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)


class DocumentUploadUrlOut(BaseModel):
    upload_url: str
    object_key: str


class DocumentCreate(BaseModel):
    category: str = Field(min_length=1, max_length=30)
    object_key: str = Field(min_length=1, max_length=500)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class DocumentOut(BaseModel):
    id: uuid.UUID
    functional_location_id: uuid.UUID
    category: str
    filename: str
    content_type: str
    download_url: str
    uploaded_by: str
    uploaded_at: datetime


class PortfolioDocumentOut(BaseModel):
    id: uuid.UUID
    functional_location_id: uuid.UUID
    functional_location_code: str
    functional_location_name: str
    category: str
    filename: str
    content_type: str
    download_url: str
    uploaded_by: str
    uploaded_at: datetime


class IfcImportUploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)


class IfcImportUploadUrlOut(BaseModel):
    upload_url: str
    object_key: str


class IfcImportBatchCreate(BaseModel):
    object_key: str = Field(min_length=1, max_length=1000)
    filename: str = Field(min_length=1, max_length=255)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class IfcImportBatchOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    filename: str
    sha256: str
    status: Literal["processing", "ready", "failed"]
    error_code: str | None
    ifc_schema: str | None
    space_proposal_count: int | None
    equipment_proposal_count: int | None
    skipped_element_count: int | None
    uploaded_by: str
    uploaded_at: datetime


class IfcImportProposalOut(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    proposal_type: Literal["space", "equipment"]
    ifc_class: str
    ifc_global_id: str
    name: str
    space_type: str | None
    parent_ifc_global_id: str | None
    containing_space_ifc_global_id: str | None
    status: Literal["proposed", "accepted", "rejected"]
    created_node_id: uuid.UUID | None
    decided_by: str | None
    decided_at: datetime | None
    rejection_reason: str | None
    created_at: datetime


class IfcImportProposalReject(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class BacnetDiscoveryScanRequest(BaseModel):
    equipment_id: uuid.UUID
    address: str = Field(min_length=1, max_length=255)
    timeout: float = Field(default=3.0, ge=0.5, le=15.0)


class BacnetDiscoveryBatchOut(BaseModel):
    id: uuid.UUID
    equipment_id: uuid.UUID
    address: str
    timeout_seconds: float
    device_instance: int | None
    status: Literal["processing", "ready", "failed"]
    error_code: str | None
    object_count: int | None
    proposal_count: int | None
    duplicate_count: int | None
    scanned_by: str
    scanned_at: datetime


class BacnetDiscoveryProposalOut(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    object_type: str
    object_instance: int
    object_name: str | None
    description: str | None
    bacnet_units: str | None
    present_value_preview: str | None
    value_type: Literal["number", "boolean", "multistate"]
    states: dict[str, str] | None
    proposed_point_class: str | None
    proposed_unit: str | None
    confidence: float | None
    reason_code: str
    reason_message: str
    status: Literal["proposed", "accepted", "rejected", "duplicate"]
    created_point_id: uuid.UUID | None
    decided_by: str | None
    decided_at: datetime | None
    rejection_reason: str | None
    created_at: datetime


class BacnetDiscoveryProposalAccept(BaseModel):
    point_class: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=20)
    code: str | None = Field(default=None, max_length=200)
    name: str | None = Field(default=None, max_length=200)


class BacnetDiscoveryProposalReject(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class BacnetDiscoveryPendingOut(BaseModel):
    """Ce que l'agent Edge a besoin de savoir pour exécuter un scan demandé
    par une personne : jamais plus (pas le statut, l'agent ne fait qu'un
    scan par lot reçu)."""

    id: uuid.UUID
    equipment_id: uuid.UUID
    address: str
    timeout_seconds: float


class BacnetDiscoveryObjectIn(BaseModel):
    """Un objet BACnet tel que découvert par l'agent Edge (mêmes champs que
    `app.connectors.bacnet.BacnetObjectInfo`, pour reconstruire directement
    la structure côté domaine sans renommage)."""

    object_type: str = Field(min_length=1, max_length=50)
    object_instance: int = Field(ge=0)
    value_type: Literal["number", "boolean", "multistate"]
    object_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    units: str | None = Field(default=None, max_length=100)
    present_value_preview: str | None = Field(default=None, max_length=200)
    states: dict[str, str] | None = None


class BacnetDiscoveryResultSubmit(BaseModel):
    device_instance: int = Field(ge=0)
    objects: list[BacnetDiscoveryObjectIn] = Field(default_factory=list)


class BacnetDiscoveryFailureSubmit(BaseModel):
    error_code: Literal["BACNET_DEVICE_UNREACHABLE", "BACNET_INVENTORY_FAILED"]


class PlanPlacementCreate(BaseModel):
    space_id: uuid.UUID | None = None
    functional_location_id: uuid.UUID | None = None
    point_id: uuid.UUID | None = None
    x_ratio: float = Field(ge=0, le=1)
    y_ratio: float = Field(ge=0, le=1)


class PlanPlacementOut(BaseModel):
    id: uuid.UUID
    floor_plan_id: uuid.UUID
    space_id: uuid.UUID | None
    functional_location_id: uuid.UUID | None
    point_id: uuid.UUID | None
    x_ratio: float
    y_ratio: float
    status: str
    created_by: str
    created_at: datetime
    validated_by: str | None
    validated_at: datetime | None


class PlanPlacementLiveOut(BaseModel):
    id: uuid.UUID
    floor_plan_id: uuid.UUID
    space_id: uuid.UUID | None
    functional_location_id: uuid.UUID | None
    point_id: uuid.UUID | None
    x_ratio: float
    y_ratio: float
    point_value: float | None
    point_value_type: str | None
    point_unit: str | None
    point_states: dict[str, str] | None
    point_measured_at: datetime | None
    point_trust_score: int | None


class GraphNodeOut(BaseModel):
    id: uuid.UUID
    node_type: str
    created_at: datetime


class ImpactedNodeOut(BaseModel):
    node_id: uuid.UUID
    node_type: str
    open_finding_count: int


class ImpactReportOut(BaseModel):
    node_id: uuid.UUID
    open_finding_count: int
    impacted: list[ImpactedNodeOut]


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


class PortfolioTelemetryEntryOut(BaseModel):
    """Un point du portefeuille avec sa dernière valeur, pour la page
    Telemetry (directive UI/dashboard, section 36 point 9). `value` et
    `measured_at` sont `None` sans relevé exploitable ; `stale` reste `None`
    sans intervalle attendu déclaré sur le point (actualité invérifiable,
    jamais devinée)."""

    point_id: uuid.UUID
    functional_location_id: uuid.UUID | None
    code: str
    name: str
    point_class: str | None
    unit: str | None
    value: float | None
    measured_at: datetime | None
    stale: bool | None


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


class EdgeMeasurementBatch(BaseModel):
    """Sans `source` : pour un appareil authentifié, la source est son
    identité vérifiée (voir app/routers/devices.py), jamais une valeur
    annoncée dans le corps de la requête."""

    items: list[MeasurementItem] = Field(min_length=1, max_length=1000)


class MeasurementBatchError(BaseModel):
    index: int
    point_id: uuid.UUID
    code: str
    params: dict
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


class ConfigVersionCreate(BaseModel):
    config_type: str = Field(min_length=1, max_length=50)
    subject_key: str = Field(min_length=1, max_length=200)
    content: dict
    reason: str = Field(min_length=1, max_length=500)


class ConfigReason(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ConfigVersionOut(BaseModel):
    id: uuid.UUID
    config_type: str
    subject_key: str
    version: int
    content: dict
    content_hash: str
    schema_version: str
    status: str
    author: str
    reason: str
    parent_version_id: uuid.UUID | None
    created_at: datetime
    activated_at: datetime | None
    activated_by: str | None


class ConfigDiffOut(BaseModel):
    from_version: int
    to_version: int
    added: dict
    removed: dict
    changed: dict


class RuleSimulationBreachOut(BaseModel):
    measured_at: datetime
    value: float
    evidence: dict[str, Any]


class RuleSimulationOut(BaseModel):
    sample_size: int
    breach_count: int
    breaches: list[RuleSimulationBreachOut]


class DesiredStateCreate(BaseModel):
    value: float = Field(allow_inf_nan=False)
    valid_from: AwareDatetime | None = None
    daily_start: time | None = None
    daily_end: time | None = None
    timezone: str | None = Field(default=None, max_length=64)
    reason: str = Field(min_length=1, max_length=500)


class DesiredStateEnd(BaseModel):
    valid_to: AwareDatetime | None = None


class DesiredStateOut(BaseModel):
    id: uuid.UUID
    point_id: uuid.UUID
    value: float
    daily_start: time | None
    daily_end: time | None
    timezone: str | None
    source: str
    valid_from: datetime
    valid_to: datetime | None
    reason: str
    created_by: str
    recorded_at: datetime


class FindingOut(BaseModel):
    id: uuid.UUID
    subject_node_id: uuid.UUID
    point_id: uuid.UUID | None
    kind: str
    method: str
    rule_config_version_id: uuid.UUID | None
    dedup_key: str
    severity: str
    reason_code: str
    reason_params: dict
    # Traduits à l'affichage (sauf titre et action écrits par l'auteur d'une règle).
    title: str
    recommended_action: str | None
    confidence: float | None
    certainty: str
    action_required: bool
    confirmed_by: str | None
    confirmed_at: datetime | None
    evidence: dict
    condition_state: str
    ack_state: str
    handling_status: str
    first_seen_at: datetime
    last_seen_at: datetime
    occurrence_count: int
    alarm_id: uuid.UUID | None
    work_order_id: uuid.UUID | None
    created_at: datetime


class TrustOut(BaseModel):
    point_id: uuid.UUID
    evaluated_at: datetime
    algorithm: str
    score: int
    components: dict
    reasons: list[str]


class LifecycleChange(BaseModel):
    to_state: Literal[
        "planned",
        "ordered",
        "in_stock",
        "commissioned",
        "in_service",
        "out_of_service",
        "decommissioned",
        "disposed",
    ]
    occurred_at: AwareDatetime | None = None
    note: str | None = Field(default=None, max_length=2000)


class LifecycleEventOut(BaseModel):
    id: uuid.UUID
    physical_unit_id: uuid.UUID
    from_state: str | None
    to_state: str
    occurred_at: datetime
    recorded_at: datetime
    changed_by: str
    note: str | None


class ClosurePart(BaseModel):
    reference: str = Field(min_length=1, max_length=100)
    quantity: float = Field(gt=0, allow_inf_nan=False)
    description: str | None = Field(default=None, max_length=200)


class ClosureCreate(BaseModel):
    symptom_code: str = Field(min_length=1, max_length=50)
    cause_code: str = Field(min_length=1, max_length=50)
    action_code: str = Field(min_length=1, max_length=50)
    parts: list[ClosurePart] = Field(default_factory=list, max_length=50)
    labor_minutes: int = Field(ge=0, le=10080)
    verification_result: Literal["ok", "partial", "failed"]
    note: str | None = Field(default=None, max_length=2000)


class ClosureOut(BaseModel):
    id: uuid.UUID
    intervention_id: uuid.UUID
    symptom_code: str
    cause_code: str
    action_code: str
    parts: list[dict]
    labor_minutes: int
    verification_result: str
    note: str | None
    closed_by: str
    closed_at: datetime


class TagCreate(BaseModel):
    tag_type: Literal["qr", "nfc", "barcode"] = "qr"


class TagRevoke(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class TagOut(BaseModel):
    id: uuid.UUID
    node_id: uuid.UUID
    code: str
    payload: str
    tag_type: str
    status: str
    created_by: str
    created_at: datetime
    revoked_at: datetime | None
    revoked_by: str | None
    revoke_reason: str | None


class PropertySet(BaseModel):
    key: str = Field(min_length=1, max_length=50)
    value: float | str
    unit: str | None = Field(default=None, max_length=30)
    source: Literal["nameplate", "document", "measurement", "manual"]
    valid_from: AwareDatetime | None = None
    reason: str = Field(min_length=1, max_length=500)


class PropertyOut(BaseModel):
    id: uuid.UUID
    node_id: uuid.UUID
    property_key: str
    value: float | str
    unit: str | None
    source: str
    valid_from: datetime
    valid_to: datetime | None
    recorded_at: datetime
    reason: str
    created_by: str


class EquipmentStatusSource(BaseModel):
    point_id: uuid.UUID
    point_class: str
    value: float
    measured_at: datetime


class EquipmentStatusOut(BaseModel):
    """Deux axes distincts (ADR 013, 4.5). `current` est faux quand l'état
    n'est que le dernier connu (hors ligne, ou actualité invérifiable)."""

    operational_status: str
    communication_status: str
    current: bool
    as_of: datetime | None
    reason: str | None
    evaluated_at: datetime
    sources: list[EquipmentStatusSource]


class PortfolioEquipmentStatusOut(BaseModel):
    """Version allégée de `EquipmentStatusOut` pour le bloc « Santé des
    actifs » du Global Command Center (un par équipement du portefeuille) :
    sans `sources`, jamais utile à un résumé, uniquement à l'analyse d'un
    équipement précis (fiche équipement, `GET
    /functional-locations/{id}/status`)."""

    functional_location_id: uuid.UUID
    operational_status: str
    communication_status: str
    current: bool
    as_of: datetime | None
    reason: str | None
