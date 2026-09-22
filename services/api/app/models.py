import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Tenant(Base):
    """Un client de la plateforme (isolation au niveau base de données via RLS)."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Site(Base):
    """Première table métier d'exemple, portant tenant_id (protégée par RLS)."""

    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Journal append-only chaîné par hachage.

    Chaque entrée référence l'empreinte de la précédente (previous_hash),
    formant une chaîne : falsifier une entrée casse la chaîne de toutes
    celles qui suivent. La base de données interdit en plus toute
    modification ou suppression (voir les triggers créés dans la migration).
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProductModel(Base):
    """Référence catalogue d'un équipement, indépendante de tout exemplaire
    physique (voir ADR 001 : modèle d'identité à trois niveaux)."""

    __tablename__ = "product_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    manufacturer: Mapped[str] = mapped_column(String(200), nullable=False)
    reference: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PhysicalUnit(Base):
    """Un exemplaire physique précis d'un ProductModel, identifié par son
    numéro de série (voir ADR 001)."""

    __tablename__ = "physical_units"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    product_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_models.id"), nullable=False
    )
    serial_number: Mapped[str] = mapped_column(String(200), nullable=False)
    commissioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FunctionalLocation(Base):
    """Une position dans la hiérarchie d'une installation (ex. « sous-station
    nord, circuit 2 »), qui peut changer d'occupant sans perdre son propre
    historique (voir ADR 001, et FunctionalLocationAssignment ci-dessous)."""

    __tablename__ = "functional_locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("functional_locations.id"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FunctionalLocationAssignment(Base):
    """Historique bitemporel : quel exemplaire physique occupe quelle
    position fonctionnelle, et depuis quand (temps de validité, valid_from/
    valid_to) et depuis quand la plateforme le sait (temps de saisie,
    recorded_at). Voir ADR 001.

    Remplacer un exemplaire ne modifie jamais une ligne existante : on clôt
    l'affectation courante (valid_to) et on en insère une nouvelle. C'est
    app.assets.assign_physical_unit qui applique cette règle.
    """

    __tablename__ = "functional_location_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    functional_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("functional_locations.id"), nullable=False
    )
    physical_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("physical_units.id"), nullable=False
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkOrder(Base):
    """Un ordre de travail (GMAO) : une tâche de maintenance à planifier et
    suivre, ciblant une position fonctionnelle et/ou un exemplaire physique.

    `work_order_type` reprend la catégorisation standard du secteur CMMS/EAM
    (corrective, préventif, prédictif, inspection) : voir ADR 004 pour la
    source. Le champ `status` est une valeur courante dénormalisée,
    pratique à lire ; la vérité historique vit dans WorkOrderStatusHistory,
    jamais modifiée après coup (voir app.maintenance.change_work_order_status).
    """

    __tablename__ = "work_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    functional_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("functional_locations.id"), nullable=True
    )
    physical_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("physical_units.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    work_order_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="corrective"
    )
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkOrderStatusHistory(Base):
    """Historique des changements de statut d'un ordre de travail.

    Une ligne par transition, jamais modifiée ni supprimée après coup :
    c'est app.maintenance.change_work_order_status qui garantit cette
    discipline (même principe que FunctionalLocationAssignment)."""

    __tablename__ = "work_order_status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_orders.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Intervention(Base):
    """Un passage terrain d'un technicien, rattaché ou non à un ordre de
    travail, sur une position fonctionnelle et/ou un exemplaire physique.

    Deux styles de saisie coexistent, souvent mélangés :
    - `intervention` : réparation ou incident, décrit surtout en texte libre
      (`summary`).
    - `ronde` : contrôle de routine, décrit surtout par une liste de
      vérifications structurée (`checklist`), avec du texte libre en
      complément si besoin.
    """

    __tablename__ = "interventions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_orders.id"), nullable=True
    )
    functional_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("functional_locations.id"), nullable=True
    )
    physical_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("physical_units.id"), nullable=True
    )
    technician: Mapped[str] = mapped_column(String(200), nullable=False)
    intervention_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="intervention"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    checklist: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alarm(Base):
    """Une alarme ou un incident signalé sur une position fonctionnelle ou
    un exemplaire physique. Pour le MVP, toutes les alarmes sont levées
    manuellement (aucune détection automatique n'existe encore)."""

    __tablename__ = "alarms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    functional_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("functional_locations.id"), nullable=True
    )
    physical_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("physical_units.id"), nullable=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    raised_by: Mapped[str] = mapped_column(String(200), nullable=False)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlarmStatusHistory(Base):
    """Historique des changements de statut d'une alarme (open → acknowledged
    → resolved), jamais modifié ni supprimé après coup (voir
    app.maintenance.change_alarm_status)."""

    __tablename__ = "alarm_status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    alarm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alarms.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InterventionPhoto(Base):
    """Une photo rattachée à une intervention, stockée hors base (voir
    ADR 006). Seule la référence de stockage est conservée ici : le contenu
    de la photo n'entre jamais dans PostgreSQL ni dans Git."""

    __tablename__ = "intervention_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interventions.id"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
