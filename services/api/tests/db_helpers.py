"""Aides de test pour contourner les protections append-only d'audit_log.

Ces protections sont volontaires (voir app/audit.py et la migration
5929036bce23) : même le nettoyage des données de test doit passer par un
accès administrateur explicite, jamais par un simple DELETE applicatif.
"""

from sqlalchemy import create_engine, text

# Compte administrateur PostgreSQL local (voir infra/init-db/01-create-app-role.sql).
# Jamais utilisé par l'API elle-même, uniquement ici pour nettoyer les
# entrées d'audit créées par les tests.
ADMIN_DATABASE_URL = (
    "postgresql+psycopg://postgres:postgres_admin_dev_password@localhost:5432/paios"
)


def purge_relations_for_tenant(tenant_id) -> None:
    """Même principe pour les relations, protégées contre toute suppression
    (voir la migration 706eca882498)."""
    admin_engine = create_engine(ADMIN_DATABASE_URL)
    try:
        with admin_engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE relations DISABLE TRIGGER relations_protect_history")
            )
            connection.execute(
                text("DELETE FROM relations WHERE tenant_id = :id"), {"id": tenant_id}
            )
            connection.execute(
                text("ALTER TABLE relations ENABLE TRIGGER relations_protect_history")
            )
    finally:
        admin_engine.dispose()


def purge_config_versions_for_tenant(tenant_id) -> None:
    """Les versions de configuration sont protégées contre toute suppression
    (voir la migration 1403c6bbaa32). Les constats qui les référencent
    doivent être supprimés avant."""
    admin_engine = create_engine(ADMIN_DATABASE_URL)
    try:
        with admin_engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE config_versions DISABLE TRIGGER config_versions_no_delete")
            )
            connection.execute(
                text("DELETE FROM config_versions WHERE tenant_id = :id"), {"id": tenant_id}
            )
            connection.execute(
                text("ALTER TABLE config_versions ENABLE TRIGGER config_versions_no_delete")
            )
    finally:
        admin_engine.dispose()


def purge_audit_log_for_tenant(tenant_id) -> None:
    admin_engine = create_engine(ADMIN_DATABASE_URL)
    try:
        with admin_engine.begin() as connection:
            connection.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_delete"))
            connection.execute(
                text("DELETE FROM audit_log WHERE tenant_id = :id"), {"id": tenant_id}
            )
            connection.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_delete"))
    finally:
        admin_engine.dispose()


def purge_intervention_closures_for_tenant(tenant_id) -> None:
    """Les clôtures d'intervention sont des preuves, protégées contre toute
    suppression (voir la migration a4a1fa8a4cfa)."""
    admin_engine = create_engine(ADMIN_DATABASE_URL)
    try:
        with admin_engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE intervention_closures "
                    "DISABLE TRIGGER intervention_closures_no_delete"
                )
            )
            connection.execute(
                text("DELETE FROM intervention_closures WHERE tenant_id = :id"), {"id": tenant_id}
            )
            connection.execute(
                text(
                    "ALTER TABLE intervention_closures "
                    "ENABLE TRIGGER intervention_closures_no_delete"
                )
            )
    finally:
        admin_engine.dispose()
