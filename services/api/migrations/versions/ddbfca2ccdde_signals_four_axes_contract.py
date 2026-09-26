"""signals: make the new axes mandatory and retire the single status (contract)

ADR 013, étape L3, temps 3/3 (contracter).
- Colonnes obligatoires et vocabulaires contrôlés par la base.
- Une confirmation exige une personne (jamais un compte système) et une
  prédiction ne peut jamais être confirmée.
- Un constat de règle garde le titre écrit par son auteur ; les constats du
  système n'en stockent plus (code + paramètres, traduits à l'affichage).
- Un seul constat en traitement par problème (index sur `handling_status`).
- Retrait de l'ancien statut unique : son contenu est intégralement porté par
  les trois axes (étape 2) et le retour arrière le reconstruit. Aucune base
  de production n'existe encore (rien n'est déployé avant M1).

Revision ID: ddbfca2ccdde
Revises: b0125567ecd2
Create Date: 2026-09-24 08:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ddbfca2ccdde'
down_revision: Union[str, None] = 'b0125567ecd2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CERTAINTIES = (
    'detected', 'confirmed', 'probable_cause', 'hypothesis', 'prediction', 'recommendation',
    'simulation_result', 'unavailable',
)
HISTORY_FIELDS = ('condition_state', 'ack_state', 'handling_status', 'certainty')


def _in(values) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    for table in ('findings', 'alarms'):
        op.alter_column(table, 'condition_state', nullable=False, server_default='active')
        op.alter_column(table, 'ack_state', nullable=False, server_default='unacknowledged')
        op.alter_column(table, 'handling_status', nullable=False, server_default='open')
        op.create_check_constraint(
            f'ck_{table}_condition_state', table, "condition_state IN ('active', 'cleared')"
        )
        op.create_check_constraint(
            f'ck_{table}_ack_state', table, "ack_state IN ('unacknowledged', 'acknowledged')"
        )
        op.create_check_constraint(
            f'ck_{table}_handling_status', table,
            "handling_status IN ('open', 'in_progress', 'closed', 'false_positive')",
        )
    op.alter_column('findings', 'reason_code', nullable=False)
    op.alter_column('findings', 'certainty', nullable=False)
    op.alter_column('findings', 'action_required', nullable=False)
    op.alter_column('findings', 'title', nullable=True)
    op.create_check_constraint(
        'ck_findings_certainty', 'findings', f"certainty IN ({_in(CERTAINTIES)})"
    )
    op.create_check_constraint(
        'ck_findings_confirmation', 'findings',
        "certainty <> 'confirmed' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL "
        "AND confirmed_by NOT LIKE 'systeme:%')",
    )
    op.create_check_constraint(
        'ck_findings_prediction_never_confirmed', 'findings',
        "NOT (kind = 'prediction' AND certainty = 'confirmed')",
    )
    op.create_check_constraint(
        'ck_findings_rule_title', 'findings', "reason_code NOT LIKE 'RULE\\_%' OR title IS NOT NULL"
    )
    for table in ('finding_status_history', 'alarm_status_history'):
        op.create_check_constraint(
            f'ck_{table}_field', table, f"field IS NULL OR field IN ({_in(HISTORY_FIELDS)})"
        )

    op.drop_index('uq_findings_one_open', table_name='findings')
    op.create_index(
        'uq_findings_one_open', 'findings', ['tenant_id', 'dedup_key'], unique=True,
        postgresql_where=sa.text("handling_status IN ('open', 'in_progress')"),
    )
    op.drop_constraint('ck_findings_status', 'findings', type_='check')
    op.drop_column('findings', 'status')
    op.drop_column('alarms', 'status')


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                IF EXISTS (SELECT 1 FROM findings WHERE title IS NULL) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des constats sans titre stocké existent '
                        '(tenant %). Décision explicite requise.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    for table in ('findings', 'alarms'):
        op.add_column(table, sa.Column('status', sa.String(length=20), nullable=True))
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                UPDATE findings SET status = CASE
                    WHEN handling_status = 'false_positive' THEN 'false_positive'
                    WHEN handling_status = 'closed' THEN 'resolved'
                    WHEN ack_state = 'acknowledged' THEN 'acknowledged'
                    ELSE 'open' END;
                UPDATE alarms SET status = CASE
                    WHEN handling_status IN ('closed', 'false_positive') THEN 'resolved'
                    WHEN ack_state = 'acknowledged' THEN 'acknowledged'
                    ELSE 'open' END;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.alter_column('findings', 'status', nullable=False, server_default='open')
    op.alter_column('alarms', 'status', nullable=False, server_default='open')
    op.create_check_constraint(
        'ck_findings_status', 'findings',
        "status IN ('open', 'acknowledged', 'resolved', 'false_positive')",
    )
    op.drop_index('uq_findings_one_open', table_name='findings')
    op.create_index(
        'uq_findings_one_open', 'findings', ['tenant_id', 'dedup_key'], unique=True,
        postgresql_where=sa.text("status IN ('open', 'acknowledged')"),
    )
    for table in ('alarm_status_history', 'finding_status_history'):
        op.drop_constraint(f'ck_{table}_field', table, type_='check')
    for name in (
        'ck_findings_rule_title', 'ck_findings_prediction_never_confirmed',
        'ck_findings_confirmation', 'ck_findings_certainty',
    ):
        op.drop_constraint(name, 'findings', type_='check')
    op.alter_column('findings', 'title', nullable=False)
    op.alter_column('findings', 'action_required', nullable=True)
    op.alter_column('findings', 'certainty', nullable=True)
    op.alter_column('findings', 'reason_code', nullable=True)
    for table in ('alarms', 'findings'):
        for axis in ('handling_status', 'ack_state', 'condition_state'):
            op.drop_constraint(f'ck_{table}_{axis}', table, type_='check')
            op.alter_column(table, axis, nullable=True, server_default=None)
