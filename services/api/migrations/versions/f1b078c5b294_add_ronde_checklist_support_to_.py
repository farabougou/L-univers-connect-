"""add ronde checklist support to interventions

Revision ID: f1b078c5b294
Revises: e84eb7d57bcc
Create Date: 2026-09-22 12:40:26.964078

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1b078c5b294'
down_revision: Union[str, None] = 'e84eb7d57bcc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # (les 3 index détectés à tort comme "supprimés" ne sont pas déclarés au
    # niveau du modèle ORM ; ils ne sont pas touchés par cette migration.)
    op.add_column('interventions', sa.Column('intervention_type', sa.String(length=20), server_default='intervention', nullable=False))
    op.add_column('interventions', sa.Column('checklist', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))


def downgrade() -> None:
    op.drop_column('interventions', 'checklist')
    op.drop_column('interventions', 'intervention_type')
