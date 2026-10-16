"""add bacnet discovery expand

BACnet V1 (directive de Mohamed, 27/09/2026) : la découverte automatique
d'objets BACnet produit des propositions, jamais des points directement
créés — même principe que l'import IFC (b202e7f21592) et pour la même
raison : une correspondance sémantique incertaine doit rester
vérifiable/corrigeable par une personne avant de devenir un vrai point du
Universal Asset Model.

bacnet_discovery_batches trace un scan (adresse, équipement visé, état,
compteurs). bacnet_discovery_proposals porte chaque objet BACnet candidat,
avec son adressage natif (object_type, object_instance) pour la provenance,
la classe de point proposée par app.connectors.bacnet_semantics (nullable :
« needs_review » quand aucune correspondance fiable n'a été trouvée), sa
confiance, et une fois acceptée, l'identifiant du point réellement créé
(par app.points.create_point, le même chemin que la saisie manuelle).

Revision ID: d0252a39b344
Revises: 1017a1520913
Create Date: 2026-09-27 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd0252a39b344'
down_revision: Union[str, None] = '1017a1520913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bacnet_discovery_batches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('equipment_id', sa.UUID(), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('device_instance', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='processing', nullable=False),
        sa.Column('error_code', sa.String(length=100), nullable=True),
        sa.Column('object_count', sa.Integer(), nullable=True),
        sa.Column('proposal_count', sa.Integer(), nullable=True),
        sa.Column('duplicate_count', sa.Integer(), nullable=True),
        sa.Column('scanned_by', sa.String(length=200), nullable=False),
        sa.Column(
            'scanned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'equipment_id'],
            ['functional_locations.tenant_id', 'functional_locations.id'],
            name='fk_bacnet_discovery_batches_equipment',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'id', name='uq_bacnet_discovery_batches_tenant_id_id'),
        sa.CheckConstraint(
            "status IN ('processing', 'ready', 'failed')",
            name='ck_bacnet_discovery_batches_status',
        ),
        sa.CheckConstraint(
            "(status = 'failed') = (error_code IS NOT NULL)",
            name='ck_bacnet_discovery_batches_error',
        ),
    )
    op.create_index(
        'ix_bacnet_discovery_batches_equipment_id', 'bacnet_discovery_batches', ['equipment_id']
    )

    op.create_table(
        'bacnet_discovery_proposals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('batch_id', sa.UUID(), nullable=False),
        sa.Column('object_type', sa.String(length=50), nullable=False),
        sa.Column('object_instance', sa.Integer(), nullable=False),
        sa.Column('object_name', sa.String(length=200), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('bacnet_units', sa.String(length=100), nullable=True),
        sa.Column('present_value_preview', sa.String(length=200), nullable=True),
        sa.Column('value_type', sa.String(length=20), nullable=False),
        sa.Column('states', postgresql.JSONB(), nullable=True),
        sa.Column('proposed_point_class', sa.String(length=100), nullable=True),
        sa.Column('proposed_unit', sa.String(length=20), nullable=True),
        sa.Column('confidence', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('reason_code', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='proposed', nullable=False),
        sa.Column('created_point_id', sa.UUID(), nullable=True),
        sa.Column('decided_by', sa.String(length=200), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'batch_id'],
            ['bacnet_discovery_batches.tenant_id', 'bacnet_discovery_batches.id'],
            name='fk_bacnet_discovery_proposals_batch',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'batch_id', 'object_type', 'object_instance',
            name='uq_bacnet_discovery_proposals_batch_object',
        ),
        sa.CheckConstraint(
            "value_type IN ('number', 'boolean', 'multistate')",
            name='ck_bacnet_discovery_proposals_value_type',
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected', 'duplicate')",
            name='ck_bacnet_discovery_proposals_status',
        ),
        sa.CheckConstraint(
            "(status = 'accepted') = (created_point_id IS NOT NULL)",
            name='ck_bacnet_discovery_proposals_accepted_point',
        ),
        sa.CheckConstraint(
            "(status IN ('accepted', 'rejected')) = "
            "(decided_by IS NOT NULL AND decided_at IS NOT NULL)",
            name='ck_bacnet_discovery_proposals_decision',
        ),
    )
    op.create_index(
        'ix_bacnet_discovery_proposals_batch_id', 'bacnet_discovery_proposals', ['batch_id']
    )

    for table in ('bacnet_discovery_batches', 'bacnet_discovery_proposals'):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            """
        )


def downgrade() -> None:
    for table in ('bacnet_discovery_proposals', 'bacnet_discovery_batches'):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index(
        'ix_bacnet_discovery_proposals_batch_id', table_name='bacnet_discovery_proposals'
    )
    op.drop_table('bacnet_discovery_proposals')
    op.drop_index(
        'ix_bacnet_discovery_batches_equipment_id', table_name='bacnet_discovery_batches'
    )
    op.drop_table('bacnet_discovery_batches')
