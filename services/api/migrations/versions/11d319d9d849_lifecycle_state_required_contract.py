"""physical unit lifecycle state required (contract)

Étape 3/3 (contracter) de l'ADR 012, étape F5 : tout exemplaire a
désormais un état de cycle de vie connu ; un nouvel exemplaire est « en
stock » par défaut.

Revision ID: 11d319d9d849
Revises: 120f0277be56
Create Date: 2026-09-23 22:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11d319d9d849'
down_revision: Union[str, None] = '120f0277be56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATES = (
    "'planned', 'ordered', 'in_stock', 'installed', 'commissioned', 'in_service', "
    "'out_of_service', 'removed', 'decommissioned', 'disposed'"
)


def upgrade() -> None:
    op.alter_column(
        'physical_units', 'lifecycle_state', nullable=False, server_default='in_stock'
    )
    op.create_check_constraint(
        'ck_physical_units_lifecycle_state', 'physical_units', f"lifecycle_state IN ({_STATES})"
    )


def downgrade() -> None:
    op.drop_constraint('ck_physical_units_lifecycle_state', 'physical_units', type_='check')
    op.alter_column('physical_units', 'lifecycle_state', nullable=True, server_default=None)
