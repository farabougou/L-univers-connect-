"""backfill physical unit lifecycle state (migrate)

Étape 2/3 (migrer) de l'ADR 012, étape F5 : chaque exemplaire existant
reçoit son état de cycle de vie, déduit de ses affectations : « installed »
s'il occupe actuellement une position, sinon « in_stock ». Aucun événement
d'historique n'est inventé pour le passé : l'historique commence ici.

Revision ID: 120f0277be56
Revises: a4a1fa8a4cfa
Create Date: 2026-09-23 22:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '120f0277be56'
down_revision: Union[str, None] = 'a4a1fa8a4cfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                UPDATE physical_units u
                SET lifecycle_state = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM functional_location_assignments a
                        WHERE a.physical_unit_id = u.id AND a.valid_to IS NULL
                    ) THEN 'installed'
                    ELSE 'in_stock'
                END
                WHERE u.lifecycle_state IS NULL;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )


def downgrade() -> None:
    # Rien à défaire : la colonne disparaît au retour arrière de l'étape 1.
    pass
