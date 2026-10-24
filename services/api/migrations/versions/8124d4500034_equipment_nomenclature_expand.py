"""equipment nomenclature: universal type, manufacturer designation, asset code (expand)

ADR 013, étape L5, temps 1/3 (élargir) :
- modèles : type universel d'équipement et désignation du fabricant ;
- exemplaires : code d'inventaire du client, unique par client s'il existe.

Revision ID: 8124d4500034
Revises: ccb4a706c0a2
Create Date: 2026-09-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8124d4500034'
down_revision: Union[str, None] = 'ccb4a706c0a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product_models', sa.Column('equipment_type', sa.String(length=40), nullable=True))
    op.add_column(
        'product_models', sa.Column('manufacturer_designation', sa.String(length=200), nullable=True)
    )
    op.add_column('physical_units', sa.Column('asset_code', sa.String(length=100), nullable=True))
    op.create_index(
        'uq_physical_units_tenant_asset_code', 'physical_units', ['tenant_id', 'asset_code'],
        unique=True, postgresql_where=sa.text('asset_code IS NOT NULL'),
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
                IF EXISTS (SELECT 1 FROM physical_units WHERE asset_code IS NOT NULL) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des codes d''inventaire existent (tenant %). '
                        'Décision explicite requise.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.drop_index('uq_physical_units_tenant_asset_code', table_name='physical_units')
    op.drop_column('physical_units', 'asset_code')
    op.drop_column('product_models', 'manufacturer_designation')
    op.drop_column('product_models', 'equipment_type')
