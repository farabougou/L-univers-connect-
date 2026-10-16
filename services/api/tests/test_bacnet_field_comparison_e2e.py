"""Outil de comparaison terrain, bout en bout contre un vrai scan BACnet
(BACnet Lab) — palier SIMULATOR_TESTED. Prouve que l'outil fonctionne
réellement sur les propositions produites par un scan complet, pas
seulement sur des données fabriquées à la main
(tests/test_bacnet_field_comparison.py). Aucune exécution ici ne constitue
une validation terrain (voir docs/adr/015-decouverte-bacnet-v1.md)."""

import uuid

import pytest
from sqlalchemy import text

from app.bacnet_discovery import complete_discovery, list_proposals, request_discovery
from app.bacnet_field_comparison import GtbEntry, compare, render_markdown_report
from app.connectors.bacnet import discover_device, read_device_objects
from app.db import engine
from app.tenancy import set_tenant_context
from tests.bacnet_lab import BacnetLab
from tests.tenant_cleanup import purge_tenant

ADDRESS = "127.0.0.1:47846"
DEVICE_INSTANCE = 5300


@pytest.fixture(scope="module", autouse=True)
def lab():
    simulator = BacnetLab(ADDRESS, device_instance=DEVICE_INSTANCE, profile="cta")
    simulator.start()
    yield simulator
    simulator.stop()


@pytest.fixture
def tenant():
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    equipment_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": "ClientBacnetComparaisonTerrain", "slug": f"cmp-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site')"),
            {"id": site_id, "tenant_id": tenant_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'cta-01', 'CTA Test')"
            ),
            {"id": equipment_id, "tenant_id": tenant_id, "site_id": site_id},
        )
    yield {"tenant_id": tenant_id, "equipment_id": equipment_id}
    purge_tenant(tenant_id)


def test_comparaison_contre_un_vrai_scan_bacnet(tenant):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        batch_id = request_discovery(
            connection,
            tenant_id=tenant["tenant_id"],
            equipment_id=tenant["equipment_id"],
            address=ADDRESS,
            scanned_by="test",
            timeout=3.0,
        )

    device_info = discover_device(ADDRESS, timeout=3.0)
    objects = read_device_objects(ADDRESS, device_info.device_instance, timeout=3.0)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        complete_discovery(
            connection,
            tenant_id=tenant["tenant_id"],
            batch_id=batch_id,
            device_instance=device_info.device_instance,
            objects=objects,
        )
        proposals = list_proposals(connection, batch_id=batch_id)

    # Reproduit ce qu'un technicien relèverait à la main depuis la GTB
    # existante avant l'essai : deux noms strictement identiques à ce que
    # le scan a trouvé, un absent du scan (écart réel à investiguer), et le
    # scan trouve par ailleurs des objets que la liste GTB ignorait.
    gtb_inventory = [
        GtbEntry(name="T Depart CTA", unit="°C"),
        GtbEntry(name="Defaut General CTA"),
        GtbEntry(name="Sonde Introuvable Sur Le Bus"),
    ]

    rows, summary = compare(gtb_inventory, proposals)

    assert summary.gtb_count == 3
    assert summary.discovered_count == 8
    assert summary.matched_count == 2
    assert summary.gtb_only_count == 1
    assert summary.discovery_only_count == 6

    gtb_only_names = {row.gtb_name for row in rows if row.match_kind == "gtb_only"}
    assert gtb_only_names == {"Sonde Introuvable Sur Le Bus"}

    matched_names = {row.discovered_name for row in rows if row.match_kind == "matched"}
    assert matched_names == {"T Depart CTA", "Defaut General CTA"}

    report = render_markdown_report(rows, summary, title="Essai pilote CTA-01")
    assert "Essai pilote CTA-01" in report
    assert "Sonde Introuvable Sur Le Bus" in report
