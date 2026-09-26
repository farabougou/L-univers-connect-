"""link node tables to graph_nodes (contract)

Étape 3/3 (contracter) de l'ADR 012, étape F1 : chaque site, position
fonctionnelle et exemplaire doit désormais avoir son nœud dans le registre,
avec le même tenant. La base refuse toute ligne qui n'en aurait pas.

Revision ID: 2a7235eda53c
Revises: 2c1a247ca272
Create Date: 2026-09-23 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2a7235eda53c'
down_revision: Union[str, None] = '2c1a247ca272'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NODE_TABLES = ('sites', 'functional_locations', 'physical_units')


def upgrade() -> None:
    for table in _NODE_TABLES:
        op.create_foreign_key(
            f'fk_{table}_graph_node',
            table,
            'graph_nodes',
            ['tenant_id', 'id'],
            ['tenant_id', 'id'],
        )


def downgrade() -> None:
    for table in _NODE_TABLES:
        op.drop_constraint(f'fk_{table}_graph_node', table, type_='foreignkey')
