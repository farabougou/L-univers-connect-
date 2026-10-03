"""add floor plans expand

ADR 011, étape S3 : un plan (PDF/PNG/JPEG) rattaché à un espace (étage ou
bâtiment), stocké comme les photos (ADR 006). Un nouveau plan crée toujours
une nouvelle version : jamais un écrasement (règle non négociable 3), imposé
ici comme pour les autres preuves (interventions_closures, config_versions,
asset_tags) par des déclencheurs qui interdisent toute modification et
suppression — réutilise les fonctions `forbid_update`/`forbid_delete` déjà
créées par la migration 1403c6bbaa32.

Revision ID: f65006c6d8c7
Revises: fbf9f0eba7e6
Create Date: 2026-09-26 20:36:20.476390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f65006c6d8c7'
down_revision: Union[str, None] = 'fbf9f0eba7e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'floor_plans',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('space_id', sa.UUID(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('uploaded_by', sa.String(length=200), nullable=False),
        sa.Column(
            'uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'space_id'], ['spaces.tenant_id', 'spaces.id'],
            name='fk_floor_plans_space',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'space_id', 'version', name='uq_floor_plans_space_version'
        ),
        sa.CheckConstraint('version >= 1', name='ck_floor_plans_version_positive'),
        sa.CheckConstraint(
            "content_type IN ('application/pdf', 'image/png', 'image/jpeg')",
            name='ck_floor_plans_content_type',
        ),
    )
    op.create_index('ix_floor_plans_space_id', 'floor_plans', ['space_id'])

    op.execute("ALTER TABLE floor_plans ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE floor_plans FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON floor_plans
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )

    # Un plan déjà envoyé n'est jamais modifié ni supprimé : une nouvelle
    # version se rajoute (voir ADR 011, section 3). forbid_update/forbid_delete
    # existent déjà (migration 1403c6bbaa32), réutilisées telles quelles.
    op.execute(
        """
        CREATE TRIGGER floor_plans_no_update
        BEFORE UPDATE ON floor_plans
        FOR EACH ROW EXECUTE FUNCTION forbid_update()
        """
    )
    op.execute(
        """
        CREATE TRIGGER floor_plans_no_delete
        BEFORE DELETE ON floor_plans
        FOR EACH ROW EXECUTE FUNCTION forbid_delete()
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
                IF EXISTS (SELECT 1 FROM floor_plans) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des plans existent (tenant %). '
                        'Décision explicite requise.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS floor_plans_no_delete ON floor_plans")
    op.execute("DROP TRIGGER IF EXISTS floor_plans_no_update ON floor_plans")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON floor_plans")
    op.execute("ALTER TABLE floor_plans NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE floor_plans DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_floor_plans_space_id', table_name='floor_plans')
    op.drop_table('floor_plans')
