"""add config versions, desired states, findings (expand only)

ADR 012, étape F4 : configuration versionnée générique, état souhaité
(attentes déclarées), constats analytiques et leur historique de statut.

Élargissement uniquement (nouvelles tables). Chaque table porte tenant_id,
RLS forcée, clés étrangères composées avec le tenant, et des déclencheurs qui
empêchent de réécrire ce qui ne doit pas l'être (règle « rien n'est écrasé »).

Revision ID: 1403c6bbaa32
Revises: f688f24c2cd4
Create Date: 2026-09-23 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1403c6bbaa32'
down_revision: Union[str, None] = 'f688f24c2cd4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ('config_versions', 'desired_states', 'findings', 'finding_status_history')

_TENANT_POLICY = """
    CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def _now():
    return sa.text('now()')


def upgrade() -> None:
    op.create_table(
        'config_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('config_type', sa.String(length=50), nullable=False),
        sa.Column('subject_key', sa.String(length=200), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', postgresql.JSONB(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('schema_version', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('author', sa.String(length=200), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('parent_version_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_by', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'id', name='uq_config_versions_tenant_id_id'),
        sa.UniqueConstraint(
            'tenant_id', 'config_type', 'subject_key', 'version',
            name='uq_config_versions_version',
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'retired')",
            name='ck_config_versions_status',
        ),
        sa.CheckConstraint('version >= 1', name='ck_config_versions_version'),
    )
    op.create_foreign_key(
        'fk_config_versions_parent', 'config_versions', 'config_versions',
        ['tenant_id', 'parent_version_id'], ['tenant_id', 'id'],
    )
    # Une seule version active par élément configuré, garanti par la base.
    op.create_index(
        'uq_config_versions_one_active', 'config_versions',
        ['tenant_id', 'config_type', 'subject_key'],
        unique=True, postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        'desired_states',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('point_id', sa.UUID(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('daily_start', sa.Time(), nullable=True),
        sa.Column('daily_end', sa.Time(), nullable=True),
        sa.Column('timezone', sa.String(length=64), nullable=True),
        sa.Column('source', sa.String(length=30), server_default='declared_expectation', nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('created_by', sa.String(length=200), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'point_id'], ['points.tenant_id', 'points.id'],
            name='fk_desired_states_point',
        ),
        sa.PrimaryKeyConstraint('id'),
        # Seule origine permise en lecture seule : une attente déclarée par un
        # humain. Plannings, politiques et intentions de commande viendront
        # avec une migration explicite (règle non négociable 1).
        sa.CheckConstraint(
            "source IN ('declared_expectation')", name='ck_desired_states_source'
        ),
        sa.CheckConstraint(
            '(daily_start IS NULL) = (daily_end IS NULL)', name='ck_desired_states_window'
        ),
        sa.CheckConstraint(
            'daily_start IS NULL OR timezone IS NOT NULL', name='ck_desired_states_timezone'
        ),
        sa.CheckConstraint(
            'valid_to IS NULL OR valid_to > valid_from', name='ck_desired_states_period'
        ),
    )
    op.create_index('ix_desired_states_point_id', 'desired_states', ['point_id'])

    op.create_table(
        'findings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('subject_node_id', sa.UUID(), nullable=False),
        sa.Column('point_id', sa.UUID(), nullable=True),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('method', sa.String(length=30), nullable=False),
        sa.Column('rule_config_version_id', sa.UUID(), nullable=True),
        sa.Column('dedup_key', sa.String(length=300), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('recommended_action', sa.String(length=1000), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evidence', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='open', nullable=False),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('occurrence_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('alarm_id', sa.UUID(), nullable=True),
        sa.Column('work_order_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'subject_node_id'], ['graph_nodes.tenant_id', 'graph_nodes.id'],
            name='fk_findings_subject',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'point_id'], ['points.tenant_id', 'points.id'],
            name='fk_findings_point',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'rule_config_version_id'],
            ['config_versions.tenant_id', 'config_versions.id'],
            name='fk_findings_rule',
        ),
        sa.ForeignKeyConstraint(['alarm_id'], ['alarms.id'], name='fk_findings_alarm'),
        sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id'], name='fk_findings_work_order'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'id', name='uq_findings_tenant_id_id'),
        # Anomalie ≠ défaut ≠ prédiction : natures séparées (addendum V2, 2).
        sa.CheckConstraint(
            "kind IN ('data_quality', 'commissioning', 'anomaly', 'fault', 'prediction')",
            name='ck_findings_kind',
        ),
        sa.CheckConstraint(
            "method IN ('deterministic_rule', 'engineering_rule', 'statistical', "
            "'physical_model', 'peer_comparison', 'ml')",
            name='ck_findings_method',
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical')", name='ck_findings_severity'
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved', 'false_positive')",
            name='ck_findings_status',
        ),
        sa.CheckConstraint(
            'confidence IS NULL OR (confidence >= 0 AND confidence <= 1)',
            name='ck_findings_confidence',
        ),
        sa.CheckConstraint('occurrence_count >= 1', name='ck_findings_occurrences'),
    )
    # Un même problème n'ouvre qu'un seul constat tant qu'il n'est pas traité :
    # les répétitions l'incrémentent au lieu d'en créer des dizaines.
    op.create_index(
        'uq_findings_one_open', 'findings', ['tenant_id', 'dedup_key'],
        unique=True, postgresql_where=sa.text("status IN ('open', 'acknowledged')"),
    )
    op.create_index('ix_findings_subject_node_id', 'findings', ['subject_node_id'])

    op.create_table(
        'finding_status_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('finding_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('changed_by', sa.String(length=200), nullable=False),
        sa.Column('note', sa.String(length=2000), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(
            ['tenant_id', 'finding_id'], ['findings.tenant_id', 'findings.id'],
            name='fk_finding_status_history_finding',
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(_TENANT_POLICY.format(table=table))

    op.execute(
        """
        CREATE FUNCTION protect_config_version() RETURNS trigger AS $$
        BEGIN
            IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id
                OR NEW.config_type <> OLD.config_type OR NEW.subject_key <> OLD.subject_key
                OR NEW.version <> OLD.version OR NEW.content <> OLD.content
                OR NEW.content_hash <> OLD.content_hash
                OR NEW.schema_version <> OLD.schema_version OR NEW.author <> OLD.author
                OR NEW.reason <> OLD.reason
                OR NEW.parent_version_id IS DISTINCT FROM OLD.parent_version_id
                OR NEW.created_at <> OLD.created_at THEN
                RAISE EXCEPTION 'config_versions : une version publiée n''est jamais réécrite (%)',
                    OLD.id;
            END IF;
            IF OLD.activated_at IS NOT NULL
                AND (NEW.activated_at IS DISTINCT FROM OLD.activated_at
                     OR NEW.activated_by IS DISTINCT FROM OLD.activated_by) THEN
                RAISE EXCEPTION 'config_versions : activation déjà enregistrée (%)', OLD.id;
            END IF;
            IF NEW.status <> OLD.status AND NOT (
                (OLD.status = 'draft' AND NEW.status IN ('active', 'retired'))
                OR (OLD.status = 'active' AND NEW.status IN ('superseded', 'retired'))
            ) THEN
                RAISE EXCEPTION 'config_versions : passage % → % interdit (%)',
                    OLD.status, NEW.status, OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER config_versions_protect
        BEFORE UPDATE ON config_versions
        FOR EACH ROW EXECUTE FUNCTION protect_config_version()
        """
    )
    # Une version de configuration n'est jamais supprimée : on la retire
    # (statut « retired »), elle reste dans l'historique.
    op.execute(
        """
        CREATE FUNCTION forbid_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% : suppression interdite (ligne %)', TG_TABLE_NAME, OLD.id;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER config_versions_no_delete
        BEFORE DELETE ON config_versions
        FOR EACH ROW EXECUTE FUNCTION forbid_delete()
        """
    )

    op.execute(
        """
        CREATE FUNCTION protect_desired_state() RETURNS trigger AS $$
        BEGIN
            IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id
                OR NEW.point_id <> OLD.point_id OR NEW.value <> OLD.value
                OR NEW.daily_start IS DISTINCT FROM OLD.daily_start
                OR NEW.daily_end IS DISTINCT FROM OLD.daily_end
                OR NEW.timezone IS DISTINCT FROM OLD.timezone OR NEW.source <> OLD.source
                OR NEW.valid_from <> OLD.valid_from OR NEW.reason <> OLD.reason
                OR NEW.created_by <> OLD.created_by OR NEW.recorded_at <> OLD.recorded_at THEN
                RAISE EXCEPTION 'desired_states : champ non modifiable (%), clore et recréer',
                    OLD.id;
            END IF;
            IF OLD.valid_to IS NOT NULL AND NEW.valid_to IS DISTINCT FROM OLD.valid_to THEN
                RAISE EXCEPTION 'desired_states : la ligne % est déjà close', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER desired_states_protect
        BEFORE UPDATE ON desired_states
        FOR EACH ROW EXECUTE FUNCTION protect_desired_state()
        """
    )

    op.execute(
        """
        CREATE FUNCTION protect_finding() RETURNS trigger AS $$
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
    )
    op.execute(
        """
        CREATE TRIGGER findings_protect
        BEFORE UPDATE ON findings
        FOR EACH ROW EXECUTE FUNCTION protect_finding()
        """
    )


def downgrade() -> None:
    # Retour arrière refusé dès qu'une configuration, une attente ou un
    # constat existe : les supprimer effacerait l'historique de décision.
    op.execute(
        """
        DO $$
        DECLARE
            t record;
        BEGIN
            FOR t IN SELECT id FROM tenants LOOP
                PERFORM set_config('app.current_tenant_id', t.id::text, true);
                IF EXISTS (SELECT 1 FROM config_versions)
                    OR EXISTS (SELECT 1 FROM desired_states)
                    OR EXISTS (SELECT 1 FROM findings) THEN
                    RAISE EXCEPTION
                        'retour arrière refusé : des configurations, attentes ou constats '
                        'existent (tenant %). Sauvegarde et décision explicite requises.', t.id;
                END IF;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END;
        $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS findings_protect ON findings")
    op.execute("DROP FUNCTION IF EXISTS protect_finding()")
    op.execute("DROP TRIGGER IF EXISTS desired_states_protect ON desired_states")
    op.execute("DROP FUNCTION IF EXISTS protect_desired_state()")
    op.execute("DROP TRIGGER IF EXISTS config_versions_no_delete ON config_versions")
    op.execute("DROP TRIGGER IF EXISTS config_versions_protect ON config_versions")
    op.execute("DROP FUNCTION IF EXISTS forbid_delete()")
    op.execute("DROP FUNCTION IF EXISTS protect_config_version()")

    for table in reversed(_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table('finding_status_history')
    op.drop_index('ix_findings_subject_node_id', table_name='findings')
    op.drop_index('uq_findings_one_open', table_name='findings')
    op.drop_table('findings')
    op.drop_index('ix_desired_states_point_id', table_name='desired_states')
    op.drop_table('desired_states')
    op.drop_index('uq_config_versions_one_active', table_name='config_versions')
    op.drop_constraint('fk_config_versions_parent', 'config_versions', type_='foreignkey')
    op.drop_table('config_versions')
