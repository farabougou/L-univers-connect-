"""Boucle de commande complète, à travers le vrai démon : une commande créée
via l'API est récupérée par le démon au tour suivant, exécutée sur un relais
simulé (jamais un vrai équipement — voir CLAUDE.md), vérifiée, et son
résultat apparaît aussi dans la télémétrie (Actual State), exactement comme
n'importe quel point.
"""

import threading
import time

import pytest
from pymodbus.server import ServerStop, StartTcpServer
from sqlalchemy import text
from starlette.testclient import TestClient

from app.commands import create_command, get_command
from app.connectors.edge_client import EdgeApiClient
from app.connectors.offline_buffer import OfflineBuffer
from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from scripts.modbus_daemon import run
from scripts.simulated_relay_simulator import build_context
from tests.modbus_fixtures import (
    activate_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_point,
    provision_device_for_tenant,
)

PORT = 5922


@pytest.fixture(scope="module", autouse=True)
def relay_simulator():
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
def commandable_tenant():
    created = create_tenant_with_energy_point("ClientDaemonCommandes")
    activate_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=PORT,
        device_type="simulated_relay",
        points=[{"point_id": str(created["point_id"]), "register_name": "relay_state"}],
    )
    secret = provision_device_for_tenant(tenant_id=created["tenant_id"], device_id="relais-daemon")
    yield {**created, "device_id": "relais-daemon", "secret": secret}
    cleanup_tenant(created)


def _api(tenant: dict) -> EdgeApiClient:
    return EdgeApiClient(
        client=TestClient(app),
        tenant_id=tenant["tenant_id"],
        device_id=tenant["device_id"],
        secret=tenant["secret"],
    )


def _measurement_value(tenant_id, point_id) -> float | None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        return connection.execute(
            text(
                "SELECT value FROM measurements WHERE point_id = :point_id "
                "ORDER BY measured_at DESC LIMIT 1"
            ),
            {"point_id": point_id},
        ).scalar()


def test_commande_executee_verifiee_et_visible_en_telemetrie(commandable_tenant, tmp_path):
    with engine.begin() as connection:
        set_tenant_context(connection, commandable_tenant["tenant_id"])
        command_id = create_command(
            connection,
            tenant_id=commandable_tenant["tenant_id"],
            point_id=commandable_tenant["point_id"],
            requested_value=1.0,
            requested_by="mohamed",
        )

    with _api(commandable_tenant) as api:
        cycles = run(
            api=api,
            equipment_id=commandable_tenant["location_id"],
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            source="simulated_relay",
            max_cycles=1,
        )

    assert cycles == 1
    with engine.begin() as connection:
        set_tenant_context(connection, commandable_tenant["tenant_id"])
        command = get_command(connection, command_id)
    assert command["status"] == "verified"
    assert command["actual_value"] == 1.0

    assert (
        _measurement_value(commandable_tenant["tenant_id"], commandable_tenant["point_id"]) == 1.0
    )


def test_deux_commandes_successives_sont_toutes_deux_verifiees(commandable_tenant, tmp_path):
    """Éteindre puis rallumer : deux tours, deux commandes, chacune vérifiée
    contre la valeur réellement relue à ce tour-là."""
    with engine.begin() as connection:
        set_tenant_context(connection, commandable_tenant["tenant_id"])
        first_id = create_command(
            connection,
            tenant_id=commandable_tenant["tenant_id"],
            point_id=commandable_tenant["point_id"],
            requested_value=1.0,
            requested_by="mohamed",
        )

    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    with _api(commandable_tenant) as api:
        run(
            api=api,
            equipment_id=commandable_tenant["location_id"],
            interval_seconds=0.05,
            buffer=buffer,
            source="simulated_relay",
            max_cycles=1,
        )
        with engine.begin() as connection:
            set_tenant_context(connection, commandable_tenant["tenant_id"])
            second_id = create_command(
                connection,
                tenant_id=commandable_tenant["tenant_id"],
                point_id=commandable_tenant["point_id"],
                requested_value=0.0,
                requested_by="mohamed",
            )
        run(
            api=api,
            equipment_id=commandable_tenant["location_id"],
            interval_seconds=0.05,
            buffer=buffer,
            source="simulated_relay",
            max_cycles=1,
        )

    with engine.begin() as connection:
        set_tenant_context(connection, commandable_tenant["tenant_id"])
        first = get_command(connection, first_id)
        second = get_command(connection, second_id)

    assert first["status"] == "verified" and first["actual_value"] == 1.0
    assert second["status"] == "verified" and second["actual_value"] == 0.0
    assert (
        _measurement_value(commandable_tenant["tenant_id"], commandable_tenant["point_id"]) == 0.0
    )
