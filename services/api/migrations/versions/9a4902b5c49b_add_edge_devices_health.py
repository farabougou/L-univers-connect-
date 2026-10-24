"""add edge devices health

V4 (ADR 012 §2.10, priorité « Edge » : health monitoring) : un appareil
Edge peut déjà annoncer son identité, son état de communication
(last_seen_at) et ses mesures. Deux colonnes de plus, toutes deux
nullables et mises à jour uniquement quand l'appareil les reporte
(COALESCE, voir app/devices.py::touch_last_seen) — jamais écrasées par une
absence, même principe que « hors ligne montre le dernier état connu » :

- `agent_version` : la version du démon qui authentifie cet appareil,
  pour voir d'un coup d'œil sur toute la flotte quels démons restent à
  mettre à jour (aucune mise à jour automatique construite ici, juste la
  visibilité qui la rendra possible plus tard).
- `pending_buffer_count` : combien de mesures ont dû être mises en
  tampon local (app/connectors/offline_buffer.py) avant cette relève
  réussie — 0 signifie aucune instabilité réseau récente.

Revision ID: 9a4902b5c49b
Revises: b3f7a1c9d2e4
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a4902b5c49b'
down_revision: Union[str, None] = 'b3f7a1c9d2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('edge_devices', sa.Column('agent_version', sa.String(length=50), nullable=True))
    op.add_column('edge_devices', sa.Column('pending_buffer_count', sa.Integer(), nullable=True))
    op.create_check_constraint(
        'ck_edge_devices_pending_buffer_count_non_negative',
        'edge_devices',
        'pending_buffer_count IS NULL OR pending_buffer_count >= 0',
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_edge_devices_pending_buffer_count_non_negative', 'edge_devices', type_='check'
    )
    op.drop_column('edge_devices', 'pending_buffer_count')
    op.drop_column('edge_devices', 'agent_version')
