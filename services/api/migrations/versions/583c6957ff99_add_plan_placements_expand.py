"""add plan placements expand

ADR 011, étape S4 : « tel espace / telle position / tel point est dessiné
ici sur telle version de plan ». Trois colonnes de référence facultatives
avec une contrainte « exactement une renseignée », de vraies clés
étrangères (impossible de pointer vers un actif inexistant ou d'un autre
tenant). Coordonnées normalisées (0 à 1) : indépendantes de la résolution
de l'image, portables si le plan change de format.

Statut proposé/validé (voir ADR 011, ordre de mise en œuvre) : contrairement
aux preuves déjà protégées en base (audit_log, config_versions,
intervention_closures, floor_plans...), un placement décrit une position
d'affichage, pas un fait opérationnel de l'actif lui-même (qui reste
entièrement dans functional_locations/points/spaces, inchangés) — il reste
donc modifiable et supprimable normalement, tracé par le journal d'audit
comme les autres actions de gestion du registre.

Revision ID: 583c6957ff99
Revises: f65006c6d8c7
Create Date: 2026-09-26 21:18:25.259688

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '583c6957ff99'
down_revision: Union[str, None] = 'f65006c6d8c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # floor_plans n'avait pas encore besoin d'être référencée par une autre
    # table : lui ajouter la contrainte (tenant_id, id) habituelle, requise
    # pour la clé étrangère composite ci-dessous.
    op.create_unique_constraint(
        'uq_floor_plans_tenant_id_id', 'floor_plans', ['tenant_id', 'id']
    )

    op.create_table(
        'plan_placements',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('floor_plan_id', sa.UUID(), nullable=False),
        sa.Column('space_id', sa.UUID(), nullable=True),
        sa.Column('functional_location_id', sa.UUID(), nullable=True),
        sa.Column('point_id', sa.UUID(), nullable=True),
        sa.Column('x_ratio', sa.Numeric(5, 4), nullable=False),
        sa.Column('y_ratio', sa.Numeric(5, 4), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='proposed', nullable=False),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('validated_by', sa.String(length=200), nullable=True),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'floor_plan_id'], ['floor_plans.tenant_id', 'floor_plans.id'],
            name='fk_plan_placements_floor_plan',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'space_id'], ['spaces.tenant_id', 'spaces.id'],
            name='fk_plan_placements_space',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'functional_location_id'],
            ['functional_locations.tenant_id', 'functional_locations.id'],
            name='fk_plan_placements_functional_location',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'point_id'], ['points.tenant_id', 'points.id'],
            name='fk_plan_placements_point',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('x_ratio >= 0 AND x_ratio <= 1', name='ck_plan_placements_x_ratio'),
        sa.CheckConstraint('y_ratio >= 0 AND y_ratio <= 1', name='ck_plan_placements_y_ratio'),
        sa.CheckConstraint(
            "status IN ('proposed', 'validated')", name='ck_plan_placements_status'
        ),
        sa.CheckConstraint(
            "(status = 'validated') = (validated_at IS NOT NULL)",
            name='ck_plan_placements_validation',
        ),
        sa.CheckConstraint(
            "(space_id IS NOT NULL)::int + (functional_location_id IS NOT NULL)::int "
            "+ (point_id IS NOT NULL)::int = 1",
            name='ck_plan_placements_exactly_one_target',
        ),
    )
    op.create_index('ix_plan_placements_floor_plan_id', 'plan_placements', ['floor_plan_id'])

    op.execute("ALTER TABLE plan_placements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE plan_placements FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON plan_placements
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON plan_placements")
    op.execute("ALTER TABLE plan_placements NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE plan_placements DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_plan_placements_floor_plan_id', table_name='plan_placements')
    op.drop_table('plan_placements')
    op.drop_constraint('uq_floor_plans_tenant_id_id', 'floor_plans', type_='unique')
