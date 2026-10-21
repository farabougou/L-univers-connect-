"""add sync feed support

Consolidation V5 (21/10/2026) : synchronisation incrémentale du mobile
(app/sync_feed.py). Aujourd'hui l'application télécharge TOUTES les
interventions (35 Mo à 100 000 lignes, mesuré) et TOUS les équipements à chaque
synchronisation : inutilisable sur une connexion faible.

Pour ne transmettre que ce qui a changé depuis la dernière synchronisation, il
faut savoir QUAND un équipement a changé. Une intervention n'est jamais
modifiée ni supprimée par l'application (`created_at` suffit). Un équipement,
lui, est archivé puis désarchivé (`archived_at`, remis à NULL : aucune trace de
l'événement) et peut changer d'espace : il lui faut une date de dernière
modification.

Uniquement additif (phase « élargir » de la règle des trois temps) :
- `functional_locations.updated_at`, valeur par défaut `clock_timestamp()`
  (l'heure réelle, pas celle du début de la transaction) ; les équipements
  existants reçoivent l'heure de cette migration, ce qui n'a aucune conséquence
  (aucun téléphone ne détient encore de point de reprise) ;
- un déclencheur qui la met à jour à chaque modification, de sorte qu'aucun code
  applicatif présent ou futur ne puisse l'oublier ;
- deux index de parcours par curseur `(tenant_id, date, id)`.
Aucune requête existante n'est modifiée.

Revision ID: e7b2d9c41a68
Revises: c8e5a2f94b16
Create Date: 2026-10-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e7b2d9c41a68'
down_revision: Union[str, None] = 'c8e5a2f94b16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = (
    ('ix_interventions_tenant_created_id', 'interventions', 'tenant_id, created_at, id'),
    ('ix_functional_locations_tenant_updated_id', 'functional_locations', 'tenant_id, updated_at, id'),
)


def upgrade() -> None:
    op.execute(
        'ALTER TABLE functional_locations '
        'ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT clock_timestamp()'
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION paios_touch_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at := clock_timestamp();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute('DROP TRIGGER IF EXISTS functional_locations_touch_updated_at ON functional_locations')
    op.execute(
        """
        CREATE TRIGGER functional_locations_touch_updated_at
        BEFORE UPDATE ON functional_locations
        FOR EACH ROW EXECUTE FUNCTION paios_touch_updated_at()
        """
    )
    with op.get_context().autocommit_block():
        for name, table, columns in _INDEXES:
            op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS {name}')
            op.execute(f'CREATE INDEX CONCURRENTLY {name} ON {table} ({columns})')


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, _table, _columns in _INDEXES:
            op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS {name}')
    op.execute('DROP TRIGGER IF EXISTS functional_locations_touch_updated_at ON functional_locations')
    op.execute('DROP FUNCTION IF EXISTS paios_touch_updated_at()')
    op.execute('ALTER TABLE functional_locations DROP COLUMN IF EXISTS updated_at')
