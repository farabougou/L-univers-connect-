"""add functional_locations.archived_with_site (expand)

Décision de Mohamed du 23/10/2026 : archiver un site archive aussi ses équipements.
Constat sur le staging : trois équipements étaient restés actifs sur des sites archivés.

Le désarchivage d'un site ne doit remettre en service que les équipements archivés AVEC
lui, jamais ceux qu'une personne avait archivés elle-même (elle ne voulait peut-être pas les
voir revenir). Il faut donc retenir la cause de l'archivage d'un équipement : une colonne
booléenne explicite, plutôt qu'une égalité de dates qui laisserait ce lien implicite et fragile.

Temps 1/3 (élargir), uniquement additif :
- `archived_with_site`, faux par défaut : tous les équipements existants gardent leur état ;
- une contrainte qui interdit « archivé avec le site » pour un équipement qui n'est pas archivé,
  de sorte qu'aucun code présent ou futur ne puisse laisser un indicateur sans archivage.
Aucune requête existante n'est modifiée. Le temps 2/3 (migrer) range les équipements restés
actifs sur des sites archivés.

Revision ID: d4b7e91a3c52
Revises: e7b2d9c41a68
Create Date: 2026-10-23 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4b7e91a3c52'
down_revision: Union[str, None] = 'e7b2d9c41a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = 'functional_locations_archived_with_site_needs_archived_at'


def upgrade() -> None:
    op.execute(
        'ALTER TABLE functional_locations '
        'ADD COLUMN IF NOT EXISTS archived_with_site boolean NOT NULL DEFAULT false'
    )
    op.execute(
        f'ALTER TABLE functional_locations ADD CONSTRAINT {_CONSTRAINT} '
        'CHECK (NOT archived_with_site OR archived_at IS NOT NULL)'
    )


def downgrade() -> None:
    op.execute(f'ALTER TABLE functional_locations DROP CONSTRAINT IF EXISTS {_CONSTRAINT}')
    op.execute('ALTER TABLE functional_locations DROP COLUMN IF EXISTS archived_with_site')
