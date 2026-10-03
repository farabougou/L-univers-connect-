"""add tenants and sites with row level security

Revision ID: cde75fe03e41
Revises: ff56e61b2d17
Create Date: 2026-09-21 22:23:32.036612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cde75fe03e41'
down_revision: Union[str, None] = 'ff56e61b2d17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('tenants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('sites',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Isolation des tenants : chaque requête ne voit que les lignes de son
    # propre tenant. FORCE ROW LEVEL SECURITY applique la règle même au
    # rôle propriétaire de la table (le rôle utilisé par l'application),
    # pas seulement aux autres rôles.
    op.execute("ALTER TABLE sites ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sites FORCE ROW LEVEL SECURITY")
    # NULLIF(..., '') est nécessaire car PostgreSQL réinitialise un paramètre
    # personnalisé (custom GUC) à une chaîne vide, et non à NULL, une fois
    # qu'il a été utilisé au moins une fois dans la session. Sans ce NULLIF,
    # le cast ::uuid échouerait dès qu'aucun tenant n'est déclaré.
    op.execute(
        """
        CREATE POLICY tenant_isolation ON sites
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON sites")
    op.execute("ALTER TABLE sites NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sites DISABLE ROW LEVEL SECURITY")
    op.drop_table('sites')
    op.drop_table('tenants')
