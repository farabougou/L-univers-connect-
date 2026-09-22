"""add intervention photos

Revision ID: c5c55a91cdf8
Revises: 22040f25f770
Create Date: 2026-09-22 13:00:51.726781

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5c55a91cdf8'
down_revision: Union[str, None] = '22040f25f770'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # (les 3 index détectés à tort comme "supprimés" ne sont pas déclarés au
    # niveau du modèle ORM ; ils ne sont pas touchés par cette migration.)
    op.create_table('intervention_photos',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('intervention_id', sa.UUID(), nullable=False),
    sa.Column('storage_key', sa.String(length=500), nullable=False),
    sa.Column('caption', sa.String(length=500), nullable=True),
    sa.Column('taken_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['intervention_id'], ['interventions.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.execute("ALTER TABLE intervention_photos ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE intervention_photos FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON intervention_photos
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON intervention_photos")
    op.execute("ALTER TABLE intervention_photos NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE intervention_photos DISABLE ROW LEVEL SECURITY")

    op.drop_table('intervention_photos')
