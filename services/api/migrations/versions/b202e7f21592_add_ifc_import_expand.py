"""add ifc import expand

ADR 011, section 2 (BIM/IFC) : un envoi produit des propositions, jamais
des données fiables sans validation humaine (même principe que le mapping
BACnet/Modbus, proposed -> validated). ifc_import_batches trace l'envoi
(fichier, schéma IFC, compteurs) ; ifc_import_proposals porte chaque
élément candidat (espace ou équipement), avec ses identifiants IFC bruts
pour reconstruire la hiérarchie au moment de l'acceptation.

Comme plan_placements (583c6957ff99) : une proposition décrit un candidat
à valider, pas un fait déjà établi — modifiable/rejetable normalement,
aucun trigger d'immutabilité ici. `created_node_id` reste sans clé
étrangère : une fois acceptée, une proposition d'espace pointe vers
`spaces` et une proposition d'équipement vers `functional_locations`,
deux tables différentes selon le type (même principe que `entity_id` dans
`audit_log`).

Revision ID: b202e7f21592
Revises: 583c6957ff99
Create Date: 2026-09-26 22:30:37.509120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b202e7f21592'
down_revision: Union[str, None] = '583c6957ff99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ifc_import_batches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('site_id', sa.UUID(), nullable=False),
        sa.Column('storage_key', sa.String(length=1000), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='processing', nullable=False),
        sa.Column('error_code', sa.String(length=100), nullable=True),
        sa.Column('ifc_schema', sa.String(length=20), nullable=True),
        sa.Column('space_proposal_count', sa.Integer(), nullable=True),
        sa.Column('equipment_proposal_count', sa.Integer(), nullable=True),
        sa.Column('skipped_element_count', sa.Integer(), nullable=True),
        sa.Column('uploaded_by', sa.String(length=200), nullable=False),
        sa.Column(
            'uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'site_id'], ['sites.tenant_id', 'sites.id'],
            name='fk_ifc_import_batches_site',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'id', name='uq_ifc_import_batches_tenant_id_id'),
        sa.CheckConstraint(
            "status IN ('processing', 'ready', 'failed')",
            name='ck_ifc_import_batches_status',
        ),
        sa.CheckConstraint(
            "(status = 'failed') = (error_code IS NOT NULL)",
            name='ck_ifc_import_batches_error',
        ),
    )
    op.create_index('ix_ifc_import_batches_site_id', 'ifc_import_batches', ['site_id'])

    op.create_table(
        'ifc_import_proposals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('batch_id', sa.UUID(), nullable=False),
        sa.Column('proposal_type', sa.String(length=20), nullable=False),
        sa.Column('ifc_class', sa.String(length=100), nullable=False),
        sa.Column('ifc_global_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('space_type', sa.String(length=20), nullable=True),
        sa.Column('parent_ifc_global_id', sa.String(length=100), nullable=True),
        sa.Column('containing_space_ifc_global_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='proposed', nullable=False),
        sa.Column('created_node_id', sa.UUID(), nullable=True),
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
            ['ifc_import_batches.tenant_id', 'ifc_import_batches.id'],
            name='fk_ifc_import_proposals_batch',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'batch_id', 'ifc_global_id',
            name='uq_ifc_import_proposals_batch_global_id',
        ),
        sa.CheckConstraint(
            "proposal_type IN ('space', 'equipment')",
            name='ck_ifc_import_proposals_type',
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected')",
            name='ck_ifc_import_proposals_status',
        ),
        sa.CheckConstraint(
            "(proposal_type = 'space') = (space_type IS NOT NULL)",
            name='ck_ifc_import_proposals_space_type',
        ),
        sa.CheckConstraint(
            "(status = 'accepted') = (created_node_id IS NOT NULL)",
            name='ck_ifc_import_proposals_accepted_node',
        ),
        sa.CheckConstraint(
            "(status != 'proposed') = (decided_by IS NOT NULL AND decided_at IS NOT NULL)",
            name='ck_ifc_import_proposals_decision',
        ),
    )
    op.create_index('ix_ifc_import_proposals_batch_id', 'ifc_import_proposals', ['batch_id'])

    for table in ('ifc_import_batches', 'ifc_import_proposals'):
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
    for table in ('ifc_import_proposals', 'ifc_import_batches'):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index('ix_ifc_import_proposals_batch_id', table_name='ifc_import_proposals')
    op.drop_table('ifc_import_proposals')
    op.drop_index('ix_ifc_import_batches_site_id', table_name='ifc_import_batches')
    op.drop_table('ifc_import_batches')
