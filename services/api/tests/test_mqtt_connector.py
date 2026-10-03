"""Connecteur MQTT contre un vrai courtier (mosquitto, le binaire de
référence du protocole — aucun matériel requis).

Le simulateur est un vrai courtier MQTT lancé comme sous-processus : ce test
prouve que le connecteur dialogue réellement en MQTT (connexion, abonnement,
message retenu), pas seulement contre une fonction Python. Mêmes principes
que tests/test_opcua_connector.py et tests/test_executors.py (serveur réel
du protocole, jamais un simulacre)."""

import socket
import subprocess
import time

import paho.mqtt.publish as mqtt_publish
import pytest

from app.connectors.mqtt import MqttPoint, MqttReadError, find_point_by_name, read_mqtt_points

FAKE_VALUES = {"temperature": 21.5, "setpoint": 19.0}


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
        for name, value in FAKE_VALUES.items():
            mqtt_publish.single(
                f"paios-test/{name}",
                payload=str(value),
                hostname="127.0.0.1",
                port=port,
                retain=True,
            )
        yield port
    finally:
        process.terminate()
        process.wait(timeout=5)


def _points() -> list[MqttPoint]:
    return [
        MqttPoint(name="temperature", topic="paios-test/temperature"),
        MqttPoint(name="setpoint", topic="paios-test/setpoint"),
    ]


def test_lit_tous_les_points_avec_la_bonne_valeur(mqtt_broker) -> None:
    values = read_mqtt_points("127.0.0.1", mqtt_broker, _points())

    assert values == FAKE_VALUES


def test_courtier_injoignable_leve_une_erreur_explicite(mqtt_broker) -> None:
    with pytest.raises(MqttReadError):
        read_mqtt_points("127.0.0.1", _free_port(), _points(), timeout=1.0)


def test_sujet_jamais_publie_leve_une_erreur_explicite(mqtt_broker) -> None:
    unknown = [MqttPoint(name="inconnu", topic="paios-test/jamais-publie")]
    with pytest.raises(MqttReadError):
        read_mqtt_points("127.0.0.1", mqtt_broker, unknown, timeout=1.0)


def test_valeur_non_numerique_leve_une_erreur_explicite(mqtt_broker) -> None:
    mqtt_publish.single(
        "paios-test/texte",
        payload="pas-un-nombre",
        hostname="127.0.0.1",
        port=mqtt_broker,
        retain=True,
    )
    bad_point = [MqttPoint(name="texte", topic="paios-test/texte")]
    with pytest.raises(MqttReadError):
        read_mqtt_points("127.0.0.1", mqtt_broker, bad_point, timeout=1.0)


def test_point_inconnu_leve_une_erreur_explicite() -> None:
    with pytest.raises(ValueError, match="Point MQTT inconnu"):
        find_point_by_name(_points(), "fictif")
