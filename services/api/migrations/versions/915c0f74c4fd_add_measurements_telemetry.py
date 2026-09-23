"""add measurements (telemetry, read-only)

Revision ID: 915c0f74c4fd
Revises: c5c55a91cdf8
Create Date: 2026-09-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '915c0f74c4fd'
down_revision: Union[str, None] = 'c5c55a91cdf8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'measurements',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('functional_location_id', sa.UUID(), nullable=True),
        sa.Column('physical_unit_id', sa.UUID(), nullable=True),
        sa.Column('metric', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('source', sa.String(length=50), server_default='simulator', nullable=False),
        sa.Column('measured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['functional_location_id'], ['functional_locations.id'], ),
        sa.ForeignKeyConstraint(['physical_unit_id'], ['physical_units.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_measurements_functional_location_id_measured_at',
        'measurements',
        ['functional_location_id', 'measured_at'],
    )

    op.execute("ALTER TABLE measurements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE measurements FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON measurements
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON measurements")
    op.execute("ALTER TABLE measurements NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE measurements DISABLE ROW LEVEL SECURITY")

    op.drop_index('ix_measurements_functional_location_id_measured_at', table_name='measurements')
    op.drop_table('measurements')
