"""Palier INTEGRATION_TESTED pour le script de seed du Virtual Commissioning
Lab (ADR 017 §2.1 ; câblage étendu le 02/10/2026, demande explicite de
Mohamed). Aucun test n'exerçait directement `scripts/seed_virtual_site.py`
avant ce fichier — seul le générateur de télémétrie pur
(`app/connectors/virtual_telemetry.py`) était testé. Ici : la vraie fonction
`seed()`, contre une vraie base, deux fois de suite pour prouver
l'idempotence (règles FDD, état souhaité, point commandable, relation
dependsOn)."""

import uuid

from sqlalchemy import text

from app.db import engine
from app.rules import ALARM_RULE
from app.tenancy import set_tenant_context
from scripts.seed_virtual_site import TENANT_ID, seed
from tests.db_helpers import (
    purge_config_versions_for_tenant,
    purge_relations_for_tenant,
)

SITE_NAME = "Test VCL Seed Script"


def _cleanup() -> None:
    purge_relations_for_tenant(TENANT_ID)
    purge_config_versions_for_tenant(TENANT_ID)
    with engine.begin() as connection:
        set_tenant_context(connection, TENANT_ID)
        site_id = connection.execute(
            text("SELECT id FROM sites WHERE tenant_id = :tenant_id AND name = :name"),
            {"tenant_id": TENANT_ID, "name": SITE_NAME},
        ).scalar()
        if site_id is None:
            return
        for table in ("desired_states", "edge_devices"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :tenant_id"), {"tenant_id": TENANT_ID}
            )
        connection.execute(
            text("DELETE FROM points WHERE tenant_id = :tenant_id"), {"tenant_id": TENANT_ID}
        )
        connection.execute(
            text(
                "DELETE FROM functional_location_space_history WHERE functional_location_id IN "
                "(SELECT id FROM functional_locations WHERE site_id = :site_id)"
            ),
            {"site_id": site_id},
        )
        connection.execute(
            text("DELETE FROM functional_locations WHERE site_id = :site_id"), {"site_id": site_id}
        )
        connection.execute(
            text("DELETE FROM spaces WHERE site_id = :site_id"), {"site_id": site_id}
        )
        connection.execute(text("DELETE FROM sites WHERE id = :id"), {"id": site_id})


def _active_rule_subject_keys(connection) -> set[str]:
    return set(
        connection.execute(
            text(
                "SELECT subject_key FROM config_versions WHERE config_type = :type "
                "AND status = 'active'"
            ),
            {"type": ALARM_RULE},
        ).scalars()
    )


def test_seed_wires_fdd_rules_desired_state_relay_and_impact_relation() -> None:
    _cleanup()
    try:
        manifest = seed(site_name=SITE_NAME, profiles=["cta", "groupe_froid", "pompe"])
        equipment_by_profile = {e["profile"]: e for e in manifest["equipment"]}
        assert set(equipment_by_profile) == {"cta", "groupe_froid", "pompe"}

        with engine.begin() as connection:
            set_tenant_context(connection, TENANT_ID)

            subject_keys = _active_rule_subject_keys(connection)
            assert {
                "CTA-01-correlation",
                "CTA-01-projection",
                "CTA-01-divergence",
                "GROUPE_FROID-01-seuil",
                "GROUPE_FROID-01-projection",
                "POMPE-01-seuil",
                "POMPE-01-projection",
            } <= subject_keys

            damper_point_id = equipment_by_profile["cta"]["points"]["volet_air_neuf"]
            desired_state = connection.execute(
                text(
                    "SELECT value FROM desired_states WHERE point_id = :point_id "
                    "AND valid_to IS NULL"
                ),
                {"point_id": damper_point_id},
            ).scalar()
            assert desired_state == 50.0

            relay_point_id = equipment_by_profile["pompe"]["points"]["commande_marche_forcee"]
            mapping_subject_key = equipment_by_profile["pompe"]["functional_location_id"]
            mapping_content = connection.execute(
                text(
                    "SELECT content FROM config_versions "
                    "WHERE config_type = 'modbus_device_mapping' "
                    "AND subject_key = :key AND status = 'active'"
                ),
                {"key": mapping_subject_key},
            ).scalar()
            assert mapping_content["device_type"] == "simulated_relay"
            assert mapping_content["points"][0]["point_id"] == relay_point_id

            pompe_location_id = uuid.UUID(equipment_by_profile["pompe"]["functional_location_id"])
            groupe_froid_location_id = uuid.UUID(
                equipment_by_profile["groupe_froid"]["functional_location_id"]
            )
            relation = connection.execute(
                text(
                    "SELECT 1 FROM relations WHERE subject_id = :subject "
                    "AND predicate = 'dependsOn' AND object_id = :object AND valid_to IS NULL"
                ),
                {"subject": pompe_location_id, "object": groupe_froid_location_id},
            ).scalar()
            assert relation == 1

        # Rejouer le script ne duplique rien : même nombre de versions actives,
        # même état souhaité, même relation — idempotence réelle, pas seulement
        # déclarée dans le docstring. `device_secret` est volontairement
        # exclu de la comparaison : un appareil déjà provisionné n'est
        # jamais re-provisionné, son secret devient None au second appel
        # (comportement documenté, pas un défaut d'idempotence).
        manifest_again = seed(site_name=SITE_NAME, profiles=["cta", "groupe_froid", "pompe"])

        def _without_secret(equipment: list[dict]) -> list[dict]:
            return [{k: v for k, v in e.items() if k != "device_secret"} for e in equipment]

        assert _without_secret(manifest_again["equipment"]) == _without_secret(
            manifest["equipment"]
        )
        with engine.begin() as connection:
            set_tenant_context(connection, TENANT_ID)
            assert _active_rule_subject_keys(connection) == subject_keys
            desired_state_count = connection.execute(
                text(
                    "SELECT COUNT(*) FROM desired_states WHERE point_id = :point_id "
                    "AND valid_to IS NULL"
                ),
                {"point_id": damper_point_id},
            ).scalar()
            assert desired_state_count == 1
            relation_count = connection.execute(
                text(
                    "SELECT COUNT(*) FROM relations WHERE subject_id = :subject "
                    "AND predicate = 'dependsOn' AND object_id = :object AND valid_to IS NULL"
                ),
                {"subject": pompe_location_id, "object": groupe_froid_location_id},
            ).scalar()
            assert relation_count == 1
    finally:
        _cleanup()
