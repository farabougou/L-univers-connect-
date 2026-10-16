"""add graph_nodes and relations (expand)

Étape 1/3 (élargir) de l'ADR 012, étape F1 : registre d'identité commun et
relations typées. Aucune table existante n'est modifiée ici ; les lignes déjà
présentes sont rattrapées par la migration suivante.

Revision ID: 706eca882498
Revises: 915c0f74c4fd
Create Date: 2026-09-23 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '706eca882498'
down_revision: Union[str, None] = '915c0f74c4fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""

# Table métier → type de nœud enregistré automatiquement.
_NODE_TABLES = {
    'sites': 'site',
    'functional_locations': 'functional_location',
    'physical_units': 'physical_unit',
}


def upgrade() -> None:
    op.create_table(
        'graph_nodes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('node_type', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'id', name='uq_graph_nodes_tenant_id_id'),
        sa.CheckConstraint(
            "node_type IN ('site', 'functional_location', 'physical_unit')",
            name='ck_graph_nodes_node_type',
        ),
    )

    op.create_table(
        'relations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('subject_id', sa.UUID(), nullable=False),
        sa.Column('predicate', sa.String(length=50), nullable=False),
        sa.Column('object_id', sa.UUID(), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('origin', sa.String(length=20), server_default='manual', nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='validated', nullable=False),
        sa.Column('vocabulary_version', sa.String(length=30), nullable=False),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        # Clés composées avec le tenant : relier deux clients différents est
        # impossible au niveau de la base, quel que soit le code applicatif.
        sa.ForeignKeyConstraint(
            ['tenant_id', 'subject_id'],
            ['graph_nodes.tenant_id', 'graph_nodes.id'],
            name='fk_relations_subject',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'object_id'],
            ['graph_nodes.tenant_id', 'graph_nodes.id'],
            name='fk_relations_object',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('subject_id <> object_id', name='ck_relations_not_self'),
        sa.CheckConstraint(
            'valid_to IS NULL OR valid_to > valid_from', name='ck_relations_valid_period'
        ),
        sa.CheckConstraint(
            "origin IN ('manual', 'import', 'discovery', 'inferred')", name='ck_relations_origin'
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'validated', 'rejected')", name='ck_relations_status'
        ),
        sa.CheckConstraint(
            'confidence IS NULL OR (confidence >= 0 AND confidence <= 1)',
            name='ck_relations_confidence',
        ),
    )
    op.create_index('ix_relations_subject_id', 'relations', ['subject_id'])
    op.create_index('ix_relations_object_id', 'relations', ['object_id'])
    # Une même relation ne peut être ouverte deux fois (les relations closes
    # ou rejetées restent dans l'historique).
    op.create_index(
        'uq_relations_open',
        'relations',
        ['tenant_id', 'subject_id', 'predicate', 'object_id'],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL AND status <> 'rejected'"),
    )

    for table in ('graph_nodes', 'relations'):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(_TENANT_POLICY.format(table=table))

    # Une relation n'est jamais effacée ni réécrite : seules la clôture
    # (valid_to, une seule fois) et la décision sur une proposition
    # (proposed → validated/rejected) sont permises.
    op.execute(
        """
        CREATE FUNCTION protect_relation_history() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'relations : suppression interdite (ligne %), clore la relation',
                    OLD.id;
            END IF;
            IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id
                OR NEW.subject_id <> OLD.subject_id OR NEW.predicate <> OLD.predicate
                OR NEW.object_id <> OLD.object_id OR NEW.valid_from <> OLD.valid_from
                OR NEW.recorded_at <> OLD.recorded_at OR NEW.origin <> OLD.origin
                OR NEW.confidence IS DISTINCT FROM OLD.confidence
                OR NEW.vocabulary_version <> OLD.vocabulary_version
                OR NEW.created_by <> OLD.created_by THEN
                RAISE EXCEPTION 'relations : champ non modifiable sur la ligne %', OLD.id;
            END IF;
            IF OLD.valid_to IS NOT NULL AND NEW.valid_to IS DISTINCT FROM OLD.valid_to THEN
                RAISE EXCEPTION 'relations : la ligne % est déjà close', OLD.id;
            END IF;
            IF NEW.status <> OLD.status AND OLD.status <> 'proposed' THEN
                RAISE EXCEPTION 'relations : statut définitif sur la ligne %', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER relations_protect_history
        BEFORE UPDATE OR DELETE ON relations
        FOR EACH ROW EXECUTE FUNCTION protect_relation_history()
        """
    )

    # Enregistrement automatique dans le registre : aucun chemin d'écriture
    # (API, import, test) ne peut oublier de créer le nœud.
    op.execute(
        """
        CREATE FUNCTION register_graph_node() RETURNS trigger AS $$
        BEGIN
            INSERT INTO graph_nodes (id, tenant_id, node_type)
            VALUES (NEW.id, NEW.tenant_id, TG_ARGV[0]);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE FUNCTION unregister_graph_node() RETURNS trigger AS $$
        BEGIN
            DELETE FROM graph_nodes WHERE id = OLD.id;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table, node_type in _NODE_TABLES.items():
        op.execute(
            f"""
            CREATE TRIGGER {table}_register_graph_node
            BEFORE INSERT ON {table}
            FOR EACH ROW EXECUTE FUNCTION register_graph_node('{node_type}')
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER {table}_unregister_graph_node
            AFTER DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION unregister_graph_node()
            """
        )


def downgrade() -> None:
    for table in _NODE_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_unregister_graph_node ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_register_graph_node ON {table}")
    op.execute("DROP FUNCTION IF EXISTS unregister_graph_node()")
    op.execute("DROP FUNCTION IF EXISTS register_graph_node()")

    op.execute("DROP TRIGGER IF EXISTS relations_protect_history ON relations")
    op.execute("DROP FUNCTION IF EXISTS protect_relation_history()")

    for table in ('relations', 'graph_nodes'):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index('uq_relations_open', table_name='relations')
    op.drop_index('ix_relations_object_id', table_name='relations')
    op.drop_index('ix_relations_subject_id', table_name='relations')
    op.drop_table('relations')
    op.drop_table('graph_nodes')
