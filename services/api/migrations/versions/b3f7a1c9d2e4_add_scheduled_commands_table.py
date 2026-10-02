"""add scheduled_commands table

Planification (V2, 02/10/2026, priorité « planification » de la feuille de
route) : une commande déclarée à l'avance, exécutée plus tard par un
balayage périodique (app/scheduled_commands_sweep.py, même mécanisme que
app/supervision_sweep.py). N'étend jamais la règle non négociable 1 : la
commandabilité et la policy active du point (app/command_policies.py) sont
revérifiées au moment du déclenchement, pas seulement à la planification —
un point qui cesse d'être commandable, ou une policy qui change entre
temps, bloque le déclenchement (status 'failed'), jamais un contournement.

Revision ID: b3f7a1c9d2e4
Revises: ada08b67a28c
Create Date: 2026-10-02 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b3f7a1c9d2e4'
down_revision: Union[str, None] = 'ada08b67a28c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON scheduled_commands
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def upgrade() -> None:
    op.create_table(
        'scheduled_commands',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('point_id', sa.UUID(), nullable=False),
        sa.Column('requested_value', sa.Float(), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('requested_by', sa.String(length=200), nullable=False),
        # Rôles de la personne au moment de la planification — revérifiés
        # contre la policy active au déclenchement (voir
        # app/scheduled_commands.py) : un balayage automatique n'a pas de
        # session, donc pas de rôle "courant" à relire ailleurs.
        sa.Column(
            'requester_roles', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('command_id', sa.UUID(), nullable=True),
        sa.Column('failure_reason', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_by', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'point_id'],
            ['points.tenant_id', 'points.id'],
            name='fk_scheduled_commands_point',
        ),
        sa.ForeignKeyConstraint(
            ['command_id'], ['commands.id'], name='fk_scheduled_commands_command'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN ('pending', 'dispatched', 'cancelled', 'failed')",
            name='ck_scheduled_commands_status',
        ),
    )
    op.create_index(
        'ix_scheduled_commands_due', 'scheduled_commands', ['status', 'scheduled_for']
    )
    op.create_index('ix_scheduled_commands_point_id', 'scheduled_commands', ['point_id'])

    op.execute("ALTER TABLE scheduled_commands ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE scheduled_commands FORCE ROW LEVEL SECURITY")
    op.execute(_TENANT_POLICY)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON scheduled_commands")
    op.execute("ALTER TABLE scheduled_commands NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE scheduled_commands DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_scheduled_commands_point_id', table_name='scheduled_commands')
    op.drop_index('ix_scheduled_commands_due', table_name='scheduled_commands')
    op.drop_table('scheduled_commands')
