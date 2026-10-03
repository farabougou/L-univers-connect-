"""add operat declarations

OPERAT / Éco Énergie Tertiaire (décret tertiaire, arrêté du 10 avril 2020) —
voir docs/regulatory/01-operat-eco-energie-tertiaire.md. Une déclaration par
site et par année de référence, workflow brouillon → prêt → transmis : la
transmission réelle au portail ADEME reste aujourd'hui manuelle (aucun accès
API officiel disponible), donc enregistrée ici après coup
(`record_manual_submission`) plutôt que simulée. Gelée une fois transmise
(trigger dédié, jamais le `forbid_update` générique qui bloquerait aussi le
brouillon) ; supprimable seulement tant qu'elle reste un brouillon.

Revision ID: ada08b67a28c
Revises: adce8b5d46b8
Create Date: 2026-10-02 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ada08b67a28c'
down_revision: Union[str, None] = 'adce8b5d46b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'operat_declarations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('site_id', sa.UUID(), nullable=False),
        sa.Column('reference_year', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('floor_area_m2', sa.Float(), nullable=True),
        sa.Column('activity_category', sa.String(length=200), nullable=True),
        sa.Column('electricity_kwh', sa.Float(), nullable=True),
        sa.Column('gas_kwh', sa.Float(), nullable=True),
        sa.Column('heat_network_kwh', sa.Float(), nullable=True),
        sa.Column('other_kwh', sa.Float(), nullable=True),
        sa.Column('other_label', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.String(length=2000), nullable=True),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('updated_by', sa.String(length=200), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_by', sa.String(length=200), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submission_reference', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'site_id'], ['sites.tenant_id', 'sites.id'],
            name='fk_operat_declarations_site',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'site_id', 'reference_year', name='uq_operat_declarations_site_year'
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'submitted')", name='ck_operat_declarations_status'
        ),
        sa.CheckConstraint(
            "(status = 'submitted') = (submitted_at IS NOT NULL AND submitted_by IS NOT NULL)",
            name='ck_operat_declarations_submission_fields',
        ),
        sa.CheckConstraint(
            'floor_area_m2 IS NULL OR floor_area_m2 >= 0', name='ck_operat_floor_area_non_negative'
        ),
        sa.CheckConstraint(
            'electricity_kwh IS NULL OR electricity_kwh >= 0',
            name='ck_operat_electricity_non_negative',
        ),
        sa.CheckConstraint('gas_kwh IS NULL OR gas_kwh >= 0', name='ck_operat_gas_non_negative'),
        sa.CheckConstraint(
            'heat_network_kwh IS NULL OR heat_network_kwh >= 0',
            name='ck_operat_heat_network_non_negative',
        ),
        sa.CheckConstraint(
            'other_kwh IS NULL OR other_kwh >= 0', name='ck_operat_other_non_negative'
        ),
    )

    op.execute("ALTER TABLE operat_declarations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE operat_declarations FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON operat_declarations
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )

    op.execute(
        """
        CREATE FUNCTION protect_operat_declaration_update() RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'submitted' THEN
                RAISE EXCEPTION
                    'operat_declarations : une déclaration transmise ne se modifie plus (ligne %)',
                    OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER operat_declarations_protect_update
        BEFORE UPDATE ON operat_declarations
        FOR EACH ROW EXECUTE FUNCTION protect_operat_declaration_update()
        """
    )
    op.execute(
        """
        CREATE FUNCTION protect_operat_declaration_delete() RETURNS trigger AS $$
        BEGIN
            IF OLD.status <> 'draft' THEN
                RAISE EXCEPTION
                    'operat_declarations : seul un brouillon peut être supprimé (ligne %)', OLD.id;
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER operat_declarations_protect_delete
        BEFORE DELETE ON operat_declarations
        FOR EACH ROW EXECUTE FUNCTION protect_operat_declaration_delete()
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
                IF EXISTS (SELECT 1 FROM operat_declarations) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des déclarations OPERAT existent (tenant %). '
                        'Décision explicite requise.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS operat_declarations_protect_delete ON operat_declarations"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_operat_declaration_delete()")
    op.execute(
        "DROP TRIGGER IF EXISTS operat_declarations_protect_update ON operat_declarations"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_operat_declaration_update()")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON operat_declarations")
    op.execute("ALTER TABLE operat_declarations NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE operat_declarations DISABLE ROW LEVEL SECURITY")
    op.drop_table('operat_declarations')
