"""add commands table

Première brique du pipeline de commande (exception strictement limitée à un
appareil simulé — voir CLAUDE.md, exception à la règle non négociable 1,
décision de Mohamed du 24/09/2026). Ne touche jamais `points.is_writable`
(toujours false, `ck_points_read_only_c0`) : un point reste une chose qu'on
lit, la commande est un objet séparé dont on observe le résultat via la
télémétrie existante, jamais un point rendu inscriptible.

Revision ID: 1cb0a1548c63
Revises: 98d44070ae24
Create Date: 2026-09-24 11:47:16.871311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1cb0a1548c63'
down_revision: Union[str, None] = '98d44070ae24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON commands
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def upgrade() -> None:
    op.create_table(
        'commands',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('point_id', sa.UUID(), nullable=False),
        sa.Column('requested_value', sa.Float(), nullable=False),
        sa.Column('requested_by', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('actual_value', sa.Float(), nullable=True),
        sa.Column('failure_reason', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('edge_device_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'point_id'], ['points.tenant_id', 'points.id'], name='fk_commands_point'
        ),
        sa.ForeignKeyConstraint(
            ['edge_device_id'], ['edge_devices.id'], name='fk_commands_edge_device'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'acknowledged', 'verified', 'failed')",
            name='ck_commands_status',
        ),
    )
    op.create_index('ix_commands_point_id', 'commands', ['point_id'])
    op.create_index('ix_commands_status', 'commands', ['status'])

    op.execute("ALTER TABLE commands ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE commands FORCE ROW LEVEL SECURITY")
    op.execute(_TENANT_POLICY)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON commands")
    op.execute("ALTER TABLE commands NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE commands DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_commands_status', table_name='commands')
    op.drop_index('ix_commands_point_id', table_name='commands')
    op.drop_table('commands')
