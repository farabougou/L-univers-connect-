"""backfill graph_nodes for existing rows (migrate)

Étape 2/3 (migrer) de l'ADR 012, étape F1 : enregistre dans le registre les
sites, positions fonctionnelles et exemplaires créés avant l'étape 1.

La RLS est forcée sur toutes ces tables, y compris pour le propriétaire : on
parcourt donc les tenants un par un en positionnant leur contexte, plutôt que
de désactiver la sécurité, même temporairement. Rejouable sans effet (ON
CONFLICT DO NOTHING).

Revision ID: 2c1a247ca272
Revises: 706eca882498
Create Date: 2026-09-23 14:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2c1a247ca272'
down_revision: Union[str, None] = '706eca882498'
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

                INSERT INTO graph_nodes (id, tenant_id, node_type)
                SELECT id, tenant_id, 'site' FROM sites
                ON CONFLICT (id) DO NOTHING;

                INSERT INTO graph_nodes (id, tenant_id, node_type)
                SELECT id, tenant_id, 'functional_location' FROM functional_locations
                ON CONFLICT (id) DO NOTHING;

                INSERT INTO graph_nodes (id, tenant_id, node_type)
                SELECT id, tenant_id, 'physical_unit' FROM physical_units
                ON CONFLICT (id) DO NOTHING;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )


def downgrade() -> None:
    # Rien à défaire ici : les nœuds disparaissent avec la table graph_nodes
    # lors du retour arrière de l'étape 1. Les supprimer ici casserait les
    # relations éventuellement créées entre-temps.
    pass
