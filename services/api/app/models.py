import uuid
from datetime import datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Tenant(Base):
    """Un client de la plateforme (isolation au niveau base de données via RLS)."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _graph_node_fk(table: str) -> ForeignKeyConstraint:
    """Chaque ligne d'une table « nœud » a son entrée dans graph_nodes, avec le
    même tenant (créée par un déclencheur en base, voir la migration 706eca882498)."""
    return ForeignKeyConstraint(
        ["tenant_id", "id"],
        ["graph_nodes.tenant_id", "graph_nodes.id"],
        name=f"fk_{table}_graph_node",
    )


class GraphNode(Base):
    """Registre d'identité commun (ADR 012, section 2.1) : tout ce qui peut
    être relié, placé, scanné ou diagnostiqué y a une ligne, avec le même UUID
    que dans sa propre table."""

    __tablename__ = "graph_nodes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_graph_nodes_tenant_id_id"),
        CheckConstraint(
            "node_type IN ('site', 'space', 'functional_location', 'physical_unit', 'point')",
            name="ck_graph_nodes_node_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Relation(Base):
    """Relation typée entre deux nœuds du même tenant (ADR 012, section 2.2).

    Bitemporelle (valid_from/valid_to + recorded_at), jamais effacée ni
    réécrite : un déclencheur en base n'autorise que la clôture et la décision
    sur une proposition. Le vocabulaire des prédicats vit dans
    app.graph_vocabulary."""

    __tablename__ = "relations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["graph_nodes.tenant_id", "graph_nodes.id"],
            name="fk_relations_subject",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "object_id"],
            ["graph_nodes.tenant_id", "graph_nodes.id"],
            name="fk_relations_object",
        ),
        CheckConstraint("subject_id <> object_id", name="ck_relations_not_self"),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_relations_valid_period"
        ),
        CheckConstraint(
            "origin IN ('manual', 'import', 'discovery', 'inferred')", name="ck_relations_origin"
        ),
        CheckConstraint(
            "status IN ('proposed', 'validated', 'rejected')", name="ck_relations_status"
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_relations_confidence",
        ),
        Index("ix_relations_subject_id", "subject_id"),
        Index("ix_relations_object_id", "object_id"),
        Index(
            "uq_relations_open",
            "tenant_id",
            "subject_id",
            "predicate",
            "object_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL AND status <> 'rejected'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    predicate: Mapped[str] = mapped_column(String(50), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    origin: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="validated")
    vocabulary_version: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)


class Site(Base):
    """Première table métier d'exemple, portant tenant_id (protégée par RLS)."""

    __tablename__ = "sites"
    __table_args__ = (
        _graph_node_fk("sites"),
        UniqueConstraint("tenant_id", "id", name="uq_sites_tenant_id_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Fuseau IANA du site (« Europe/Paris ») ; vide pour les sites créés avant
    # ADR 013 tant qu'il n'a pas été renseigné : aucun fuseau n'est deviné.
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Journal append-only chaîné par hachage.

    Chaque entrée référence l'empreinte de la précédente (previous_hash),
    formant une chaîne : falsifier une entrée casse la chaîne de toutes
    celles qui suivent. La base de données interdit en plus toute
    modification ou suppression (voir les triggers créés dans la migration).
    """

    __tablename__ = "audit_log"
    __table_args__ = (Index("audit_log_tenant_seq_idx", "tenant_id", "seq"),)

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
    # Type universel (app.equipment_vocabulary) et appellation du fabricant,
    # conservée telle quelle (ADR 013, étape L5).
    equipment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    manufacturer_designation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PhysicalUnit(Base):
    """Un exemplaire physique précis d'un ProductModel, identifié par son
    numéro de série (voir ADR 001)."""

    __tablename__ = "physical_units"
    __table_args__ = (
        _graph_node_fk("physical_units"),
        Index("physical_units_tenant_serial_idx", "tenant_id", "serial_number", unique=True),
        Index(
            "uq_physical_units_tenant_asset_code",
            "tenant_id",
            "asset_code",
            unique=True,
            postgresql_where=text("asset_code IS NOT NULL"),
        ),
        UniqueConstraint("tenant_id", "id", name="uq_physical_units_tenant_id_id"),
        CheckConstraint(
            "lifecycle_state IN ('planned', 'ordered', 'in_stock', 'installed', 'commissioned', "
            "'in_service', 'out_of_service', 'removed', 'decommissioned', 'disposed')",
            name="ck_physical_units_lifecycle_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    product_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_models.id"), nullable=False
    )
    serial_number: Mapped[str] = mapped_column(String(200), nullable=False)
    # Code d'inventaire propre au client (unique chez lui s'il est renseigné).
    asset_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    commissioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # État courant (app.lifecycle) ; la vérité historique vit dans
    # PhysicalUnitLifecycleEvent, jamais modifiée.
    lifecycle_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="in_stock"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FunctionalLocation(Base):
    """Une position dans la hiérarchie d'une installation (ex. « sous-station
    nord, circuit 2 »), qui peut changer d'occupant sans perdre son propre
    historique (voir ADR 001, et FunctionalLocationAssignment ci-dessous)."""

    __tablename__ = "functional_locations"
    __table_args__ = (
        _graph_node_fk("functional_locations"),
        UniqueConstraint("tenant_id", "id", name="uq_functional_locations_tenant_id_id"),
        # Une position ne peut être placée que dans un espace du même site.
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "space_id"],
            ["spaces.tenant_id", "spaces.site_id", "spaces.id"],
            name="fk_functional_locations_space",
        ),
        Index("ix_functional_locations_space_id", "space_id"),
    )

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
    # Emplacement courant (ADR 011) ; la vérité historique vit dans
    # FunctionalLocationSpaceHistory, jamais modifiée.
    space_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # system / equipment / component (app.spatial_vocabulary).
    kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Space(Base):
    """Un espace physique : bâtiment, étage, pièce, zone… (ADR 011).

    Arbre séparé de l'arbre technique des positions fonctionnelles. Le parent
    est toujours dans le même tenant et le même site (clé étrangère composée).
    La structure n'est jamais réécrite : un espace rénové est clos (valid_to)
    et remplacé par un nouveau (déclencheur en base)."""

    __tablename__ = "spaces"
    __table_args__ = (
        _graph_node_fk("spaces"),
        ForeignKeyConstraint(
            ["tenant_id", "site_id"], ["sites.tenant_id", "sites.id"], name="fk_spaces_site"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "site_id", "parent_id"],
            ["spaces.tenant_id", "spaces.site_id", "spaces.id"],
            name="fk_spaces_parent",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_spaces_tenant_id_id"),
        UniqueConstraint("tenant_id", "site_id", "id", name="uq_spaces_tenant_site_id"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_spaces_not_own_parent"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_spaces_valid_period"),
        Index("ix_spaces_parent_id", "parent_id"),
        Index(
            "uq_spaces_open_code",
            "tenant_id",
            "site_id",
            "code",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    space_type: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FunctionalLocationSpaceHistory(Base):
    """Historique des emplacements d'une position fonctionnelle : une ligne
    par changement (space_id NULL = retirée de tout espace), jamais modifiée.
    valid_from = date réelle du déplacement, recorded_at = date de saisie."""

    __tablename__ = "functional_location_space_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "functional_location_id"],
            ["functional_locations.tenant_id", "functional_locations.id"],
            name="fk_fl_space_history_location",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "space_id"],
            ["spaces.tenant_id", "spaces.id"],
            name="fk_fl_space_history_space",
        ),
        Index("ix_fl_space_history_location_valid_from", "functional_location_id", "valid_from"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    functional_location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    space_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


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
    __table_args__ = (
        # Un seul exemplaire à la fois dans une position (voir la migration
        # 01847c2561a1).
        Index(
            "functional_location_one_open_assignment",
            "functional_location_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

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
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_interventions_tenant_id_id"),
        UniqueConstraint("tenant_id", "client_ref", name="uq_interventions_tenant_client_ref"),
    )

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
    # Référence fournie par le client pour rejouer un envoi sans doublon
    # (identifiant local de la file hors ligne du téléphone).
    client_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Alarm(Base):
    """Une alarme ou un incident signalé sur une position fonctionnelle ou
    un exemplaire physique. Pour le MVP, toutes les alarmes sont levées
    manuellement (aucune détection automatique n'existe encore)."""

    __tablename__ = "alarms"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'major', 'critical')", name="ck_alarms_severity"
        ),
        CheckConstraint(
            "condition_state IN ('active', 'cleared')", name="ck_alarms_condition_state"
        ),
        CheckConstraint(
            "ack_state IN ('unacknowledged', 'acknowledged')", name="ck_alarms_ack_state"
        ),
        CheckConstraint(
            "handling_status IN ('open', 'in_progress', 'closed', 'false_positive')",
            name="ck_alarms_handling_status",
        ),
    )

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
    # Trois axes séparés (ADR 013, 4.2) : condition, acquittement, traitement.
    condition_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    ack_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="unacknowledged"
    )
    handling_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    raised_by: Mapped[str] = mapped_column(String(200), nullable=False)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlarmStatusHistory(Base):
    """Historique des changements de statut d'une alarme (open → acknowledged
    → resolved), jamais modifié ni supprimé après coup (voir
    app.maintenance.change_alarm_status)."""

    __tablename__ = "alarm_status_history"
    __table_args__ = (
        CheckConstraint(
            "field IS NULL OR field IN "
            "('condition_state', 'ack_state', 'handling_status', 'certainty')",
            name="ck_alarm_status_history_field",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    alarm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alarms.id"), nullable=False
    )
    # Champ modifié (vide pour les lignes antérieures à ADR 013 : ancien statut).
    field: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InterventionPhoto(Base):
    """Une photo rattachée à une intervention, stockée hors base (voir
    ADR 006). Seule la référence de stockage est conservée ici : le contenu
    de la photo n'entre jamais dans PostgreSQL ni dans Git."""

    __tablename__ = "intervention_photos"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "client_ref", name="uq_intervention_photos_tenant_client_ref"
        ),
    )

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
    client_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Point(Base):
    """Un point de télémétrie : capteur, consigne, état, alarme, compteur…
    (ADR 012, section 2.7), nœud du graphe.

    Rattaché à une position fonctionnelle et/ou à un espace. Un point découvert
    commence « proposed » : il n'est considéré fiable qu'une fois validé
    (mise en service), et sa description est alors figée (déclencheur en
    base). `is_writable` est forcé à faux par une contrainte : règle non
    négociable 1 inscrite dans la base."""

    __tablename__ = "points"
    __table_args__ = (
        _graph_node_fk("points"),
        ForeignKeyConstraint(
            ["tenant_id", "functional_location_id"],
            ["functional_locations.tenant_id", "functional_locations.id"],
            name="fk_points_functional_location",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "space_id"], ["spaces.tenant_id", "spaces.id"], name="fk_points_space"
        ),
        UniqueConstraint("tenant_id", "id", name="uq_points_tenant_id_id"),
        UniqueConstraint("tenant_id", "code", name="uq_points_tenant_code"),
        CheckConstraint("is_writable = false", name="ck_points_read_only_c0"),
        CheckConstraint(
            "value_type IN ('number', 'boolean', 'multistate')", name="ck_points_value_type"
        ),
        CheckConstraint(
            "mapping_status IN ('proposed', 'validated', 'rejected')",
            name="ck_points_mapping_status",
        ),
        CheckConstraint(
            "mapping_confidence IS NULL OR (mapping_confidence >= 0 AND mapping_confidence <= 1)",
            name="ck_points_mapping_confidence",
        ),
        CheckConstraint(
            "expected_interval_seconds IS NULL OR expected_interval_seconds > 0",
            name="ck_points_expected_interval",
        ),
        CheckConstraint(
            "min_value IS NULL OR max_value IS NULL OR min_value < max_value",
            name="ck_points_range",
        ),
        Index("ix_points_functional_location_id", "functional_location_id"),
        Index("ix_points_space_id", "space_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    functional_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    space_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    code: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    point_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    states: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expected_interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_writable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    mapping_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="proposed"
    )
    mapping_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExternalIdentifier(Base):
    """Identifiant d'un nœud dans un autre système (code client, GlobalId
    IFC, objet BACnet…) : une seule table de correspondance pour tous les
    imports et connecteurs, jamais de modèle d'actifs parallèle (ADR 011)."""

    __tablename__ = "external_identifiers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "node_id"],
            ["graph_nodes.tenant_id", "graph_nodes.id"],
            name="fk_external_identifiers_node",
        ),
        UniqueConstraint(
            "tenant_id", "scheme", "external_id", name="uq_external_identifiers_scheme_value"
        ),
        Index("ix_external_identifiers_node_id", "node_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scheme: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Measurement(Base):
    """Une valeur relevée sur un point, en lecture seule (ADR 012, 2.7-2.8).

    Clé primaire (point, date du relevé) : un relevé renvoyé deux fois (reprise
    après coupure Edge) n'est jamais dupliqué, et la clé est compatible avec
    TimescaleDB (M3). `received_at` = date de réception par la plateforme ;
    `origin` distingue une mesure réelle d'une valeur simulée ou estimée ;
    `quality_flags` garde les anomalies détectées à la réception. Une mesure
    n'est jamais modifiée après coup."""

    __tablename__ = "measurements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "point_id"],
            ["points.tenant_id", "points.id"],
            name="fk_measurements_point",
        ),
        CheckConstraint(
            "origin IN ('measured', 'manual', 'derived', 'estimated', 'simulated')",
            name="ck_measurements_origin",
        ),
    )

    point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    quality_flags: Mapped[list[str]] = mapped_column(
        ARRAY(String(30)), nullable=False, server_default=text("'{}'")
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConfigVersion(Base):
    """Une version d'une configuration qui influence le fonctionnement (règle
    d'alarme, attente, mapping…), ADR 012 section 2.11.

    Jamais réécrite ni supprimée : corriger ou revenir en arrière crée une
    nouvelle version (raison obligatoire). Une seule version active par
    élément configuré (index partiel unique)."""

    __tablename__ = "config_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_config_versions_tenant_id_id"),
        UniqueConstraint(
            "tenant_id", "config_type", "subject_key", "version", name="uq_config_versions_version"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "parent_version_id"],
            ["config_versions.tenant_id", "config_versions.id"],
            name="fk_config_versions_parent",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'retired')",
            name="ck_config_versions_status",
        ),
        CheckConstraint("version >= 1", name="ck_config_versions_version"),
        Index(
            "uq_config_versions_one_active",
            "tenant_id",
            "config_type",
            "subject_key",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    config_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class DesiredState(Base):
    """État souhaité d'un point (ADR 012, section 2.4). En lecture seule, la
    seule origine permise est une attente déclarée par un humain (« éclairage
    éteint de 20 h à 7 h »). Fenêtre quotidienne facultative, toujours avec
    son fuseau horaire. Jamais réécrit : on le clôt et on en crée un autre."""

    __tablename__ = "desired_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "point_id"],
            ["points.tenant_id", "points.id"],
            name="fk_desired_states_point",
        ),
        CheckConstraint("source IN ('declared_expectation')", name="ck_desired_states_source"),
        CheckConstraint(
            "(daily_start IS NULL) = (daily_end IS NULL)", name="ck_desired_states_window"
        ),
        CheckConstraint(
            "daily_start IS NULL OR timezone IS NOT NULL", name="ck_desired_states_timezone"
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_desired_states_period"
        ),
        Index("ix_desired_states_point_id", "point_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    daily_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    daily_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="declared_expectation"
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Finding(Base):
    """Un constat analytique (ADR 012, section 2.15) : qualité de donnée, mise
    en service, anomalie, défaut ou prédiction, avec la règle (et sa version)
    qui l'a produit et ses preuves. Jamais une action : il peut lever une
    alarme ou créer un ordre de travail, pas commander un équipement."""

    __tablename__ = "findings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "subject_node_id"],
            ["graph_nodes.tenant_id", "graph_nodes.id"],
            name="fk_findings_subject",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "point_id"], ["points.tenant_id", "points.id"], name="fk_findings_point"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rule_config_version_id"],
            ["config_versions.tenant_id", "config_versions.id"],
            name="fk_findings_rule",
        ),
        ForeignKeyConstraint(["alarm_id"], ["alarms.id"], name="fk_findings_alarm"),
        ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], name="fk_findings_work_order"),
        UniqueConstraint("tenant_id", "id", name="uq_findings_tenant_id_id"),
        CheckConstraint(
            "kind IN ('data_quality', 'commissioning', 'anomaly', 'fault', 'prediction')",
            name="ck_findings_kind",
        ),
        CheckConstraint(
            "method IN ('deterministic_rule', 'engineering_rule', 'statistical', "
            "'physical_model', 'peer_comparison', 'ml')",
            name="ck_findings_method",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'major', 'critical')", name="ck_findings_severity"
        ),
        CheckConstraint(
            "condition_state IN ('active', 'cleared')", name="ck_findings_condition_state"
        ),
        CheckConstraint(
            "ack_state IN ('unacknowledged', 'acknowledged')", name="ck_findings_ack_state"
        ),
        CheckConstraint(
            "handling_status IN ('open', 'in_progress', 'closed', 'false_positive')",
            name="ck_findings_handling_status",
        ),
        CheckConstraint(
            "certainty IN ('detected', 'confirmed', 'probable_cause', 'hypothesis', "
            "'prediction', 'recommendation', 'simulation_result', 'unavailable')",
            name="ck_findings_certainty",
        ),
        CheckConstraint(
            "certainty <> 'confirmed' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by NOT LIKE 'systeme:%')",
            name="ck_findings_confirmation",
        ),
        CheckConstraint(
            "NOT (kind = 'prediction' AND certainty = 'confirmed')",
            name="ck_findings_prediction_never_confirmed",
        ),
        CheckConstraint(
            "reason_code NOT LIKE 'RULE\\_%' OR title IS NOT NULL", name="ck_findings_rule_title"
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_findings_confidence",
        ),
        CheckConstraint("occurrence_count >= 1", name="ck_findings_occurrences"),
        Index(
            "uq_findings_one_open",
            "tenant_id",
            "dedup_key",
            unique=True,
            postgresql_where=text("handling_status IN ('open', 'in_progress')"),
        ),
        Index("ix_findings_subject_node_id", "subject_node_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    subject_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    rule_config_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    dedup_key: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    # Code stable + paramètres : la phrase est produite à l'affichage (ADR 013).
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_params: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # Titre écrit par l'auteur d'une règle (contenu du client) ; vide pour les
    # constats produits par le système.
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    certainty: Mapped[str] = mapped_column(String(30), nullable=False)
    action_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    condition_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    ack_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="unacknowledged"
    )
    handling_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    alarm_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FindingStatusHistory(Base):
    """Historique des statuts d'un constat, jamais modifié (même principe que
    les alarmes et ordres de travail)."""

    __tablename__ = "finding_status_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "finding_id"],
            ["findings.tenant_id", "findings.id"],
            name="fk_finding_status_history_finding",
        ),
        CheckConstraint(
            "field IS NULL OR field IN "
            "('condition_state', 'ack_state', 'handling_status', 'certainty')",
            name="ck_finding_status_history_field",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Champ modifié (vide pour les lignes antérieures à ADR 013 : ancien statut).
    field: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PhysicalUnitLifecycleEvent(Base):
    """Historique du cycle de vie d'un exemplaire (ADR 012, 2.9), une ligne
    par changement d'état, jamais modifiée."""

    __tablename__ = "physical_unit_lifecycle_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "physical_unit_id"],
            ["physical_units.tenant_id", "physical_units.id"],
            name="fk_lifecycle_events_unit",
        ),
        Index("ix_lifecycle_events_unit_occurred", "physical_unit_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    physical_unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_state: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class AssetTag(Base):
    """Étiquette QR / NFC collée sur un actif : un code aléatoire opaque qui
    renvoie vers un nœud du graphe (app.tags). Révocable, jamais réattribuée."""

    __tablename__ = "asset_tags"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "node_id"],
            ["graph_nodes.tenant_id", "graph_nodes.id"],
            name="fk_asset_tags_node",
        ),
        UniqueConstraint("code", name="uq_asset_tags_code"),
        CheckConstraint("tag_type IN ('qr', 'nfc', 'barcode')", name="ck_asset_tags_type"),
        CheckConstraint("status IN ('active', 'revoked')", name="ck_asset_tags_status"),
        CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)", name="ck_asset_tags_revocation"
        ),
        Index("ix_asset_tags_node_id", "node_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    tag_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class InterventionClosure(Base):
    """Clôture structurée d'une intervention (codes fermés, app.closure_vocabulary).
    Une preuve : jamais modifiée ni supprimée (déclencheurs en base)."""

    __tablename__ = "intervention_closures"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "intervention_id"],
            ["interventions.tenant_id", "interventions.id"],
            name="fk_intervention_closures_intervention",
        ),
        UniqueConstraint("intervention_id", name="uq_intervention_closures_intervention"),
        CheckConstraint(
            "labor_minutes >= 0 AND labor_minutes <= 10080", name="ck_closures_labor_minutes"
        ),
        CheckConstraint(
            "verification_result IN ('ok', 'partial', 'failed')", name="ck_closures_verification"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    intervention_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    symptom_code: Mapped[str] = mapped_column(String(50), nullable=False)
    cause_code: Mapped[str] = mapped_column(String(50), nullable=False)
    action_code: Mapped[str] = mapped_column(String(50), nullable=False)
    parts: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    labor_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    verification_result: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    closed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NodeProperty(Base):
    """Propriété technique datée d'un nœud (app.properties) : fluide, charge,
    puissances… Bitemporelle, jamais réécrite : une nouvelle valeur clôt
    l'ancienne."""

    __tablename__ = "node_properties"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "node_id"],
            ["graph_nodes.tenant_id", "graph_nodes.id"],
            name="fk_node_properties_node",
        ),
        CheckConstraint(
            "(value_number IS NULL) <> (value_text IS NULL)", name="ck_node_properties_one_value"
        ),
        CheckConstraint(
            "source IN ('nameplate', 'document', 'measurement', 'manual')",
            name="ck_node_properties_source",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_node_properties_period"
        ),
        Index(
            "uq_node_properties_open",
            "tenant_id",
            "node_id",
            "property_key",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_key: Mapped[str] = mapped_column(String(50), nullable=False)
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
