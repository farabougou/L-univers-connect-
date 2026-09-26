"""Vérifie qu'une photo envoyée reste accessible après un redémarrage du
service API : les photos vivent dans le stockage (R2), jamais sur le disque
du conteneur (voir ADR 006) — un redémarrage de l'API ne doit donc jamais
les affecter. Ce script récupère la photo la plus récente du tenant de
démonstration, génère une URL de téléchargement et vérifie qu'elle répond.

Utilisation, depuis services/api : python scripts/check_photo_persists.py
"""

import urllib.request
import uuid

from sqlalchemy import text

from app.db import engine
from app.storage import create_presigned_download_url
from app.tenancy import set_tenant_context

DEMO_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def main() -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, DEMO_TENANT_ID)
        photo = connection.execute(
            text(
                "SELECT id, intervention_id, storage_key, taken_at FROM intervention_photos "
                "WHERE tenant_id = :tenant_id ORDER BY taken_at DESC LIMIT 1"
            ),
            {"tenant_id": DEMO_TENANT_ID},
        ).mappings().first()

    if not photo:
        print("Aucune photo trouvée pour ce tenant.")
        return

    print(f"Photo la plus récente : {photo['id']} (intervention {photo['intervention_id']})")
    print(f"Clé de stockage : {photo['storage_key']}")

    download_url = create_presigned_download_url(photo["storage_key"])
    with urllib.request.urlopen(download_url, timeout=10) as response:
        size = len(response.read())

    print(f"Téléchargement réussi : {size} octets reçus.")


if __name__ == "__main__":
    main()
