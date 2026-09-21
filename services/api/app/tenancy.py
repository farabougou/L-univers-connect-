import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection


def set_tenant_context(connection: Connection, tenant_id: uuid.UUID) -> None:
    """Déclare le tenant courant pour la transaction en cours.

    Les politiques RLS PostgreSQL lisent ce paramètre de session pour ne
    laisser passer que les lignes du tenant courant. `set_config(..., true)`
    équivaut à `SET LOCAL` : la valeur est effacée à la fin de la transaction.
    """
    connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
