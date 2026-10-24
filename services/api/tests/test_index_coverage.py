"""Couverture d'index (audit V5 du 20/10/2026).

La sécurité par ligne ajoute `tenant_id = ...` à chaque requête : sans index
adapté, Postgres parcourt la table de TOUS les clients pour n'en garder qu'un,
et le coût croît avec le nombre total de clients. Mesuré sur 40 clients et
160 000 lignes par table : jusqu'à x910 plus lent sans index (voir la
migration c8e5a2f94b16 et docs/spec/feature-benchmark-matrix.md).

Ces tests empêchent le retour du défaut : une nouvelle table multi-clients
doit arriver avec un index, ou avec une exemption écrite et justifiée ici.
"""

import pytest
from sqlalchemy import text

from app.db import engine

# Tables portant `tenant_id` sans index secondaire, avec la raison.
_EXEMPT = {
    "measurements": "sa clé primaire (point_id, measured_at) sert tous les accès (par point)",
    "product_models": "catalogue de quelques dizaines de lignes par client",
    "providers": "catalogue de quelques dizaines de lignes par client",
}

_SECONDARY_INDEX_COUNT = """
SELECT t.relname,
       count(*) FILTER (
           WHERE i.indexrelid IS NOT NULL AND NOT i.indisprimary
             AND NOT (i.indisunique AND i.indnatts = 1 AND a.attname = 'id')
       ) AS secondary_indexes
FROM pg_class t
JOIN pg_attribute ta ON ta.attrelid = t.oid AND ta.attname = 'tenant_id' AND NOT ta.attisdropped
LEFT JOIN pg_index i ON i.indrelid = t.oid
LEFT JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = i.indkey[0]
WHERE t.relkind = 'r' AND t.relnamespace = 'public'::regnamespace
GROUP BY t.relname
"""


def test_toute_table_multi_clients_a_un_index_ou_une_exemption_justifiee() -> None:
    with engine.connect() as connection:
        rows = connection.execute(text(_SECONDARY_INDEX_COUNT)).all()

    without_index = {name for name, count in rows if count == 0}
    unjustified = without_index - set(_EXEMPT)
    assert not unjustified, (
        f"Tables avec tenant_id et sans aucun index secondaire : {sorted(unjustified)}. "
        "Ajouter un index (migration) ou une exemption justifiée dans _EXEMPT."
    )
    stale = set(_EXEMPT) - without_index
    assert not stale, f"Exemptions devenues inutiles, à retirer : {sorted(stale)}"


# Définitions exactes des index de la migration c8e5a2f94b16. Un test de plan
# d'exécution ne serait pas déterministe ici : sur des tables presque vides, le
# planificateur départage deux index à coût égal. L'usage réel de chacun a été
# mesuré sur 40 clients et 160 000 lignes par table (voir la matrice).
_HOT_PATH_INDEXES = {
    "ix_alarms_tenant_handling_raised": "(tenant_id, handling_status, raised_at DESC)",
    "ix_alarms_tenant_location_raised": "(tenant_id, functional_location_id, raised_at DESC)",
    "ix_work_orders_tenant_location": "(tenant_id, functional_location_id)",
    "ix_interventions_work_order": "(work_order_id) WHERE (work_order_id IS NOT NULL)",
    "ix_interventions_tenant_location": "(tenant_id, functional_location_id)",
    "ix_work_order_status_history_order": "(work_order_id, changed_at)",
    "ix_alarm_status_history_alarm": "(alarm_id, changed_at)",
    "ix_finding_status_history_finding": "(finding_id, changed_at)",
    "ix_documents_tenant_uploaded": "(tenant_id, uploaded_at DESC)",
}


@pytest.mark.parametrize(("index_name", "expected"), sorted(_HOT_PATH_INDEXES.items()))
def test_l_index_des_chemins_chauds_existe_est_valide_et_a_la_bonne_forme(
    index_name: str, expected: str
) -> None:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT i.indisvalid, pg_get_indexdef(i.indexrelid) FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indexrelid WHERE c.relname = :name"
            ),
            {"name": index_name},
        ).one_or_none()

    assert row is not None, f"index {index_name} absent"
    is_valid, definition = row
    assert is_valid, f"index {index_name} invalide (construction interrompue ?)"
    assert definition.split(" USING btree ", 1)[1] == expected
