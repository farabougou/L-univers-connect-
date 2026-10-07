"""signals: codes, certainty and separate axes for findings and alarms (expand)

ADR 013, étape L3, temps 1/3 (élargir). Nouvelles colonnes facultatives :
- constats : code de raison + paramètres (plus de phrase générée stockée),
  niveau de certitude, état de la condition, acquittement, traitement,
  indicateur « action requise », auteur et date de confirmation ;
- alarmes : état de la condition, acquittement, traitement ;
- historiques : champ concerné par chaque changement (`field`), la colonne
  `status` portant la nouvelle valeur ; les lignes anciennes restent telles
  quelles (field vide = ancien statut unique).
Gravité : niveau `major` ajouté (constats et alarmes).

Revision ID: 411cfe7c1b9a
Revises: c0b50f293eec
Create Date: 2026-09-24 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '411cfe7c1b9a'
down_revision: Union[str, None] = 'c0b50f293eec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AXES = ('condition_state', 'ack_state', 'handling_status')

_PROTECT_FINDING_V2 = """
CREATE OR REPLACE FUNCTION protect_finding() RETURNS trigger AS $$
BEGIN
    IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id
        OR NEW.subject_node_id <> OLD.subject_node_id
        OR NEW.point_id IS DISTINCT FROM OLD.point_id OR NEW.kind <> OLD.kind
        OR NEW.method <> OLD.method
        OR NEW.rule_config_version_id IS DISTINCT FROM OLD.rule_config_version_id
        OR NEW.dedup_key <> OLD.dedup_key OR NEW.severity <> OLD.severity
        OR NEW.title IS DISTINCT FROM OLD.title
        OR NEW.recommended_action IS DISTINCT FROM OLD.recommended_action
        OR NEW.confidence IS DISTINCT FROM OLD.confidence
        OR NEW.evidence <> OLD.evidence OR NEW.first_seen_at <> OLD.first_seen_at
        OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'findings : champ non modifiable sur la ligne %', OLD.id;
    END IF;
    -- Le code de raison et ses paramètres se renseignent une seule fois.
    IF OLD.reason_code IS NOT NULL AND (NEW.reason_code IS DISTINCT FROM OLD.reason_code
        OR NEW.reason_params IS DISTINCT FROM OLD.reason_params) THEN
        RAISE EXCEPTION 'findings : code de raison non modifiable sur la ligne %', OLD.id;
    END IF;
    -- Une confirmation humaine ne se défait pas et ne se réécrit pas.
    IF OLD.certainty = 'confirmed' AND (NEW.certainty IS DISTINCT FROM OLD.certainty
        OR NEW.confirmed_by IS DISTINCT FROM OLD.confirmed_by
        OR NEW.confirmed_at IS DISTINCT FROM OLD.confirmed_at) THEN
        RAISE EXCEPTION 'findings : confirmation non modifiable sur la ligne %', OLD.id;
    END IF;
    IF NEW.occurrence_count < OLD.occurrence_count
        OR NEW.last_seen_at < OLD.last_seen_at THEN
        RAISE EXCEPTION 'findings : compteur ou date en arrière sur la ligne %', OLD.id;
    END IF;
    IF (OLD.alarm_id IS NOT NULL AND NEW.alarm_id IS DISTINCT FROM OLD.alarm_id)
        OR (OLD.work_order_id IS NOT NULL
            AND NEW.work_order_id IS DISTINCT FROM OLD.work_order_id) THEN
        RAISE EXCEPTION 'findings : lien déjà établi sur la ligne %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

