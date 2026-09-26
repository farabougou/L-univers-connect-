"""Diagnostic ponctuel : reproduit exactement l'INSERT fait par POST /sites
pour voir l'erreur complète en console, sans passer par les logs Railway.

À supprimer une fois le problème de staging résolu (pas un outil permanent).
"""

import uuid

from sqlalchemy import text

from app.db import engine
from app.tenancy import set_tenant_context

DEMO_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def main() -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, DEMO_TENANT_ID)
        connection.execute(
            text(
                "INSERT INTO sites (id, tenant_id, name, timezone) "
                "VALUES (:id, :tenant_id, :name, :timezone)"
            ),
            {
                "id": uuid.uuid4(),
                "tenant_id": DEMO_TENANT_ID,
                "name": "Site Test",
                "timezone": "Europe/Paris",
            },
        )
    print("Site créé sans erreur.")


if __name__ == "__main__":
    main()
