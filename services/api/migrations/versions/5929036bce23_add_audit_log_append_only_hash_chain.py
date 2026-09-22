"""add audit_log append-only hash chain

Revision ID: 5929036bce23
Revises: cde75fe03e41
Create Date: 2026-09-22 11:10:57.749214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5929036bce23'
down_revision: Union[str, None] = 'cde75fe03e41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('audit_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('seq', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('actor', sa.String(length=200), nullable=False),
    sa.Column('action', sa.String(length=200), nullable=False),
    sa.Column('entity_type', sa.String(length=200), nullable=True),
    sa.Column('entity_id', sa.String(length=200), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('previous_hash', sa.String(length=64), nullable=False),
    sa.Column('entry_hash', sa.String(length=64), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('seq')
    )
    op.create_index('audit_log_tenant_seq_idx', 'audit_log', ['tenant_id', 'seq'])

    # Isolation par tenant, comme pour sites (voir migration cde75fe03e41).
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON audit_log
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )

    # Append-only : la base de données elle-même refuse toute modification
    # ou suppression d'une entrée déjà écrite, quel que soit le rôle qui
    # tente l'opération (hors superutilisateur désactivant les triggers).
    op.execute(
        """
        CREATE FUNCTION prevent_audit_log_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log est append-only : % interdit sur la ligne %', TG_OP, OLD.id;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_log")
    op.execute("ALTER TABLE audit_log NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log DISABLE ROW LEVEL SECURITY")
    op.drop_index('audit_log_tenant_seq_idx', table_name='audit_log')
    op.drop_table('audit_log')
