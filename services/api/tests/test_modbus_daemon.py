"""Démon de sondage : plusieurs tours, un tour raté n'arrête pas les suivants,
et une mesure lue pendant une coupure de la base repart au lieu d'être perdue.

`run(max_cycles=...)` (scripts/modbus_daemon.py) est le même code que celui
lancé en continu sur site, juste borné pour le test.
"""

import threading
import time

import pytest
from pymodbus.server import ServerStop, StartTcpServer
from sqlalchemy import text

import scripts.modbus_daemon as daemon
from app.connectors.modbus import find_register_by_name
from app.connectors.offline_buffer import OfflineBuffer
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


def test_plusieurs_tours_enregistrent_plusieurs_mesures(tenant, tmp_path):
    cycles = run(
        tenant_id=tenant["tenant_id"],
        point_id=tenant["point_id"],
        host="127.0.0.1",
        port=PORT,
        register=REGISTER,
        interval_seconds=0.05,
        buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
        max_cycles=3,
    )

    assert cycles == 3
    assert _measurement_count(tenant["tenant_id"]) == 3


def test_un_tour_rate_n_arrete_pas_le_demon(tenant, tmp_path):
    # Port sans rien qui écoute : chaque tour échoue, mais la boucle continue
    # jusqu'à max_cycles au lieu de lever une exception. Rien à mettre au
    # tampon puisqu'aucune valeur n'a jamais été lue.
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    cycles = run(
        tenant_id=tenant["tenant_id"],
        point_id=tenant["point_id"],
        host="127.0.0.1",
        port=1,
        register=REGISTER,
        interval_seconds=0.05,
        buffer=buffer,
        max_cycles=2,
    )

    assert cycles == 2
    assert _measurement_count(tenant["tenant_id"]) == 0
    assert buffer.pending() == []


def test_base_injoignable_met_en_tampon_puis_transmet_tout_au_retour(tenant, tmp_path, monkeypatch):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")

    def _echoue_toujours(*args, **kwargs):
        raise RuntimeError("base injoignable (simulé)")

    monkeypatch.setattr(daemon, "ingest_measurements", _echoue_toujours)
    run(
        tenant_id=tenant["tenant_id"],
        point_id=tenant["point_id"],
        host="127.0.0.1",
        port=PORT,
        register=REGISTER,
        interval_seconds=0.05,
        buffer=buffer,
        max_cycles=2,
    )

    # Deux lectures réussies, deux échecs d'écriture : rien en base, tout au tampon.
    assert _measurement_count(tenant["tenant_id"]) == 0
    assert len(buffer.pending()) == 2

    monkeypatch.undo()
    cycles = run(
        tenant_id=tenant["tenant_id"],
        point_id=tenant["point_id"],
        host="127.0.0.1",
        port=PORT,
        register=REGISTER,
        interval_seconds=0.05,
        buffer=buffer,
        max_cycles=1,
    )

    # Le tour suivant, une fois la base à nouveau joignable, renvoie les deux
    # mesures en attente en plus de la nouvelle : rien n'a été perdu.
    assert cycles == 1
    assert _measurement_count(tenant["tenant_id"]) == 3
    assert buffer.pending() == []