_PROTECT_FINDING_V1 = """
CREATE OR REPLACE FUNCTION protect_finding() RETURNS trigger AS $$
BEGIN
    IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id
        OR NEW.subject_node_id <> OLD.subject_node_id
        OR NEW.point_id IS DISTINCT FROM OLD.point_id OR NEW.kind <> OLD.kind
        OR NEW.method <> OLD.method
        OR NEW.rule_config_version_id IS DISTINCT FROM OLD.rule_config_version_id
        OR NEW.dedup_key <> OLD.dedup_key OR NEW.severity <> OLD.severity
        OR NEW.title <> OLD.title
        OR NEW.recommended_action IS DISTINCT FROM OLD.recommended_action
        OR NEW.confidence IS DISTINCT FROM OLD.confidence
        OR NEW.evidence <> OLD.evidence OR NEW.first_seen_at <> OLD.first_seen_at
        OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'findings : champ non modifiable sur la ligne %', OLD.id;
    END IF;
    IF NEW.occurrence_count < OLD.occurrence_count
        OR NEW.last_seen_at < OLD.last_seen_at THEN
        RAISE EXCEPTION 'findings : compteur ou date en arrière sur la ligne %', OLD.id;
    END IF;
    IF (OLD.alarm_id IS NOT NULL AND NEW.alarm_id IS DISTINCT FROM OLD.alarm_id)
        OR (OLD.work_order_id IS NOT NULL
            AND NEW.work_order_id IS DISTINCT FROM OLD.work_order_id) THEN
        RAISE EXCEPTION 'findings : lien déjà établi sur la ligne %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""


def upgrade() -> None:
    op.add_column('findings', sa.Column('reason_code', sa.String(length=80), nullable=True))
    op.add_column(
        'findings',
        sa.Column(
            'reason_params', postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"), nullable=False,
        ),
    )
    op.add_column('findings', sa.Column('certainty', sa.String(length=30), nullable=True))
    op.add_column('findings', sa.Column('action_required', sa.Boolean(), nullable=True))
    op.add_column('findings', sa.Column('confirmed_by', sa.String(length=200), nullable=True))
    op.add_column(
        'findings', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True)
    )
    for table in ('findings', 'alarms'):
        for axis in _AXES:
            op.add_column(table, sa.Column(axis, sa.String(length=20), nullable=True))
    for table in ('finding_status_history', 'alarm_status_history'):
        op.add_column(table, sa.Column('field', sa.String(length=30), nullable=True))

    op.drop_constraint('ck_findings_severity', 'findings', type_='check')
    op.create_check_constraint(
        'ck_findings_severity', 'findings', "severity IN ('info', 'warning', 'major', 'critical')"
    )
    op.create_check_constraint(
        'ck_alarms_severity', 'alarms', "severity IN ('info', 'warning', 'major', 'critical')"
    )
    op.execute(_PROTECT_FINDING_V2)


def downgrade() -> None:
    # Refusé si des données n'ont pas d'équivalent dans l'ancien modèle.
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                IF EXISTS (SELECT 1 FROM findings WHERE severity = 'major'
                           OR certainty = 'confirmed')
                    OR EXISTS (SELECT 1 FROM alarms WHERE severity = 'major')
                    OR EXISTS (SELECT 1 FROM finding_status_history WHERE field IS NOT NULL)
                    OR EXISTS (SELECT 1 FROM alarm_status_history WHERE field IS NOT NULL)
                THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des signalements utilisent le nouveau modèle '
                        '(tenant %). Décision explicite requise.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.execute(_PROTECT_FINDING_V1)
    op.drop_constraint('ck_alarms_severity', 'alarms', type_='check')
    op.drop_constraint('ck_findings_severity', 'findings', type_='check')
    op.create_check_constraint(
        'ck_findings_severity', 'findings', "severity IN ('info', 'warning', 'critical')"
    )
    for table in ('alarm_status_history', 'finding_status_history'):
        op.drop_column(table, 'field')
    for table in ('alarms', 'findings'):
        for axis in reversed(_AXES):
            op.drop_column(table, axis)
    for column in (
        'confirmed_at', 'confirmed_by', 'action_required', 'certainty', 'reason_params',
        'reason_code',
    ):
        op.drop_column('findings', column)
