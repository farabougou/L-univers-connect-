"""add hot path indexes

Audit V5 (20/10/2026) : 22 des 44 tables portant `tenant_id` n'avaient aucun
index commençant par `tenant_id`, et plusieurs tables qui grossissent avec le
temps (`alarms`, `work_orders`, les trois historiques de statut) n'avaient que
leur clé primaire. Or la sécurité par ligne ajoute `tenant_id = ...` à chaque
requête : sans index adapté, Postgres parcourt la table de TOUS les clients
pour n'en garder qu'un, et le coût croît avec le nombre total de clients, pas
avec la taille du client concerné.

Mesuré sur une base jetable (40 clients, 160 000 lignes par table, rôle
applicatif soumis à la sécurité par ligne, requêtes réelles de l'API) :
alarmes ouvertes x201, alarmes d'un équipement x75, historique d'un ordre de
travail x766, historique d'une alarme x910, historique des constats x85,
chronologie d'ordres de travail x60, documents du portefeuille x33,
interventions d'un ordre de travail x26. Les constats ouverts n'ont PAS
d'index ajouté : l'index partiel existant `uq_findings_one_open` les sert déjà
(gain mesuré x0,9, donc rien à ajouter).

Uniquement additif (phase « élargir » de la règle des trois temps) : aucune
colonne, aucune donnée, aucune requête de l'application modifiée.
`CREATE INDEX CONCURRENTLY` ne bloque pas les écritures (hors transaction,
d'où `autocommit_block`). Un index laissé invalide par une construction
interrompue est supprimé avant d'être recréé, car `IF NOT EXISTS` le
laisserait inutilisable.

Revision ID: c8e5a2f94b16
Revises: b7c43d1f8e70
Create Date: 2026-10-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c8e5a2f94b16'
down_revision: Union[str, None] = 'b7c43d1f8e70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = (
    ('ix_alarms_tenant_handling_raised', 'alarms', 'tenant_id, handling_status, raised_at DESC', ''),
    ('ix_alarms_tenant_location_raised', 'alarms', 'tenant_id, functional_location_id, raised_at DESC', ''),
    ('ix_work_orders_tenant_location', 'work_orders', 'tenant_id, functional_location_id', ''),
    ('ix_interventions_work_order', 'interventions', 'work_order_id', 'WHERE work_order_id IS NOT NULL'),
    ('ix_interventions_tenant_location', 'interventions', 'tenant_id, functional_location_id', ''),
    ('ix_work_order_status_history_order', 'work_order_status_history', 'work_order_id, changed_at', ''),
    ('ix_alarm_status_history_alarm', 'alarm_status_history', 'alarm_id, changed_at', ''),
    ('ix_finding_status_history_finding', 'finding_status_history', 'finding_id, changed_at', ''),
    ('ix_documents_tenant_uploaded', 'documents', 'tenant_id, uploaded_at DESC', ''),
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table, columns, where in _INDEXES:
            op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS {name}')
            op.execute(f'CREATE INDEX CONCURRENTLY {name} ON {table} ({columns}) {where}'.rstrip())


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, _table, _columns, _where in _INDEXES:
            op.execute(f'DROP INDEX CONCURRENTLY IF EXISTS {name}')
