"""add lifecycle, asset tags, intervention closures, node properties (expand)

Étape 1/3 (élargir) de l'ADR 012, étape F5 : cycle de vie des exemplaires
(colonne encore facultative, remplie à l'étape 2), étiquettes QR/NFC,
clôture structurée des interventions, propriétés techniques datées.

Revision ID: a4a1fa8a4cfa
Revises: 1403c6bbaa32
Create Date: 2026-09-23 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a4a1fa8a4cfa'
down_revision: Union[str, None] = '1403c6bbaa32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    'physical_unit_lifecycle_events',
    'asset_tags',
    'intervention_closures',
    'node_properties',
)

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def _now():
    return sa.text('now()')


def upgrade() -> None:
    op.add_column(
        'physical_units', sa.Column('lifecycle_state', sa.String(length=20), nullable=True)
    )
    op.create_unique_constraint(
        'uq_physical_units_tenant_id_id', 'physical_units', ['tenant_id', 'id']
    )
    op.create_unique_constraint(
        'uq_interventions_tenant_id_id', 'interventions', ['tenant_id', 'id']
    )

    op.create_table(
        'physical_unit_lifecycle_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('physical_unit_id', sa.UUID(), nullable=False),
        sa.Column('from_state', sa.String(length=20), nullable=True),
        sa.Column('to_state', sa.String(length=20), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column('changed_by', sa.String(length=200), nullable=False),
        sa.Column('note', sa.String(length=2000), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'physical_unit_id'],
            ['physical_units.tenant_id', 'physical_units.id'],
            name='fk_lifecycle_events_unit',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_lifecycle_events_unit_occurred', 'physical_unit_lifecycle_events',
        ['physical_unit_id', 'occurred_at'],
    )

    op.create_table(
        'asset_tags',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('node_id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('tag_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.String(length=200), nullable=True),
        sa.Column('revoke_reason', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'node_id'], ['graph_nodes.tenant_id', 'graph_nodes.id'],
            name='fk_asset_tags_node',
        ),
        sa.PrimaryKeyConstraint('id'),
        # Code aléatoire (128 bits) : impossible à deviner, unique partout.
        sa.UniqueConstraint('code', name='uq_asset_tags_code'),
        sa.CheckConstraint("tag_type IN ('qr', 'nfc', 'barcode')", name='ck_asset_tags_type'),
        sa.CheckConstraint("status IN ('active', 'revoked')", name='ck_asset_tags_status'),
        sa.CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)", name='ck_asset_tags_revocation'
        ),
    )
    op.create_index('ix_asset_tags_node_id', 'asset_tags', ['node_id'])

    op.create_table(
        'intervention_closures',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('intervention_id', sa.UUID(), nullable=False),
        sa.Column('symptom_code', sa.String(length=50), nullable=False),
        sa.Column('cause_code', sa.String(length=50), nullable=False),
        sa.Column('action_code', sa.String(length=50), nullable=False),
        sa.Column('parts', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('labor_minutes', sa.Integer(), nullable=False),
        sa.Column('verification_result', sa.String(length=20), nullable=False),
        sa.Column('note', sa.String(length=2000), nullable=True),
        sa.Column('closed_by', sa.String(length=200), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'intervention_id'],
            ['interventions.tenant_id', 'interventions.id'],
            name='fk_intervention_closures_intervention',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('intervention_id', name='uq_intervention_closures_intervention'),
        sa.CheckConstraint(
            'labor_minutes >= 0 AND labor_minutes <= 10080', name='ck_closures_labor_minutes'
        ),
        sa.CheckConstraint(
            "verification_result IN ('ok', 'partial', 'failed')", name='ck_closures_verification'
        ),
    )

    op.create_table(
        'node_properties',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('node_id', sa.UUID(), nullable=False),
        sa.Column('property_key', sa.String(length=50), nullable=False),
        sa.Column('value_number', sa.Float(), nullable=True),
        sa.Column('value_text', sa.String(length=200), nullable=True),
        sa.Column('unit', sa.String(length=30), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'node_id'], ['graph_nodes.tenant_id', 'graph_nodes.id'],
            name='fk_node_properties_node',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            '(value_number IS NULL) <> (value_text IS NULL)', name='ck_node_properties_one_value'
        ),
        sa.CheckConstraint(
            "source IN ('nameplate', 'document', 'measurement', 'manual')",
            name='ck_node_properties_source',
        ),
        sa.CheckConstraint(
            'valid_to IS NULL OR valid_to > valid_from', name='ck_node_properties_period'
        ),
    )
    op.create_index(
        'uq_node_properties_open', 'node_properties', ['tenant_id', 'node_id', 'property_key'],
        unique=True, postgresql_where=sa.text('valid_to IS NULL'),
    )

    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(_TENANT_POLICY.format(table=table))

    # Une clôture d'intervention est une preuve : jamais modifiée ni supprimée.
    op.execute(
        """
        CREATE FUNCTION forbid_update() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% : modification interdite (ligne %)', TG_TABLE_NAME, OLD.id;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER intervention_closures_no_update
        BEFORE UPDATE ON intervention_closures
        FOR EACH ROW EXECUTE FUNCTION forbid_update()
        """
    )
    op.execute(
        """
        CREATE TRIGGER intervention_closures_no_delete
        BEFORE DELETE ON intervention_closures
        FOR EACH ROW EXECUTE FUNCTION forbid_delete()
        """
    )

    # Une étiquette n'est jamais réattribuée : seule sa révocation (une fois)
    # est permise. Une étiquette abîmée est révoquée, une nouvelle est créée.
    op.execute(
        """
        CREATE FUNCTION protect_asset_tag() RETURNS trigger AS $$
        BEGIN
            IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id OR NEW.node_id <> OLD.node_id
                OR NEW.code <> OLD.code OR NEW.tag_type <> OLD.tag_type
                OR NEW.created_by <> OLD.created_by OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'asset_tags : champ non modifiable sur la ligne %', OLD.id;
            END IF;
            IF OLD.status = 'revoked' THEN
                RAISE EXCEPTION 'asset_tags : la ligne % est déjà révoquée', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER asset_tags_protect
        BEFORE UPDATE ON asset_tags
        FOR EACH ROW EXECUTE FUNCTION protect_asset_tag()
        """
    )

    op.execute(
        """
        CREATE FUNCTION protect_node_property() RETURNS trigger AS $$
        BEGIN
            IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id OR NEW.node_id <> OLD.node_id
                OR NEW.property_key <> OLD.property_key
                OR NEW.value_number IS DISTINCT FROM OLD.value_number
                OR NEW.value_text IS DISTINCT FROM OLD.value_text
                OR NEW.unit IS DISTINCT FROM OLD.unit OR NEW.source <> OLD.source
                OR NEW.valid_from <> OLD.valid_from OR NEW.recorded_at <> OLD.recorded_at
                OR NEW.reason <> OLD.reason OR NEW.created_by <> OLD.created_by THEN
                RAISE EXCEPTION 'node_properties : champ non modifiable (%), clore et recréer',
                    OLD.id;
            END IF;
            IF OLD.valid_to IS NOT NULL AND NEW.valid_to IS DISTINCT FROM OLD.valid_to THEN
                RAISE EXCEPTION 'node_properties : la ligne % est déjà close', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER node_properties_protect
        BEFORE UPDATE ON node_properties
        FOR EACH ROW EXECUTE FUNCTION protect_node_property()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                IF EXISTS (SELECT 1 FROM physical_unit_lifecycle_events)
                    OR EXISTS (SELECT 1 FROM asset_tags)
                    OR EXISTS (SELECT 1 FROM intervention_closures)
                    OR EXISTS (SELECT 1 FROM node_properties) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des données de cycle de vie, étiquettes, '
                        'clôtures ou propriétés existent (tenant %). Décision explicite requise.',
                        t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS node_properties_protect ON node_properties")
    op.execute("DROP FUNCTION IF EXISTS protect_node_property()")
    op.execute("DROP TRIGGER IF EXISTS asset_tags_protect ON asset_tags")
    op.execute("DROP FUNCTION IF EXISTS protect_asset_tag()")
    op.execute("DROP TRIGGER IF EXISTS intervention_closures_no_delete ON intervention_closures")
    op.execute("DROP TRIGGER IF EXISTS intervention_closures_no_update ON intervention_closures")
    op.execute("DROP FUNCTION IF EXISTS forbid_update()")

    for table in reversed(_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index('uq_node_properties_open', table_name='node_properties')
    op.drop_table('node_properties')
    op.drop_table('intervention_closures')
    op.drop_index('ix_asset_tags_node_id', table_name='asset_tags')
    op.drop_table('asset_tags')
    op.drop_index('ix_lifecycle_events_unit_occurred', table_name='physical_unit_lifecycle_events')
    op.drop_table('physical_unit_lifecycle_events')

    op.drop_constraint('uq_interventions_tenant_id_id', 'interventions', type_='unique')
    op.drop_constraint('uq_physical_units_tenant_id_id', 'physical_units', type_='unique')
    op.drop_column('physical_units', 'lifecycle_state')
