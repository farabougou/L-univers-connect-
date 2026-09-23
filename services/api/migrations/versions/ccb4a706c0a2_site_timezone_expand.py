"""add site time zone (expand only)

ADR 013, étape L4 : l'heure d'un site s'affiche dans son fuseau (IANA).
Élargir seulement : colonne facultative. Les sites existants ne reçoivent
aucun fuseau deviné (« ne jamais inventer une certitude ») ; l'API l'exige
pour tout nouveau site et permet de le renseigner pour les anciens.

Revision ID: ccb4a706c0a2
Revises: ddbfca2ccdde
Create Date: 2026-09-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ccb4a706c0a2'
down_revision: Union[str, None] = 'ddbfca2ccdde'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sites', sa.Column('timezone', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                IF EXISTS (SELECT 1 FROM sites WHERE timezone IS NOT NULL) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des sites ont un fuseau horaire (tenant %). '
                        'Décision explicite requise.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.drop_column('sites', 'timezone')
