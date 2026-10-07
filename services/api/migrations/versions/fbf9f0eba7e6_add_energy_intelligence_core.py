"""add energy intelligence core

M5, brique de référence énergétique et de normalisation météorologique
(décision de Mohamed du 24/09/2026). Moteur interne, séparé de toute
réglementation (OPERAT, BACS, ESG à venir) — voir app/energy/. La référence
énergétique elle-même n'a pas de table dédiée : c'est une configuration
versionnée de plus (config_type "energy_baseline", ADR 012 §2.11), pour
réutiliser l'audit, l'activation et l'historique déjà en place.

Deux tables nouvelles, élargir seulement :
- `weather_observations` : température moyenne quotidienne par site, saisie
  manuellement pour la V1 (aucune intégration météo externe pour l'instant) ;
  les degrés-jours sont dérivés à la lecture (la température de base dépend
  de la référence énergétique, jamais figée dans la donnée météo elle-même).
- `energy_normalized_results` : un résultat de calcul, jamais modifié ni
  supprimé (même principe que les constats et le journal d'audit), avec la
  traçabilité complète demandée : période de référence et analysée (via la
  version de configuration + les colonnes propres), consommation brute et
  son origine, données météo utilisées, méthode et sa version, paramètres,
  données manquantes, qualité, résultat normalisé, date et auteur du calcul.

Revision ID: fbf9f0eba7e6
Revises: 59e74fed4108
Create Date: 2026-09-24 22:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbf9f0eba7e6'
down_revision: Union[str, None] = '59e74fed4108'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WEATHER_POLICY = """
    CREATE POLICY tenant_isolation ON weather_observations
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""
_RESULTS_POLICY = """
    CREATE POLICY tenant_isolation ON energy_normalized_results
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def upgrade() -> None:
    op.create_table(
        'weather_observations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('site_id', sa.UUID(), nullable=False),
        sa.Column('observed_date', sa.Date(), nullable=False),
        sa.Column('mean_temperature_celsius', sa.Float(), nullable=False),
        # "manual" seule valeur pour la V1 : aucune intégration météo externe
        # n'est prévue tant que le moteur interne n'est pas éprouvé.
        sa.Column('source', sa.String(length=30), nullable=False, server_default='manual'),
        sa.Column('station_ref', sa.String(length=200), nullable=True),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'site_id'], ['sites.tenant_id', 'sites.id'], name='fk_weather_observations_site'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'site_id', 'observed_date', name='uq_weather_observations_site_date'
        ),
        sa.CheckConstraint("source IN ('manual')", name='ck_weather_observations_source'),
    )
    op.execute("ALTER TABLE weather_observations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE weather_observations FORCE ROW LEVEL SECURITY")
    op.execute(_WEATHER_POLICY)

    op.create_table(
        'energy_normalized_results',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('functional_location_id', sa.UUID(), nullable=False),
        sa.Column('point_id', sa.UUID(), nullable=False),
        sa.Column('baseline_config_version_id', sa.UUID(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        # Copiés depuis la version de configuration au moment du calcul :
        # une défense de plus pour rester explicable même si l'interprétation
        # du contenu venait à évoluer (le contenu de la version, lui, ne
        # change jamais).
        sa.Column('method', sa.String(length=50), nullable=False),
        sa.Column('method_version', sa.String(length=20), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('raw_consumption', sa.Float(), nullable=False),
        sa.Column('raw_consumption_unit', sa.String(length=20), nullable=False),
        sa.Column('measurement_count', sa.Integer(), nullable=False),
        sa.Column('data_completeness', sa.Float(), nullable=True),
        sa.Column('quality_flags', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('degree_days', sa.Float(), nullable=True),
        sa.Column('degree_day_base_temperature_celsius', sa.Float(), nullable=True),
        sa.Column('degree_day_kind', sa.String(length=10), nullable=True),
        sa.Column('weather_source', sa.String(length=30), nullable=True),
        sa.Column('weather_days_missing', sa.Integer(), nullable=True),
        sa.Column('normalization_status', sa.String(length=30), nullable=False),
        sa.Column('normalized_consumption', sa.Float(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('computed_by', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'functional_location_id'],
            ['functional_locations.tenant_id', 'functional_locations.id'],
            name='fk_energy_results_functional_location',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'point_id'], ['points.tenant_id', 'points.id'], name='fk_energy_results_point'
        ),
        sa.ForeignKeyConstraint(
            ['baseline_config_version_id'], ['config_versions.id'], name='fk_energy_results_baseline'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("degree_day_kind IN ('heating', 'cooling')", name='ck_energy_results_dd_kind'),
        sa.CheckConstraint(
            "normalization_status IN ('ok', 'no_weather_data', 'zero_degree_days')",
            name='ck_energy_results_normalization_status',
        ),
        sa.CheckConstraint(
            "(normalization_status = 'ok') = (normalized_consumption IS NOT NULL)",
            name='ck_energy_results_normalized_consistent',
        ),
    )
    op.create_index(
        'ix_energy_results_location_period',
        'energy_normalized_results',
        ['functional_location_id', 'period_start'],
    )
    op.create_index(
        'ix_energy_results_baseline', 'energy_normalized_results', ['baseline_config_version_id']
    )
    op.execute("ALTER TABLE energy_normalized_results ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE energy_normalized_results FORCE ROW LEVEL SECURITY")
    op.execute(_RESULTS_POLICY)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON energy_normalized_results")
    op.execute("ALTER TABLE energy_normalized_results NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE energy_normalized_results DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_energy_results_baseline', table_name='energy_normalized_results')
    op.drop_index('ix_energy_results_location_period', table_name='energy_normalized_results')
    op.drop_table('energy_normalized_results')

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON weather_observations")
    op.execute("ALTER TABLE weather_observations NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE weather_observations DISABLE ROW LEVEL SECURITY")
    op.drop_table('weather_observations')
