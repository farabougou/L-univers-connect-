"""add documents

Section 36, point 10 (directive UI/dashboard) : bibliothèque de documents
(manuels, certificats, garanties, fiches techniques, contrats, rapports de
conformité) rattachés à un équipement (position fonctionnelle). Distinct des
plans 2D (floor_plans, ADR 011 — un plan d'étage) et des photos
d'intervention (ADR 006) : un document ici est une pièce administrative ou
technique de l'équipement, pas une preuve d'intervention ni un plan spatial.

Un document envoyé n'est jamais modifié ni supprimé (règle non négociable 3)
— chaque envoi est une nouvelle ligne indépendante (pas de numéro de version
partagé comme les plans : un certificat renouvelé est un nouveau document,
pas une nouvelle version du même document). Mêmes déclencheurs
forbid_update/forbid_delete que floor_plans (migration 1403c6bbaa32).

Revision ID: b1d4f2a9c7e3
Revises: a3e8c1f0d9b2
Create Date: 2026-09-30 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1d4f2a9c7e3'
down_revision: Union[str, None] = 'a3e8c1f0d9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('functional_location_id', sa.UUID(), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
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
            ['tenant_id', 'functional_location_id'],
            ['functional_locations.tenant_id', 'functional_locations.id'],
            name='fk_documents_functional_location',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "category IN ('manual', 'certificate', 'warranty', 'datasheet', "
            "'compliance_report', 'contract', 'other')",
            name='ck_documents_category',
        ),
        sa.CheckConstraint(
            "content_type IN ('application/pdf', 'image/png', 'image/jpeg')",
            name='ck_documents_content_type',
        ),
    )
    op.create_index(
        'ix_documents_functional_location_id', 'documents', ['functional_location_id']
    )

    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE documents FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON documents
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )

    op.execute(
        """
        CREATE TRIGGER documents_no_update
        BEFORE UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION forbid_update()
        """
    )
    op.execute(
        """
        CREATE TRIGGER documents_no_delete
        BEFORE DELETE ON documents
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
                IF EXISTS (SELECT 1 FROM documents) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des documents existent (tenant %). '
                        'Décision explicite requise.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS documents_no_delete ON documents")
    op.execute("DROP TRIGGER IF EXISTS documents_no_update ON documents")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON documents")
    op.execute("ALTER TABLE documents NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE documents DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_documents_functional_location_id', table_name='documents')
    op.drop_table('documents')
