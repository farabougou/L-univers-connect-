"""add bacnet discovery timeout (edge-executed discovery)

Directive de Mohamed du 30/09/2026 : « le terrain doit servir à découvrir,
comparer, mesurer, corriger, valider — pas à développer sur place ». La
découverte BACnet s'exécutait jusqu'ici en synchrone dans le processus API
(cloud) : cela ne peut pas atteindre un réseau BACnet/IP de site réel. Le
scan est désormais demandé par une personne (le lot naît en 'processing',
sans appel réseau) puis exécuté par l'agent Edge sur site
(`scripts/bacnet_discovery_agent.py`), qui a besoin du délai maximal choisi
au moment de la demande — d'où cette colonne (nullable pour les lots déjà
en base, valeur par défaut 3.0 comme l'ancien paramètre de fonction).

Revision ID: f4a1c9e2b7d3
Revises: d0252a39b344
Create Date: 2026-09-30 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a1c9e2b7d3'
down_revision: Union[str, None] = 'd0252a39b344'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'bacnet_discovery_batches',
        sa.Column('timeout_seconds', sa.Numeric(precision=4, scale=1), server_default='3.0',
                   nullable=False),
    )


def downgrade() -> None:
    op.drop_column('bacnet_discovery_batches', 'timeout_seconds')
