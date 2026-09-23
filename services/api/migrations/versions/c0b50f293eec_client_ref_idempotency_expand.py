"""add client_ref idempotency keys to interventions and photos (expand)

Élargir seulement : une référence facultative fournie par le client (le
téléphone envoie l'identifiant local de sa file d'attente), unique par tenant.
Un renvoi après une réponse perdue ne crée plus de doublon.

Pas d'étape « migrer » ni « contracter » : les lignes existantes gardent une
référence vide, ce qui est exact (créées avant ce mécanisme), et la colonne
reste facultative pour les clients qui ne rejouent jamais (application web).
PostgreSQL accepte plusieurs valeurs vides dans une contrainte d'unicité.

Revision ID: c0b50f293eec
Revises: 11d319d9d849
Create Date: 2026-09-23 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0b50f293eec'
down_revision: Union[str, None] = '11d319d9d849'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ('interventions', 'intervention_photos')


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column('client_ref', sa.String(length=100), nullable=True))
        op.create_unique_constraint(
            f'uq_{table}_tenant_client_ref', table, ['tenant_id', 'client_ref']
        )


def downgrade() -> None:
    # Retirer la colonne ferait perdre la protection contre les doublons des
    # envois déjà reçus : refusé dès qu'une référence existe. La boucle passe
    # tenant par tenant, car la RLS forcée cache les lignes sans contexte.
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                IF EXISTS (SELECT 1 FROM interventions WHERE client_ref IS NOT NULL)
                    OR EXISTS (SELECT 1 FROM intervention_photos WHERE client_ref IS NOT NULL)
                THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des références client existent (tenant %). '
                        'Décision explicite requise.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    for table in reversed(_TABLES):
        op.drop_constraint(f'uq_{table}_tenant_client_ref', table, type_='unique')
        op.drop_column(table, 'client_ref')
