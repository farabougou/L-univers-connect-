"""add fgas intervention records

Fiche d'intervention fluides frigorigènes fluorés (CERFA 15497*04, articles
R. 543-79 et R. 543-82 du code de l'environnement) — document fourni par
Mohamed le 02/10/2026, qui débloque la ligne « Documents réglementaires »
de docs/spec/feature-benchmark-matrix.md (`DEFERRED_DOCUMENT`).

Une fiche est une preuve légale : enregistrée une fois, jamais modifiée ni
supprimée (mêmes déclencheurs forbid_update/forbid_delete que
intervention_closures et documents), le détenteur devant en conserver
l'original au moins 5 ans. Rattachée à une intervention existante (comme
intervention_closures), une seule fiche par intervention.

Toutes les identités (opérateur, détenteur, équipement, fluide) sont
enregistrées en texte au moment de la signature, jamais une référence vivante
vers une ligne qui pourrait changer plus tard (un nom de site renommé ne doit
jamais modifier un document déjà signé).

Le tonnage équivalent CO2 ([3] du CERFA) reste une saisie manuelle : son
calcul exigerait une table officielle de PRG (pouvoir de réchauffement
global) vérifiée, que ce document ne fournit pas — voir app/properties.py,
même réserve déjà posée pour les propriétés techniques F-Gas.

Revision ID: adce8b5d46b8
Revises: b1d4f2a9c7e3
Create Date: 2026-10-02 11:40:04.411520

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'adce8b5d46b8'
down_revision: Union[str, None] = 'b1d4f2a9c7e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fgas_intervention_records',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('intervention_id', sa.UUID(), nullable=False),
        sa.Column('fiche_number', sa.String(length=50), nullable=True),
        # [1] Opérateur
        sa.Column('operator_name', sa.String(length=300), nullable=False),
        sa.Column('operator_address', sa.String(length=500), nullable=True),
        sa.Column('operator_siret', sa.String(length=20), nullable=True),
        sa.Column('operator_capacity_number', sa.String(length=100), nullable=True),
        # [2] Détenteur
        sa.Column('detenteur_name', sa.String(length=300), nullable=False),
        sa.Column('detenteur_address', sa.String(length=500), nullable=True),
        sa.Column('detenteur_siret', sa.String(length=20), nullable=True),
        # [3] Équipement concerné
        sa.Column('equipment_identification', sa.String(length=300), nullable=False),
        sa.Column('refrigerant_name', sa.String(length=100), nullable=False),
        sa.Column('total_charge_kg', sa.Float(), nullable=False),
        sa.Column('co2_equivalent_tonnes', sa.Float(), nullable=True),
        # [4] Nature de l'intervention (une ou plusieurs cases)
        sa.Column('nature_of_intervention', postgresql.JSONB(), nullable=False),
        sa.Column('nature_other_detail', sa.String(length=300), nullable=True),
        # [5]/[6] Contrôle d'étanchéité
        sa.Column('manual_leak_detector_identification', sa.String(length=200), nullable=True),
        sa.Column('manual_leak_detector_checked_on', sa.Date(), nullable=True),
        sa.Column('permanent_detection_system', sa.Boolean(), nullable=True),
        # [10] Fuites constatées
        sa.Column('leaks_found', sa.Boolean(), nullable=True),
        sa.Column(
            'leaks', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        # [11] Manipulation du fluide frigorigène — les totaux (A+B+C,
        # D+E) sont calculés par le domaine, jamais saisis indépendamment
        # (évite un total incohérent avec ses composants, erreur possible
        # sur le papier, impossible ici).
        sa.Column('charged_total_kg', sa.Float(), nullable=False),
        sa.Column('charged_virgin_kg', sa.Float(), nullable=False),
        sa.Column('charged_recycled_kg', sa.Float(), nullable=False),
        sa.Column('charged_regenerated_kg', sa.Float(), nullable=False),
        sa.Column('charged_fluid_name_if_changed', sa.String(length=100), nullable=True),
        sa.Column('recovered_total_kg', sa.Float(), nullable=False),
        sa.Column('recovered_for_treatment_kg', sa.Float(), nullable=False),
        sa.Column('recovered_for_reuse_kg', sa.Float(), nullable=False),
        sa.Column('bsff_number', sa.String(length=100), nullable=True),
        sa.Column('container_identification', sa.String(length=300), nullable=True),
        # [12] Dénomination ADR/RID
        sa.Column('waste_classification', postgresql.JSONB(), nullable=False),
        sa.Column('waste_classification_other_non_flammable', sa.String(length=200), nullable=True),
        sa.Column('waste_classification_other_flammable', sa.String(length=200), nullable=True),
        # [13]/[14]
        sa.Column('destination_installation', sa.String(length=500), nullable=True),
        sa.Column('observations', sa.String(length=4000), nullable=True),
        # Signatures
        sa.Column('operator_signatory_name', sa.String(length=200), nullable=False),
        sa.Column('operator_signatory_role', sa.String(length=200), nullable=True),
        sa.Column('detenteur_signatory_name', sa.String(length=200), nullable=True),
        sa.Column('detenteur_signatory_role', sa.String(length=200), nullable=True),
        sa.Column('signed_at', sa.Date(), nullable=False),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'intervention_id'],
            ['interventions.tenant_id', 'interventions.id'],
            name='fk_fgas_records_intervention',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('intervention_id', name='uq_fgas_records_intervention'),
        sa.CheckConstraint('total_charge_kg >= 0', name='ck_fgas_total_charge_non_negative'),
        sa.CheckConstraint(
            'co2_equivalent_tonnes IS NULL OR co2_equivalent_tonnes >= 0',
            name='ck_fgas_co2_non_negative',
        ),
        sa.CheckConstraint(
            'charged_total_kg >= 0 AND charged_virgin_kg >= 0 AND charged_recycled_kg >= 0 '
            'AND charged_regenerated_kg >= 0 AND recovered_total_kg >= 0 '
            'AND recovered_for_treatment_kg >= 0 AND recovered_for_reuse_kg >= 0',
            name='ck_fgas_quantities_non_negative',
        ),
    )

    op.execute("ALTER TABLE fgas_intervention_records ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE fgas_intervention_records FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON fgas_intervention_records
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )

    op.execute(
        """
        CREATE TRIGGER fgas_intervention_records_no_update
        BEFORE UPDATE ON fgas_intervention_records
        FOR EACH ROW EXECUTE FUNCTION forbid_update()
        """
    )
    op.execute(
        """
        CREATE TRIGGER fgas_intervention_records_no_delete
        BEFORE DELETE ON fgas_intervention_records
        FOR EACH ROW EXECUTE FUNCTION forbid_delete()
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
                IF EXISTS (SELECT 1 FROM fgas_intervention_records) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des fiches F-Gas existent (tenant %). '
                        'Décision explicite requise.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS fgas_intervention_records_no_delete "
        "ON fgas_intervention_records"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS fgas_intervention_records_no_update "
        "ON fgas_intervention_records"
    )
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON fgas_intervention_records")
    op.execute("ALTER TABLE fgas_intervention_records NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE fgas_intervention_records DISABLE ROW LEVEL SECURITY")
    op.drop_table('fgas_intervention_records')
