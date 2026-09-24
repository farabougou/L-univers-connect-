"""Démon de sondage : plusieurs tours, et un tour raté n'arrête pas les suivants.

`run(max_cycles=...)` (scripts/modbus_daemon.py) est le même code que celui
lancé en continu sur site, juste borné pour le test.
"""

import threading
import time

import pytest
from pymodbus.server import ServerStop, StartTcpServer
from sqlalchemy import text

from app.connectors.modbus import find_register_by_name
from app.connectors.sdm120 import SDM120_POINTS
from app.db import engine
from app.tenancy import set_tenant_context
from scripts.modbus_daemon import run
from scripts.modbus_simulator import build_context
from tests.modbus_fixtures import cleanup_tenant, create_tenant_with_energy_point

PORT = 5097
REGISTER = find_register_by_name(SDM120_POINTS, "total_active_energy")


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
def tenant():
    created = create_tenant_with_energy_point("ClientModbusDaemon")
    yield created
    cleanup_tenant(created)


def _measurement_count(tenant_id) -> int:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        return connection.execute(
            text("SELECT count(*) FROM measurements WHERE tenant_id = :id"), {"id": tenant_id}
        ).scalar()


def test_plusieurs_tours_enregistrent_plusieurs_mesures(tenant):
    cycles = run(
        tenant_id=tenant["tenant_id"],
        point_id=tenant["point_id"],
        host="127.0.0.1",
        port=PORT,
        register=REGISTER,
        interval_seconds=0.05,
        max_cycles=3,
    )

    assert cycles == 3
    assert _measurement_count(tenant["tenant_id"]) == 3


def test_un_tour_rate_n_arrete_pas_le_demon(tenant):
    # Port sans rien qui écoute : chaque tour échoue, mais la boucle continue
    # jusqu'à max_cycles au lieu de lever une exception.
    cycles = run(
        tenant_id=tenant["tenant_id"],
        point_id=tenant["point_id"],
        host="127.0.0.1",
        port=1,
        register=REGISTER,
        interval_seconds=0.05,
        max_cycles=2,
    )

    assert cycles == 2
    assert _measurement_count(tenant["tenant_id"]) == 0
