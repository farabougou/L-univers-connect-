"""attach existing measurements to points (migrate)

Étape 2/3 (migrer) de l'ADR 012, étape F3. Chaque mesure existante (données
du simulateur M2) est rattachée à un point créé pour elle : un point par
couple (position fonctionnelle, grandeur, unité), à l'état « proposed »
(à identifier puis valider, comme tout point découvert). Origine : `simulated`
si la source était le simulateur, sinon `measured`.

Aucune donnée n'est supprimée. Si deux mesures d'un même point portent la
même date, la migration s'arrête plutôt que d'en choisir une : c'est à un
humain de décider (règle non négociable 6).

Revision ID: 5c9ace67b099
Revises: fa9d56ea8263
Create Date: 2026-09-23 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5c9ace67b099'
down_revision: Union[str, None] = 'fa9d56ea8263'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Code du point dérivé de façon stable de (position, grandeur, unité).
_LEGACY_KEY = (
    "'legacy-' || substr(md5(coalesce({fl}::text, '-') || '|' || {metric} || '|' || {unit}), 1, 16)"
)


def upgrade() -> None:
    point_code = _LEGACY_KEY.format(fl="m.functional_location_id", metric="m.metric", unit="m.unit")
    op.execute(
        f"""
        DO $$
        DECLARE
            t record;
            duplicates integer;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);

                INSERT INTO points (id, tenant_id, functional_location_id, code, name,
                                    value_type, unit, mapping_status, created_by)
                SELECT DISTINCT ON ({point_code})
                    gen_random_uuid(), m.tenant_id, m.functional_location_id,
                    {point_code}, m.metric, 'number',
                    CASE m.unit
                        WHEN '°C' THEN 'Cel'
                        WHEN 'ppm' THEN '[ppm]'
                        WHEN 'kWh' THEN 'kW.h'
                        ELSE m.unit
                    END,
                    'proposed', 'migration-f3'
                FROM measurements m
                WHERE m.point_id IS NULL
                ON CONFLICT (tenant_id, code) DO NOTHING;

                UPDATE measurements m
                SET point_id = p.id,
                    origin = CASE WHEN m.source = 'simulator' THEN 'simulated' ELSE 'measured' END,
                    received_at = m.created_at
                FROM points p
                WHERE m.point_id IS NULL AND p.code = {point_code};

                SELECT count(*) INTO duplicates FROM (
                    SELECT point_id, measured_at FROM measurements
                    GROUP BY point_id, measured_at HAVING count(*) > 1
                ) d;
                IF duplicates > 0 THEN
                    RAISE EXCEPTION
                        'migration F3 arrêtée : % mesures en double (même point, même date) '
                        'pour le tenant %. Décision humaine requise.', duplicates, t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
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
                UPDATE measurements SET point_id = NULL, origin = NULL, received_at = NULL
                WHERE point_id IN (SELECT id FROM points WHERE created_by = 'migration-f3');
                DELETE FROM points WHERE created_by = 'migration-f3';
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
