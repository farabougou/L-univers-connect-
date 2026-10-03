"""add work_order_type

Revision ID: 22040f25f770
Revises: f1b078c5b294
Create Date: 2026-09-22 12:49:39.479565

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22040f25f770'
down_revision: Union[str, None] = 'f1b078c5b294'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # (les 3 index détectés à tort comme "supprimés" ne sont pas déclarés au
    # niveau du modèle ORM ; ils ne sont pas touchés par cette migration.)
    op.add_column('work_orders', sa.Column('work_order_type', sa.String(length=20), server_default='corrective', nullable=False))


def downgrade() -> None:
    op.drop_column('work_orders', 'work_order_type')
