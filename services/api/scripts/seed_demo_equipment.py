"""Crée un équipement de démonstration et son étiquette, pour tester
l'écran passeport (mobile ou web) sans matériel réel sur site.

Script de développement local uniquement : ne pas utiliser en production
(pas d'authentification, écrit directement en base). Rejouable sans risque
(identifiants déterministes, ne duplique rien).

Utilisation : depuis services/api, avec l'environnement virtuel activé :
    python scripts/seed_demo_equipment.py
"""

import uuid

from sqlalchemy import text

from app.db import engine
from app.tags import create_tag, with_payload
from app.tenancy import set_tenant_context

DEMO_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")

# Identifiants fixes : rejouer ce script ne crée jamais de doublon.
NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000000")
SITE_ID = uuid.uuid5(NAMESPACE, "demo-site")
BUILDING_ID = uuid.uuid5(NAMESPACE, "demo-building")
ROOM_ID = uuid.uuid5(NAMESPACE, "demo-room")
MODEL_ID = uuid.uuid5(NAMESPACE, "demo-model")
UNIT_ID = uuid.uuid5(NAMESPACE, "demo-unit")
LOCATION_ID = uuid.uuid5(NAMESPACE, "demo-location")


def main() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tenants (id, name, slug) VALUES (:id, 'Démonstration', 'demo') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": DEMO_TENANT_ID},
        )
        set_tenant_context(connection, DEMO_TENANT_ID)

        # Les tables ci-dessous ont un déclencheur BEFORE INSERT qui enregistre
        # la ligne dans graph_nodes : il s'exécute avant même que Postgres
        # évalue ON CONFLICT, donc "ON CONFLICT DO NOTHING" ne suffit pas pour
        # rejouer ce script sans erreur. On vérifie l'existence nous-mêmes.
        connection.execute(
            text(
                "INSERT INTO sites (id, tenant_id, name, timezone) "
                "SELECT :id, :tenant_id, 'Site de démonstration', 'Africa/Bamako' "
                "WHERE NOT EXISTS (SELECT 1 FROM sites WHERE id = :id)"
            ),
            {"id": SITE_ID, "tenant_id": DEMO_TENANT_ID},
        )
        connection.execute(
            text(
                "INSERT INTO spaces (id, tenant_id, site_id, space_type, code, name, valid_from) "
                "SELECT :id, :tenant_id, :site_id, 'building', 'BAT-A', 'Bâtiment A', now() "
                "WHERE NOT EXISTS (SELECT 1 FROM spaces WHERE id = :id)"
            ),
            {"id": BUILDING_ID, "tenant_id": DEMO_TENANT_ID, "site_id": SITE_ID},
        )
        connection.execute(
            text(
                "INSERT INTO spaces (id, tenant_id, site_id, parent_id, space_type, code, name, "
                "valid_from) SELECT :id, :tenant_id, :site_id, :parent_id, 'zone', 'CHAUF', "
                "'Chaufferie', now() WHERE NOT EXISTS (SELECT 1 FROM spaces WHERE id = :id)"
            ),
            {
                "id": ROOM_ID,
                "tenant_id": DEMO_TENANT_ID,
                "site_id": SITE_ID,
                "parent_id": BUILDING_ID,
            },
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name, kind, "
                "space_id) SELECT :id, :tenant_id, :site_id, 'pac-01', 'PAC 01', 'equipment', "
                ":space_id WHERE NOT EXISTS (SELECT 1 FROM functional_locations WHERE id = :id)"
            ),
            {
                "id": LOCATION_ID,
                "tenant_id": DEMO_TENANT_ID,
                "site_id": SITE_ID,
                "space_id": ROOM_ID,
            },
        )
        connection.execute(
            text(
                "INSERT INTO product_models (id, tenant_id, manufacturer, reference, "
                "equipment_type) VALUES (:id, :tenant_id, 'Fabricant Démonstration', 'PAC-X', "
                "'heat_pump') ON CONFLICT (id) DO NOTHING"
            ),
            {"id": MODEL_ID, "tenant_id": DEMO_TENANT_ID},
        )
        connection.execute(
            text(
                "INSERT INTO physical_units (id, tenant_id, product_model_id, serial_number, "
                "lifecycle_state) SELECT :id, :tenant_id, :model_id, 'SN-DEMO-1', 'installed' "
                "WHERE NOT EXISTS (SELECT 1 FROM physical_units WHERE id = :id)"
            ),
            {"id": UNIT_ID, "tenant_id": DEMO_TENANT_ID, "model_id": MODEL_ID},
        )
        connection.execute(
            text(
                "INSERT INTO functional_location_assignments (id, tenant_id, "
                "functional_location_id, physical_unit_id, valid_from) "
                "SELECT gen_random_uuid(), :tenant_id, :location_id, :unit_id, now() "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM functional_location_assignments "
                "  WHERE functional_location_id = :location_id AND physical_unit_id = :unit_id"
                ")"
            ),
            {"tenant_id": DEMO_TENANT_ID, "location_id": LOCATION_ID, "unit_id": UNIT_ID},
        )

        existing_tag = connection.execute(
            text("SELECT code FROM asset_tags WHERE node_id = :node_id AND status = 'active'"),
            {"node_id": LOCATION_ID},
        ).scalar()
        if existing_tag:
            code = existing_tag
        else:
            tag = create_tag(
                connection,
                tenant_id=DEMO_TENANT_ID,
                node_id=LOCATION_ID,
                tag_type="qr",
                created_by="seed-script",
            )
            code = tag["code"]

    print("Équipement de démonstration prêt : PAC 01 (pac-01)")
    print(f"Code d'étiquette à taper dans l'écran Passeport : {code}")
    print(f"Contenu équivalent d'un QR : {with_payload({'code': code})['payload']}")


if __name__ == "__main__":
    main()
