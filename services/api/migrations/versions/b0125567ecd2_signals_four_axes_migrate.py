"""signals: fill codes, certainty and axes from the former single status (migrate)

ADR 013, étape L3, temps 2/3 (migrer), tenant par tenant (RLS forcée).

Correspondance de l'ancien statut unique :
    open            → active,  non acquitté, ouvert
    acknowledged    → active,  acquitté,     ouvert
    resolved        → revenu à la normale, acquitté, clos
    false_positive  → revenu à la normale, acquitté, faux positif
Constats : certitude « détecté » (« prédiction » pour les prédictions),
action requise sauf gravité « info », code de raison déduit de la clé de
déduplication (qualité, confiance, règle) avec ses paramètres. Les anciens
titres ne sont pas effacés (rien n'est écrasé) ; ils ne servent plus à
l'affichage des constats produits par le système.

Revision ID: b0125567ecd2
Revises: 411cfe7c1b9a
Create Date: 2026-09-24 08:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b0125567ecd2'
down_revision: Union[str, None] = '411cfe7c1b9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # « \\: » : deux-points littéral (sinon lu comme un paramètre de requête).
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);

                UPDATE findings f SET
                    condition_state = CASE f.status
                        WHEN 'resolved' THEN 'cleared' WHEN 'false_positive' THEN 'cleared'
                        ELSE 'active' END,
                    ack_state = CASE f.status
                        WHEN 'open' THEN 'unacknowledged' ELSE 'acknowledged' END,
                    handling_status = CASE f.status
                        WHEN 'resolved' THEN 'closed' WHEN 'false_positive' THEN 'false_positive'
                        ELSE 'open' END,
                    certainty = CASE f.kind WHEN 'prediction' THEN 'prediction' ELSE 'detected' END,
                    action_required = f.severity <> 'info',
                    reason_code = CASE
                        WHEN f.dedup_key LIKE 'quality:%\\:out_of_range' THEN 'DATA_QUALITY_OUT_OF_RANGE'
                        WHEN f.dedup_key LIKE 'quality:%\\:clock_suspect' THEN 'DATA_QUALITY_CLOCK_SUSPECT'
                        WHEN f.dedup_key LIKE 'quality:%\\:low_trust' THEN 'DATA_QUALITY_LOW_TRUST'
                        WHEN f.dedup_key LIKE 'rule:%' AND f.kind = 'fault'
                            THEN 'RULE_THRESHOLD_EXCEEDED'
                        WHEN f.dedup_key LIKE 'rule:%' THEN 'RULE_DESIRED_STATE_DIVERGENCE'
                        ELSE 'FINDING_UNCLASSIFIED' END,
                    reason_params = jsonb_strip_nulls(jsonb_build_object(
                        'point_code', (SELECT p.code FROM points p WHERE p.id = f.point_id),
                        'score', f.evidence -> 'trust' -> 'score',
                        'value', f.evidence -> 'value',
                        'operator', f.evidence -> 'operator',
                        'threshold', f.evidence -> 'threshold',
                        'actual', f.evidence -> 'actual',
                        'desired', f.evidence -> 'desired'))
                WHERE f.condition_state IS NULL;

                UPDATE alarms SET
                    condition_state = CASE status WHEN 'resolved' THEN 'cleared' ELSE 'active' END,
                    ack_state = CASE status WHEN 'open' THEN 'unacknowledged'
                        ELSE 'acknowledged' END,
                    handling_status = CASE status WHEN 'resolved' THEN 'closed' ELSE 'open' END
                WHERE condition_state IS NULL;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )


def downgrade() -> None:
    # Rien à défaire : les colonnes remplies ici disparaissent avec le retour
    # arrière de l'étape « élargir », et l'ancien statut n'a pas été modifié.
    pass
