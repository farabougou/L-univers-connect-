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
