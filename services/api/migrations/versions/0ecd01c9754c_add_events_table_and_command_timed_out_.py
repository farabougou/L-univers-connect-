"""add events table and command timed_out status

Modèle État → Événement → Politique → Alerte (directive de Mohamed du
24/09/2026, docs/spec/feature-benchmark-matrix.md). `events` journalise les
faits horodatés (appareil hors ligne, commande non confirmée...), séparé de
`audit_log` (actions humaines/appareil sensibles) et de `findings`/`alarms`
(ce qui mérite une attention). Append-only par construction : jamais de
UPDATE ni de DELETE prévu dans le code applicatif.

`commands.status` gagne 'timed_out' : une commande envoyée à l'Edge depuis
trop longtemps sans accusé de réception devient un état terminal persisté,
plus seulement un survol calculé à la lecture (voir app/commands.py,
app/monitoring.py).

Revision ID: 0ecd01c9754c
Revises: 1cb0a1548c63
Create Date: 2026-09-24 14:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0ecd01c9754c'
down_revision: Union[str, None] = '1cb0a1548c63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON events
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def upgrade() -> None:
    op.create_table(
        'events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('subject_type', sa.String(length=30), nullable=False),
        sa.Column('subject_id', sa.UUID(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_events_subject', 'events', ['subject_type', 'subject_id', 'occurred_at'])
    op.create_index('ix_events_type', 'events', ['event_type'])

    op.execute("ALTER TABLE events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE events FORCE ROW LEVEL SECURITY")
    op.execute(_TENANT_POLICY)

    op.drop_constraint('ck_commands_status', 'commands', type_='check')
    op.create_check_constraint(
        'ck_commands_status',
        'commands',
        "status IN ('pending', 'sent', 'acknowledged', 'verified', 'failed', 'timed_out')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_commands_status', 'commands', type_='check')
    op.create_check_constraint(
        'ck_commands_status',
        'commands',
        "status IN ('pending', 'sent', 'acknowledged', 'verified', 'failed')",
    )

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON events")
    op.execute("ALTER TABLE events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE events DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_events_type', table_name='events')
    op.drop_index('ix_events_subject', table_name='events')
    op.drop_table('events')
