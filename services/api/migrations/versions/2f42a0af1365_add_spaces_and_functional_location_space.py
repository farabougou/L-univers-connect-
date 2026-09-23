"""add spaces and functional location space (expand only)

ADR 011 + ADR 012, étape F2 : arbre spatial (bâtiment, étage, pièce, zone)
séparé de l'arbre technique, emplacement historisé des positions
fonctionnelles, et type de position (système, équipement, composant).

Élargissement uniquement : nouvelles tables, colonnes facultatives,
contraintes d'unicité supplémentaires. Aucune donnée existante n'est
modifiée, donc pas d'étape « migrer » ni « contracter ».

Revision ID: 2f42a0af1365
Revises: 2a7235eda53c
Create Date: 2026-09-23 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f42a0af1365'
down_revision: Union[str, None] = '2a7235eda53c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def upgrade() -> None:
    op.drop_constraint('ck_graph_nodes_node_type', 'graph_nodes', type_='check')
    op.create_check_constraint(
        'ck_graph_nodes_node_type',
        'graph_nodes',
        "node_type IN ('site', 'space', 'functional_location', 'physical_unit')",
    )

    # Nécessaires aux clés étrangères composées avec le tenant (ADR 012, 2.13).
    op.create_unique_constraint('uq_sites_tenant_id_id', 'sites', ['tenant_id', 'id'])
    op.create_unique_constraint(
        'uq_functional_locations_tenant_id_id', 'functional_locations', ['tenant_id', 'id']
    )

    op.create_table(
        'spaces',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('site_id', sa.UUID(), nullable=False),
        sa.Column('parent_id', sa.UUID(), nullable=True),
        sa.Column('space_type', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'site_id'], ['sites.tenant_id', 'sites.id'], name='fk_spaces_site'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'id'],
            ['graph_nodes.tenant_id', 'graph_nodes.id'],
            name='fk_spaces_graph_node',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'id', name='uq_spaces_tenant_id_id'),
        sa.UniqueConstraint('tenant_id', 'site_id', 'id', name='uq_spaces_tenant_site_id'),
        sa.CheckConstraint('parent_id IS NULL OR parent_id <> id', name='ck_spaces_not_own_parent'),
        sa.CheckConstraint(
            'valid_to IS NULL OR valid_to > valid_from', name='ck_spaces_valid_period'
        ),
    )
    # Le parent doit appartenir au même tenant ET au même site : garanti par
    # la base, pas seulement par le code.
    op.create_foreign_key(
        'fk_spaces_parent',
        'spaces',
        'spaces',
        ['tenant_id', 'site_id', 'parent_id'],
        ['tenant_id', 'site_id', 'id'],
    )
    op.create_index('ix_spaces_parent_id', 'spaces', ['parent_id'])
    op.create_index(
        'uq_spaces_open_code',
        'spaces',
        ['tenant_id', 'site_id', 'code'],
        unique=True,
        postgresql_where=sa.text('valid_to IS NULL'),
    )

    op.add_column('functional_locations', sa.Column('space_id', sa.UUID(), nullable=True))
    op.add_column('functional_locations', sa.Column('kind', sa.String(length=20), nullable=True))
    # Une position ne peut être placée que dans un espace du même site.
    op.create_foreign_key(
        'fk_functional_locations_space',
        'functional_locations',
        'spaces',
        ['tenant_id', 'site_id', 'space_id'],
        ['tenant_id', 'site_id', 'id'],
    )
    op.create_index('ix_functional_locations_space_id', 'functional_locations', ['space_id'])

    op.create_table(
        'functional_location_space_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('functional_location_id', sa.UUID(), nullable=False),
        sa.Column('space_id', sa.UUID(), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('changed_by', sa.String(length=200), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'functional_location_id'],
            ['functional_locations.tenant_id', 'functional_locations.id'],
            name='fk_fl_space_history_location',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'space_id'],
            ['spaces.tenant_id', 'spaces.id'],
            name='fk_fl_space_history_space',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_fl_space_history_location_valid_from',
        'functional_location_space_history',
        ['functional_location_id', 'valid_from'],
    )

    for table in ('spaces', 'functional_location_space_history'):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(_TENANT_POLICY.format(table=table))

    op.execute(
        """
        CREATE TRIGGER spaces_register_graph_node
        BEFORE INSERT ON spaces
        FOR EACH ROW EXECUTE FUNCTION register_graph_node('space')
        """
    )
    op.execute(
        """
        CREATE TRIGGER spaces_unregister_graph_node
        AFTER DELETE ON spaces
        FOR EACH ROW EXECUTE FUNCTION unregister_graph_node()
        """
    )

    # La structure d'un espace n'est jamais réécrite : seule sa clôture
    # (valid_to, une seule fois) est permise. Un espace rénové est clos et
    # remplacé par un nouveau, l'ancien reste dans l'historique.
    op.execute(
        """
        CREATE FUNCTION protect_space_structure() RETURNS trigger AS $$
        BEGIN
            IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id
                OR NEW.site_id <> OLD.site_id
                OR NEW.parent_id IS DISTINCT FROM OLD.parent_id
                OR NEW.space_type <> OLD.space_type OR NEW.code <> OLD.code
                OR NEW.name <> OLD.name OR NEW.valid_from <> OLD.valid_from
                OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'spaces : champ non modifiable sur la ligne %', OLD.id;
            END IF;
            IF OLD.valid_to IS NOT NULL AND NEW.valid_to IS DISTINCT FROM OLD.valid_to THEN
                RAISE EXCEPTION 'spaces : la ligne % est déjà close', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER spaces_protect_structure
        BEFORE UPDATE ON spaces
        FOR EACH ROW EXECUTE FUNCTION protect_space_structure()
        """
    )


def downgrade() -> None:
    # Retour arrière refusé dès qu'un espace réel existe : le supprimer
    # effacerait des données métier (règle non négociable 6). La RLS étant
    # forcée, on vérifie client par client.
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                IF EXISTS (SELECT 1 FROM spaces) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des espaces existent (tenant %). '
                        'Sauvegarde vérifiée et décision explicite requises.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )

    op.execute("DROP TRIGGER IF EXISTS spaces_protect_structure ON spaces")
    op.execute("DROP FUNCTION IF EXISTS protect_space_structure()")
    op.execute("DROP TRIGGER IF EXISTS spaces_unregister_graph_node ON spaces")
    op.execute("DROP TRIGGER IF EXISTS spaces_register_graph_node ON spaces")

    for table in ('functional_location_space_history', 'spaces'):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index(
        'ix_fl_space_history_location_valid_from', table_name='functional_location_space_history'
    )
    op.drop_table('functional_location_space_history')

    op.drop_index('ix_functional_locations_space_id', table_name='functional_locations')
    op.drop_constraint('fk_functional_locations_space', 'functional_locations', type_='foreignkey')
    op.drop_column('functional_locations', 'kind')
    op.drop_column('functional_locations', 'space_id')

    op.drop_index('uq_spaces_open_code', table_name='spaces')
    op.drop_index('ix_spaces_parent_id', table_name='spaces')
    op.drop_constraint('fk_spaces_parent', 'spaces', type_='foreignkey')
    op.drop_table('spaces')

    op.drop_constraint(
        'uq_functional_locations_tenant_id_id', 'functional_locations', type_='unique'
    )
    op.drop_constraint('uq_sites_tenant_id_id', 'sites', type_='unique')

    op.drop_constraint('ck_graph_nodes_node_type', 'graph_nodes', type_='check')
    op.create_check_constraint(
        'ck_graph_nodes_node_type',
        'graph_nodes',
        "node_type IN ('site', 'functional_location', 'physical_unit')",
    )
