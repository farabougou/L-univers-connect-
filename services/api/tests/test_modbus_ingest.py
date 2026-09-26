"""Chaîne complète : lecture Modbus (simulée) → mesure réellement enregistrée.

Le simulateur sert la même carte de registres qu'un vrai SDM120 (voir
tests/test_modbus_connector.py, qui valide le connecteur seul). Ce test-ci
valide l'étape suivante : la valeur lue atterrit bien dans la table
measurements, via le même chemin (ingest_measurements) que la télémétrie
envoyée par une application.
"""

import threading
import time

import pytest
from pymodbus.server import ServerStop, StartTcpServer
from sqlalchemy import text

from app.connectors.ingest import PointModbusMapping, poll_and_record
from app.connectors.sdm120 import SDM120_POINTS
from app.db import engine
from app.tenancy import set_tenant_context
from scripts.modbus_simulator import FAKE_VALUES, build_context
from tests.modbus_fixtures import cleanup_tenant, create_tenant_with_energy_point

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
    tenant = create_tenant_with_energy_point("ClientModbusIngest")
    yield tenant
    cleanup_tenant(tenant)


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
