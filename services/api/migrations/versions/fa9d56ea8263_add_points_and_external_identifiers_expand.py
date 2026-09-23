"""add points, external identifiers, telemetry v2 columns (expand)

Étape 1/3 (élargir) de l'ADR 012, étape F3 : points de télémétrie (nœuds du
graphe, forcés en lecture seule), identifiants externes, et nouvelles
colonnes de measurements (encore facultatives, remplies à l'étape 2).

Revision ID: fa9d56ea8263
Revises: 2f42a0af1365
Create Date: 2026-09-23 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'fa9d56ea8263'
down_revision: Union[str, None] = '2f42a0af1365'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def _set_node_types(types: str) -> None:
    op.drop_constraint('ck_graph_nodes_node_type', 'graph_nodes', type_='check')
    op.create_check_constraint(
        'ck_graph_nodes_node_type', 'graph_nodes', f"node_type IN ({types})"
    )


def upgrade() -> None:
    _set_node_types("'site', 'space', 'functional_location', 'physical_unit', 'point'")

    op.create_table(
        'points',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('functional_location_id', sa.UUID(), nullable=True),
        sa.Column('space_id', sa.UUID(), nullable=True),
        sa.Column('code', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('point_class', sa.String(length=100), nullable=True),
        sa.Column('kind', sa.String(length=20), nullable=True),
        sa.Column('value_type', sa.String(length=20), nullable=False),
        sa.Column('unit', sa.String(length=30), nullable=True),
        sa.Column('states', postgresql.JSONB(), nullable=True),
        sa.Column('expected_interval_seconds', sa.Integer(), nullable=True),
        sa.Column('min_value', sa.Float(), nullable=True),
        sa.Column('max_value', sa.Float(), nullable=True),
        sa.Column('is_writable', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('mapping_status', sa.String(length=20), server_default='proposed', nullable=False),
        sa.Column('mapping_confidence', sa.Float(), nullable=True),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'id'], ['graph_nodes.tenant_id', 'graph_nodes.id'],
            name='fk_points_graph_node',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'functional_location_id'],
            ['functional_locations.tenant_id', 'functional_locations.id'],
            name='fk_points_functional_location',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'space_id'], ['spaces.tenant_id', 'spaces.id'], name='fk_points_space'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'id', name='uq_points_tenant_id_id'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_points_tenant_code'),
        # Règle non négociable 1 inscrite dans la base : aucun point ne peut
        # être déclaré inscriptible. La lever exigera une migration visible.
        sa.CheckConstraint('is_writable = false', name='ck_points_read_only_c0'),
        sa.CheckConstraint(
            "value_type IN ('number', 'boolean', 'multistate')", name='ck_points_value_type'
        ),
        sa.CheckConstraint(
            "mapping_status IN ('proposed', 'validated', 'rejected')",
            name='ck_points_mapping_status',
        ),
        sa.CheckConstraint(
            'mapping_confidence IS NULL OR (mapping_confidence >= 0 AND mapping_confidence <= 1)',
            name='ck_points_mapping_confidence',
        ),
        sa.CheckConstraint(
            'expected_interval_seconds IS NULL OR expected_interval_seconds > 0',
            name='ck_points_expected_interval',
        ),
        sa.CheckConstraint(
            'min_value IS NULL OR max_value IS NULL OR min_value < max_value',
            name='ck_points_range',
        ),
    )
    op.create_index('ix_points_functional_location_id', 'points', ['functional_location_id'])
    op.create_index('ix_points_space_id', 'points', ['space_id'])

    op.create_table(
        'external_identifiers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('node_id', sa.UUID(), nullable=False),
        sa.Column('scheme', sa.String(length=50), nullable=False),
        sa.Column('external_id', sa.String(length=500), nullable=False),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'node_id'], ['graph_nodes.tenant_id', 'graph_nodes.id'],
            name='fk_external_identifiers_node',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'scheme', 'external_id', name='uq_external_identifiers_scheme_value'
        ),
    )
    op.create_index('ix_external_identifiers_node_id', 'external_identifiers', ['node_id'])

    for table in ('points', 'external_identifiers'):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(_TENANT_POLICY.format(table=table))

    op.execute(
        """
        CREATE TRIGGER points_register_graph_node
        BEFORE INSERT ON points
        FOR EACH ROW EXECUTE FUNCTION register_graph_node('point')
        """
    )
    op.execute(
        """
        CREATE TRIGGER points_unregister_graph_node
        AFTER DELETE ON points
        FOR EACH ROW EXECUTE FUNCTION unregister_graph_node()
        """
    )
    # Mise en service : un point « proposed » (découvert, pas encore validé)
    # peut encore être identifié et corrigé. Une fois validé ou rejeté, sa
    # description est figée : la corriger demandera une nouvelle version.
    op.execute(
        """
        CREATE FUNCTION protect_point_definition() RETURNS trigger AS $$
        BEGIN
            IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id
                OR NEW.created_by <> OLD.created_by OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'points : champ non modifiable sur la ligne %', OLD.id;
            END IF;
            IF OLD.mapping_status <> 'proposed' THEN
                RAISE EXCEPTION 'points : la ligne % est % et ne peut plus être modifiée',
                    OLD.id, OLD.mapping_status;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER points_protect_definition
        BEFORE UPDATE ON points
        FOR EACH ROW EXECUTE FUNCTION protect_point_definition()
        """
    )

    op.add_column('measurements', sa.Column('point_id', sa.UUID(), nullable=True))
    op.add_column('measurements', sa.Column('origin', sa.String(length=20), nullable=True))
    op.add_column(
        'measurements',
        sa.Column(
            'quality_flags',
            postgresql.ARRAY(sa.String(length=30)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.add_column(
        'measurements', sa.Column('received_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    # Retour arrière refusé si des points créés par des utilisateurs existent
    # (les points issus de la migration F3 sont retirés par l'étape 2).
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                IF EXISTS (SELECT 1 FROM points) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des points existent (tenant %). '
                        'Sauvegarde vérifiée et décision explicite requises.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.drop_column('measurements', 'received_at')
    op.drop_column('measurements', 'quality_flags')
    op.drop_column('measurements', 'origin')
    op.drop_column('measurements', 'point_id')

    op.execute("DROP TRIGGER IF EXISTS points_protect_definition ON points")
    op.execute("DROP FUNCTION IF EXISTS protect_point_definition()")
    op.execute("DROP TRIGGER IF EXISTS points_unregister_graph_node ON points")
    op.execute("DROP TRIGGER IF EXISTS points_register_graph_node ON points")
    for table in ('external_identifiers', 'points'):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_external_identifiers_node_id', table_name='external_identifiers')
    op.drop_table('external_identifiers')
    op.drop_index('ix_points_space_id', table_name='points')
    op.drop_index('ix_points_functional_location_id', table_name='points')
    op.drop_table('points')

    _set_node_types("'site', 'space', 'functional_location', 'physical_unit'")
