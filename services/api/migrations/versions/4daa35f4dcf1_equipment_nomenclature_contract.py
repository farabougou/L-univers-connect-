"""equipment nomenclature: type required, free-text category retired (contract)

ADR 013, étape L5, temps 3/3 (contracter) : le type universel devient
obligatoire ; l'ancienne catégorie libre est retirée, son contenu étant
intégralement conservé dans `manufacturer_designation` (étape 2). Le retour
arrière la reconstruit. Aucune base de production n'existe encore.

Revision ID: 4daa35f4dcf1
Revises: 6c1d9fbc55fb
Create Date: 2026-09-24 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4daa35f4dcf1'
down_revision: Union[str, None] = '6c1d9fbc55fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('product_models', 'equipment_type', nullable=False)
    op.drop_column('product_models', 'category')


def downgrade() -> None:
    op.add_column('product_models', sa.Column('category', sa.String(length=100), nullable=True))
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                UPDATE product_models
                SET category = LEFT(COALESCE(manufacturer_designation, equipment_type), 100);
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.alter_column('product_models', 'category', nullable=False)
    op.alter_column('product_models', 'equipment_type', nullable=True)
