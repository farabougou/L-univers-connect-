"""add scheduled job runs

V4 (priorité « Déploiement » : observabilité des tâches planifiées).
Les quatre balayages périodiques (supervision, commandes planifiées,
automatisation, ancrage d'audit) tournent déjà, mais leur seule trace
avant cette table était une ligne de journal : utile en direct, pas
pour répondre tout de suite à « est-ce que ça tourne encore ? ».

Donnée de plateforme, jamais une donnée métier d'un tenant (même
raisonnement que pour `tenants` elle-même, voir app/supervision_sweep.py) :
un seul balayage traite tous les tenants dans le même tour, donc aucune
ligne de cette table n'appartient à un tenant précis. Pas de RLS, pas de
tenant_id — exactement comme `tenants`.

Insertion seulement, jamais de mise à jour ni de suppression en usage
normal (voir app/job_runs.py) ; pas de déclencheur applicatif comme sur
`audit_log`, puisque ce n'est pas un témoin de sécurité mais une
télémétrie d'exploitation lue par GET /metrics (app/metrics.py).

Revision ID: 5d158928f01b
Revises: 9a4902b5c49b
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5d158928f01b'
down_revision: Union[str, None] = '9a4902b5c49b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scheduled_job_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_name', sa.String(length=100), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('succeeded', sa.Boolean(), nullable=False),
        sa.Column(
            'summary',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_scheduled_job_runs_job_name_started_at',
        'scheduled_job_runs',
        ['job_name', sa.text('started_at DESC')],
    )


def downgrade() -> None:
    op.drop_index('ix_scheduled_job_runs_job_name_started_at', table_name='scheduled_job_runs')
    op.drop_table('scheduled_job_runs')
