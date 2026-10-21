"""Démon de sondage MQTT : mêmes garanties que le démon OPC UA
(scripts/opcua_daemon.py, tests/test_opcua_daemon.py) — voir
app/connectors/mqtt.py et app/connectors/device_mapping.py.

Ces tests appellent l'application FastAPI réelle par HTTP (ASGITransport),
exactement le chemin qu'emprunte un appareil sur site, contre un vrai
courtier MQTT (mosquitto, sous-processus), pas un mock."""

import socket
import subprocess
import time

import paho.mqtt.publish as mqtt_publish
import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

import scripts.mqtt_daemon as daemon
from app.connectors.edge_client import EdgeApiClient
from app.connectors.offline_buffer import OfflineBuffer
from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from scripts.mqtt_daemon import run
from tests import daemon_resilience as resilience
from tests.modbus_fixtures import (
    activate_mqtt_device_mapping,
    cleanup_tenant,
    create_tenant_with_energy_and_power_points,
    create_tenant_with_energy_point,
    provision_device_for_tenant,
)

FAKE_VALUE = 12.5


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_listening(port: int, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"mosquitto n'a pas démarré sur le port {port}")


@pytest.fixture(scope="module", autouse=True)
def mqtt_broker():
    port = _free_port()
    process = subprocess.Popen(
        ["mosquitto", "-p", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until_listening(port)
        mqtt_publish.single(
            "paios-test/energie",
            payload=str(FAKE_VALUE),
            hostname="127.0.0.1",
            port=port,
            retain=True,
        )
        mqtt_publish.single(
            "paios-test/puissance",
            payload=str(FAKE_VALUE * 2),
            hostname="127.0.0.1",
            port=port,
            retain=True,
        )
        yield port
    finally:
        process.terminate()
        process.wait(timeout=5)


def _api(tenant: dict) -> EdgeApiClient:
    return EdgeApiClient(
        client=TestClient(app),
        tenant_id=tenant["tenant_id"],
        device_id=tenant["device_id"],
        secret=tenant["secret"],
    )


def _measurement_count(tenant_id) -> int:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        return connection.execute(
            text("SELECT count(*) FROM measurements WHERE tenant_id = :id"), {"id": tenant_id}
        ).scalar()


@pytest.fixture
def tenant(mqtt_broker):
    created = create_tenant_with_energy_point("ClientMqttDaemon")
    activate_mqtt_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=mqtt_broker,
        points=[{"point_id": str(created["point_id"]), "topic": "paios-test/energie"}],
    )
    secret = provision_device_for_tenant(tenant_id=created["tenant_id"], device_id="mqtt-daemon")
    yield {**created, "device_id": "mqtt-daemon", "secret": secret}
    cleanup_tenant(created)


@pytest.fixture
def tenant_two_points(mqtt_broker):
    created = create_tenant_with_energy_and_power_points("ClientMqttDaemonMulti")
    activate_mqtt_device_mapping(
        tenant_id=created["tenant_id"],
        equipment_id=created["location_id"],
        host="127.0.0.1",
        port=mqtt_broker,
        points=[
            {"point_id": str(created["energy_point_id"]), "topic": "paios-test/energie"},
            {"point_id": str(created["power_point_id"]), "topic": "paios-test/puissance"},
        ],
    )
    secret = provision_device_for_tenant(tenant_id=created["tenant_id"], device_id="mqtt-daemon")
    yield {**created, "device_id": "mqtt-daemon", "secret": secret}
    cleanup_tenant(created)


def test_plusieurs_tours_enregistrent_plusieurs_mesures(tenant, tmp_path):
    with _api(tenant) as api:
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=3,
        )

    assert cycles == 3
    assert _measurement_count(tenant["tenant_id"]) == 3


def test_deux_points_du_meme_appareil_sont_releves_ensemble(tenant_two_points, tmp_path):
    with _api(tenant_two_points) as api:
        cycles = run(
            api=api,
            equipment_id=tenant_two_points["location_id"],
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=1,
        )

    assert cycles == 1
    assert _measurement_count(tenant_two_points["tenant_id"]) == 2


def test_aucune_configuration_active_arrete_le_demarrage(tenant, tmp_path):
    equipement_sans_mapping = tenant["point_id"]  # n'importe quel id sans mapping actif
    with _api(tenant) as api, pytest.raises(SystemExit):
        run(
            api=api,
            equipment_id=equipement_sans_mapping,
            interval_seconds=0.05,
            buffer=OfflineBuffer(tmp_path / "buffer.jsonl"),
            max_cycles=1,
        )


def test_un_tour_rate_n_arrete_pas_le_demon(tenant, tmp_path):
    # Reconfigure vers un courtier injoignable : chaque tour échoue côté
    # lecture MQTT (connexion refusée), mais la boucle continue jusqu'à
    # max_cycles au lieu de lever une exception.
    activate_mqtt_device_mapping(
        tenant_id=tenant["tenant_id"],
        equipment_id=tenant["location_id"],
        host="127.0.0.1",
        port=48988,  # rien n'écoute ici
        points=[{"point_id": str(tenant["point_id"]), "topic": "paios-test/jamais-publie"}],
    )
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    with _api(tenant) as api:
        cycles = run(
            api=api,
            equipment_id=tenant["location_id"],
            interval_seconds=0.05,
            buffer=buffer,
            max_cycles=2,
        )

    assert cycles == 2
    assert _measurement_count(tenant["tenant_id"]) == 0


# --- Résilience commune aux démons (V5.1) : mêmes garanties que le démon Modbus ---------


def _kwargs(tenant, tmp_path):
    return dict(
        run=run,
        daemon=daemon,
        make_api=_api,
        tenant=tenant,
        count=_measurement_count,
        tmp_path=tmp_path,
    )


def test_vraie_coupure_de_l_api_le_demon_continue_de_relever_et_ne_perd_rien(
    tenant, tmp_path, monkeypatch
):
    resilience.check_real_outage_loses_nothing(**_kwargs(tenant, tmp_path), monkeypatch=monkeypatch)


def test_demarrage_pendant_une_coupure_de_l_api_n_arrete_pas_le_demon(
    tenant, tmp_path, monkeypatch
):
    resilience.check_start_during_outage_does_not_crash(
        **_kwargs(tenant, tmp_path), monkeypatch=monkeypatch
    )


def test_configuration_retiree_pendant_une_coupure_n_est_plus_relevee_au_retour(
    tenant, tmp_path, monkeypatch
):
    resilience.check_removed_config_is_not_read_from_memory(
        **_kwargs(tenant, tmp_path), monkeypatch=monkeypatch
    )


def test_arret_entre_l_envoi_et_le_vidage_du_tampon_ne_cree_aucun_doublon(
    tenant, tmp_path, monkeypatch
):
    resilience.check_kill_before_buffer_clear_creates_no_duplicate(
        **_kwargs(tenant, tmp_path), monkeypatch=monkeypatch
    )


def test_tampon_tronque_par_une_coupure_de_courant_ne_bloque_pas_le_demon(tenant, tmp_path):
    resilience.check_truncated_buffer_does_not_block_the_daemon(
        run=run,
        source="mqtt",
        make_api=_api,
        tenant=tenant,
        count=_measurement_count,
        tmp_path=tmp_path,
    )


def test_un_refus_de_l_api_est_journalise_en_erreur(tenant, tmp_path, monkeypatch, caplog):
    resilience.check_api_refusal_is_logged_as_an_error(
        run=run,
        make_api=_api,
        tenant=tenant,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        caplog=caplog,
    )
