"""add providers expand

ADR 012, section 2.2 (graphe de connaissances) : le prédicat `maintainedBy`
existait déjà dans le vocabulaire (app/graph_vocabulary.py) mais restait
inutilisable, sans aucun type de nœud pouvant en être l'objet — un
prestataire de maintenance n'était représentable nulle part. `providers`
comble cet écart : un répertoire simple (nom, contact), enregistré dans
graph_nodes comme les autres types déjà en place (site, space,
functional_location, physical_unit, point), pour qu'un site ou un
équipement puisse enfin déclarer qui le maintient.

Pas de nouvelle base : réutilise register_graph_node/unregister_graph_node,
déjà créées par 706eca882498.

Revision ID: 1017a1520913
Revises: b202e7f21592
Create Date: 2026-09-27 00:42:59.977607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1017a1520913'
down_revision: Union[str, None] = 'b202e7f21592'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_graph_nodes_node_type', 'graph_nodes', type_='check')
    op.create_check_constraint(
        'ck_graph_nodes_node_type',
        'graph_nodes',
        "node_type IN ('site', 'space', 'functional_location', 'physical_unit', 'point', "
        "'provider')",
    )

    op.create_table(
        'providers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('contact_name', sa.String(length=200), nullable=True),
        sa.Column('contact_email', sa.String(length=320), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.execute("ALTER TABLE providers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE providers FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON providers
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
        """
    )
    op.execute(
        """
        CREATE TRIGGER providers_register_graph_node
        BEFORE INSERT ON providers
        FOR EACH ROW EXECUTE FUNCTION register_graph_node('provider')
        """
    )
    op.execute(
        """
        CREATE TRIGGER providers_unregister_graph_node
        AFTER DELETE ON providers
        FOR EACH ROW EXECUTE FUNCTION unregister_graph_node()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS providers_unregister_graph_node ON providers")
    op.execute("DROP TRIGGER IF EXISTS providers_register_graph_node ON providers")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON providers")
    op.execute("ALTER TABLE providers NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE providers DISABLE ROW LEVEL SECURITY")
    op.drop_table('providers')

    op.drop_constraint('ck_graph_nodes_node_type', 'graph_nodes', type_='check')
    op.create_check_constraint(
        'ck_graph_nodes_node_type',
        'graph_nodes',
        "node_type IN ('site', 'space', 'functional_location', 'physical_unit', 'point')",
    )
