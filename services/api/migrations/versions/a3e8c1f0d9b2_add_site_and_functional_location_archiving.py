"""add site and functional location archiving

Demande de Mohamed du 30/09/2026 : « mets l'option supprimer, j'en ai
trop et souhaite faire un truc propre ». Une vraie suppression irait à
l'encontre de la règle non négociable 3 (rien n'est écrasé, historique
conservé) et pourrait un jour effacer un site ou un équipement portant
de vraies données (mesures, interventions, audit). À la place :
l'archivage, réversible, qui masque un site ou un équipement des listes
par défaut sans toucher à l'historique ni aux relations existantes.

Revision ID: a3e8c1f0d9b2
Revises: f4a1c9e2b7d3
Create Date: 2026-09-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3e8c1f0d9b2'
down_revision: Union[str, None] = 'f4a1c9e2b7d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ('sites', 'functional_locations'):
        op.add_column(table, sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column('archived_by', sa.Text(), nullable=True))


def downgrade() -> None:
    for table in ('sites', 'functional_locations'):
        op.drop_column(table, 'archived_by')
        op.drop_column(table, 'archived_at')
