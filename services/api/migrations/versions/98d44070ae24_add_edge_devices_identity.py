"""add edge devices identity

Première brique d'identité machine (M4, ADR 012 §2.10) : un appareil Edge
(aujourd'hui le démon Modbus) obtient un secret haute entropie à
l'inscription, jamais stocké en clair (seul son empreinte l'est). Conçu
pour évoluer vers un certificat (mTLS) sans réécriture : `credential_type`
distingue déjà le type de créance, même si "shared_secret" est la seule
valeur possible pour l'instant.

Revision ID: 98d44070ae24
Revises: 4daa35f4dcf1
Create Date: 2026-09-24 10:47:21.141857

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98d44070ae24'
down_revision: Union[str, None] = '4daa35f4dcf1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON edge_devices
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def upgrade() -> None:
    op.create_table(
        'edge_devices',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('site_id', sa.UUID(), nullable=True),
        # Étiquette humaine, jamais utilisée pour la recherche (voir
        # app/devices.py) : seul l'identifiant technique (id) sert de clé.
        sa.Column('device_id', sa.String(length=200), nullable=False),
        sa.Column('credential_type', sa.String(length=20), server_default='shared_secret', nullable=False),
        sa.Column('secret_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.String(length=200), nullable=True),
        sa.Column('revoked_reason', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'site_id'], ['sites.tenant_id', 'sites.id'], name='fk_edge_devices_site'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'device_id', name='uq_edge_devices_tenant_device_id'),
        sa.CheckConstraint("credential_type IN ('shared_secret')", name='ck_edge_devices_credential_type'),
        sa.CheckConstraint("status IN ('active', 'revoked')", name='ck_edge_devices_status'),
        sa.CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)", name='ck_edge_devices_revocation_consistent'
        ),
    )
    op.create_index('ix_edge_devices_site_id', 'edge_devices', ['site_id'])

    op.execute("ALTER TABLE edge_devices ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE edge_devices FORCE ROW LEVEL SECURITY")
    op.execute(_TENANT_POLICY)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON edge_devices")
    op.execute("ALTER TABLE edge_devices NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE edge_devices DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_edge_devices_site_id', table_name='edge_devices')
    op.drop_table('edge_devices')
