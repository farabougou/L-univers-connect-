"""add commands requester_roles

Audit de sécurité (16/10/2026, pistes Siemens ProductCERT SSA-333035) :
une commande immédiate (`commands`, POST /commands) ne revérifiait la
policy active du point qu'à la création, jamais au moment où l'Edge la
réclame (`claim_pending_commands`) — contrairement à une commande
planifiée (`scheduled_commands`), déjà revérifiée à la création ET au
déclenchement (voir app/scheduled_commands.py). Une commande restée
« pending » pendant une coupure de l'automate pouvait donc être exécutée
au retour avec une policy devenue entre-temps plus stricte (rôle retiré,
valeur retirée), jamais revérifiée.

Cette colonne permet la revérification à la réclamation (voir
app/commands.py, claim_pending_commands) en conservant les rôles de la
personne qui a demandé la commande — même colonne, même type, même valeur
par défaut que `scheduled_commands.requester_roles`
(migration b3f7a1c9d2e4), pour la même raison.

Revision ID: b7c43d1f8e70
Revises: 5d158928f01b
Create Date: 2026-10-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7c43d1f8e70'
down_revision: Union[str, None] = '5d158928f01b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'commands',
        sa.Column(
            'requester_roles',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('commands', 'requester_roles')
