"""telemetry v2: point-based key, drop legacy columns (contract)

Étape 3/3 (contracter) de l'ADR 012, étape F3. Chaque mesure appartient
désormais à un point. Clé primaire (point, date du relevé) : un relevé
renvoyé deux fois après une coupure Edge n'est jamais dupliqué, et cette clé
est compatible avec TimescaleDB (M3). Les anciennes colonnes (grandeur, unité,
position) vivent maintenant sur le point.

Retour arrière : reconstruit les anciennes colonnes à partir des points.
Limite assumée : l'ancien `physical_unit_id` d'une mesure n'est pas restauré
(les points se rattachent à des positions, pas à des exemplaires) ; seules des
données de simulation M2 sont concernées.

Revision ID: f688f24c2cd4
Revises: 5c9ace67b099
Create Date: 2026-09-23 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f688f24c2cd4'
down_revision: Union[str, None] = '5c9ace67b099'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('measurements', 'point_id', nullable=False)
    op.alter_column('measurements', 'origin', nullable=False)
    op.alter_column(
        'measurements', 'received_at', nullable=False, server_default=sa.text('now()')
    )
    op.alter_column('measurements', 'source', server_default=None)
    op.create_check_constraint(
        'ck_measurements_origin',
        'measurements',
        "origin IN ('measured', 'manual', 'derived', 'estimated', 'simulated')",
    )

    op.drop_index('ix_measurements_functional_location_id_measured_at', table_name='measurements')
    op.drop_constraint('measurements_pkey', 'measurements', type_='primary')
    op.create_primary_key('measurements_pkey', 'measurements', ['point_id', 'measured_at'])
    op.create_foreign_key(
        'fk_measurements_point',
        'measurements',
        'points',
        ['tenant_id', 'point_id'],
        ['tenant_id', 'id'],
    )

    for column in ('id', 'functional_location_id', 'physical_unit_id', 'metric', 'unit',
                   'created_at'):
        op.drop_column('measurements', column)


def downgrade() -> None:
    op.add_column('measurements', sa.Column('id', sa.UUID(), nullable=True))
    op.add_column('measurements', sa.Column('functional_location_id', sa.UUID(), nullable=True))
    op.add_column('measurements', sa.Column('physical_unit_id', sa.UUID(), nullable=True))
    op.add_column('measurements', sa.Column('metric', sa.String(length=100), nullable=True))
    op.add_column('measurements', sa.Column('unit', sa.String(length=20), nullable=True))
    op.add_column(
        'measurements', sa.Column('created_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                UPDATE measurements m
                SET id = gen_random_uuid(),
                    functional_location_id = p.functional_location_id,
                    metric = p.name,
                    unit = coalesce(p.unit, ''),
                    created_at = m.received_at
                FROM points p WHERE p.id = m.point_id;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.alter_column('measurements', 'id', nullable=False)
    op.alter_column('measurements', 'metric', nullable=False)
    op.alter_column('measurements', 'unit', nullable=False)
    op.alter_column(
        'measurements', 'created_at', nullable=False, server_default=sa.text('now()')
    )

    op.drop_constraint('fk_measurements_point', 'measurements', type_='foreignkey')
    op.drop_constraint('measurements_pkey', 'measurements', type_='primary')
    op.create_primary_key('measurements_pkey', 'measurements', ['id'])
    op.create_foreign_key(
        None, 'measurements', 'functional_locations', ['functional_location_id'], ['id']
    )
    op.create_foreign_key(None, 'measurements', 'physical_units', ['physical_unit_id'], ['id'])
    op.create_index(
        'ix_measurements_functional_location_id_measured_at',
        'measurements',
        ['functional_location_id', 'measured_at'],
    )

    op.drop_constraint('ck_measurements_origin', 'measurements', type_='check')
    op.alter_column('measurements', 'source', server_default='simulator')
    op.alter_column('measurements', 'received_at', nullable=True, server_default=None)
    op.alter_column('measurements', 'origin', nullable=True)
    op.alter_column('measurements', 'point_id', nullable=True)
