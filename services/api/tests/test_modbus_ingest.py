"""Chaîne complète : lecture Modbus (simulée) → mesure réellement enregistrée.

Le simulateur sert la même carte de registres qu'un vrai SDM120 (voir
tests/test_modbus_connector.py, qui valide le connecteur seul). Ce test-ci
valide l'étape suivante : la valeur lue atterrit bien dans la table
measurements, via le même chemin (ingest_measurements) que la télémétrie
envoyée par une application.
"""

import threading
import time
import uuid

import pytest
from pymodbus.server import ServerStop, StartTcpServer
from sqlalchemy import text

from app.connectors.ingest import PointModbusMapping, poll_and_record
from app.connectors.sdm120 import SDM120_POINTS
from app.db import engine
from app.points import create_point, decide_point
from app.tenancy import set_tenant_context
from scripts.modbus_simulator import FAKE_VALUES, build_context

PORT = 5098


@pytest.fixture(scope="module", autouse=True)
def modbus_simulator():
    thread = threading.Thread(
        target=StartTcpServer,
        args=(build_context(),),
        kwargs={"address": ("127.0.0.1", PORT)},
        daemon=True,
    )
    thread.start()
    time.sleep(0.5)
    yield
    ServerStop()
    thread.join(timeout=2)


@pytest.fixture
def tenant_with_point():
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    location_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": "ClientModbusIngest", "slug": f"modbus-ingest-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site')"),
            {"id": site_id, "tenant_id": tenant_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'cpt-01', 'Compteur test')"
            ),
            {"id": location_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        point_id = create_point(
            connection,
            tenant_id=tenant_id,
            code="CPT01-EATOT",
            name="Énergie active totale",
            value_type="number",
            point_class="energy_meter_reading",
            unit="kW.h",
            functional_location_id=location_id,
            min_value=0,
            max_value=1_000_000,
            created_by="test",
        )
        decide_point(connection, point_id=point_id, decision="validated")
    yield {"tenant_id": tenant_id, "point_id": point_id}
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("measurements", "points", "functional_locations", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def test_la_valeur_lue_par_modbus_est_enregistree_comme_mesure(tenant_with_point):
    tenant_id = tenant_with_point["tenant_id"]
    point_id = tenant_with_point["point_id"]
    register = next(p for p in SDM120_POINTS if p.name == "total_active_energy")

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        summary = poll_and_record(
            connection,
            tenant_id=tenant_id,
            host="127.0.0.1",
            port=PORT,
            mappings=[PointModbusMapping(point_id=point_id, register=register)],
            source="sdm120",
        )

    assert summary["inserted"] == 1

    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        row = (
            connection.execute(
                text("SELECT value, origin, source FROM measurements WHERE point_id = :id"),
                {"id": point_id},
            )
            .mappings()
            .first()
        )

    assert row is not None
    assert row["value"] == pytest.approx(FAKE_VALUES["total_active_energy"], abs=1e-3)
    assert row["origin"] == "measured"
    assert row["source"] == "sdm120"
