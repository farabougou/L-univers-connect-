"""add device public key assertion

Deuxième créance d'appareil (ADR 012 §2.10, décision de Mohamed du
24/09/2026) : identité par paire de clés asymétriques et preuve
cryptographique applicative (JWT signé ES256, voir app/devices.py), en
remplacement progressif du secret partagé — HTTPS reste obligatoire, ceci
ne fait pas de mTLS transport (voir le plan présenté à Mohamed : la
terminaison HTTPS standard de l'hébergeur ne vérifie pas de certificat
client). `shared_secret` n'est conservé que pour la compatibilité et la
migration des appareils déjà provisionnés ; ce n'est plus le modèle cible.

Élargir seulement : `secret_hash` devient nullable (un appareil à clé
publique n'en a pas), deux colonnes nouvelles portent la clé publique et
son empreinte, et une table d'usage unique protège contre le rejeu d'une
preuve interceptée (une preuve courte ne sert qu'une fois — voir
`app/devices.py`, `MAX_ASSERTION_TTL`).

Revision ID: 59e74fed4108
Revises: 0ecd01c9754c
Create Date: 2026-09-24 21:33:16.949297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59e74fed4108'
down_revision: Union[str, None] = '0ecd01c9754c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NONCE_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON device_assertion_nonces
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def upgrade() -> None:
    op.alter_column('edge_devices', 'secret_hash', existing_type=sa.String(length=64), nullable=True)
    op.add_column('edge_devices', sa.Column('public_key_pem', sa.Text(), nullable=True))
    op.add_column('edge_devices', sa.Column('key_fingerprint', sa.String(length=64), nullable=True))
    op.add_column(
        'edge_devices', sa.Column('key_rotated_at', sa.DateTime(timezone=True), nullable=True)
    )

    op.drop_constraint('ck_edge_devices_credential_type', 'edge_devices', type_='check')
    op.create_check_constraint(
        'ck_edge_devices_credential_type',
        'edge_devices',
        "credential_type IN ('shared_secret', 'public_key_assertion')",
    )
    # Exactement une créance selon le type déclaré : jamais les deux, jamais
    # aucune. Une migration (app/devices.py, set_public_key) bascule les deux
    # colonnes ensemble dans la même transaction.
    op.create_check_constraint(
        'ck_edge_devices_credential_material',
        'edge_devices',
        "(credential_type = 'shared_secret' AND secret_hash IS NOT NULL "
        "AND public_key_pem IS NULL) "
        "OR (credential_type = 'public_key_assertion' AND public_key_pem IS NOT NULL "
        "AND secret_hash IS NULL)",
    )

    op.create_table(
        'device_assertion_nonces',
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.UUID(), nullable=False),
        sa.Column('jti', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['device_id'], ['edge_devices.id']),
        sa.PrimaryKeyConstraint('device_id', 'jti'),
    )
    op.create_index(
        'ix_device_assertion_nonces_expires_at', 'device_assertion_nonces', ['expires_at']
    )

    op.execute("ALTER TABLE device_assertion_nonces ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE device_assertion_nonces FORCE ROW LEVEL SECURITY")
    op.execute(_NONCE_TENANT_POLICY)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON device_assertion_nonces")
    op.execute("ALTER TABLE device_assertion_nonces NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE device_assertion_nonces DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_device_assertion_nonces_expires_at', table_name='device_assertion_nonces')
    op.drop_table('device_assertion_nonces')

    op.drop_constraint('ck_edge_devices_credential_material', 'edge_devices', type_='check')
    op.drop_constraint('ck_edge_devices_credential_type', 'edge_devices', type_='check')
    op.create_check_constraint(
        'ck_edge_devices_credential_type', 'edge_devices', "credential_type IN ('shared_secret')"
    )
    op.drop_column('edge_devices', 'key_rotated_at')
    op.drop_column('edge_devices', 'key_fingerprint')
    op.drop_column('edge_devices', 'public_key_pem')
    op.alter_column('edge_devices', 'secret_hash', existing_type=sa.String(length=64), nullable=False)
