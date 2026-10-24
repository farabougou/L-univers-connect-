"""Connecteur MQTT générique, en lecture seule (ADR 012 §2.12 : SDK de
connecteur). Quatrième protocole de terrain après Modbus, BACnet et OPC UA
(feature-benchmark-matrix.md, ligne « Connecteurs protocoles terrain »).

Contrairement aux trois autres, MQTT n'est pas un protocole de type
requête/réponse (demander une valeur à un serveur) mais de publication/
abonnement : un appareil ou une passerelle publie ses valeurs sur des sujets
(« topics »), ce connecteur s'y abonne et attend ce qui arrive. Pour rester
compatible avec le même modèle de relève périodique que les trois autres
démons (se connecter, lire l'état courant, se déconnecter), ce module
s'appuie sur les messages retenus (« retained ») du courtier MQTT : un
courtier bien configuré renvoie immédiatement la dernière valeur publiée sur
un sujet dès l'abonnement, sans attendre une nouvelle publication. Un sujet
qui n'a jamais reçu de message retenu, ou dont la valeur n'arrive pas avant
`timeout`, est un échec de lecture — jamais une valeur inventée.

Lecture seule par construction (règle non négociable 1) : ce module n'utilise
que l'abonnement (`subscribe`) et ne propose aucune fonction de publication
(`publish` n'apparaît nulle part ici).
"""

import threading
from dataclasses import dataclass

import paho.mqtt.client as mqtt


class MqttReadError(Exception):
    """Échec de lecture d'un ou plusieurs sujets MQTT (connexion, courtier,
    sujet jamais publié, délai dépassé)."""


@dataclass(frozen=True)
class MqttPoint:
    """Un point mesuré, décrit par le sujet MQTT où sa valeur est publiée
    (ex. "capteurs/cta-01/temperature-depart")."""

    name: str
    topic: str
    unit: str = ""


def find_point_by_name(points: list[MqttPoint], name: str) -> MqttPoint:
    for point in points:
        if point.name == name:
            return point
    known = ", ".join(point.name for point in points)
    raise ValueError(f"Point MQTT inconnu : {name} (connus : {known})")


def read_mqtt_points(
    host: str,
    port: int,
    points: list[MqttPoint],
    *,
    timeout: float = 5.0,
) -> dict[str, float]:
    """Lit une liste de points sur un courtier MQTT. Renvoie nom → valeur.

    Se connecte, s'abonne à chaque sujet, attend jusqu'à `timeout` secondes
    que tous les points aient reçu une valeur (retenue ou publiée pendant
    l'attente), puis se déconnecte. Lève `MqttReadError` si la connexion
    échoue ou si au moins un point n'a reçu aucune valeur dans le délai —
    jamais un résultat partiel silencieux."""
    topic_to_name = {point.topic: point.name for point in points}
    values: dict[str, float] = {}
    all_received = threading.Event()
    invalid_payloads: dict[str, str] = {}

    def on_message(_client: mqtt.Client, _userdata: None, message: mqtt.MQTTMessage) -> None:
        name = topic_to_name.get(message.topic)
        if name is None or name in values:
            return
        try:
            values[name] = float(message.payload.decode())
        except (UnicodeDecodeError, ValueError):
            invalid_payloads[name] = message.topic
            return
        if len(values) == len(points):
            all_received.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    try:
        client.connect(host, port, keepalive=max(int(timeout), 1))
    except (OSError, ValueError) as exc:
        raise MqttReadError(f"Connexion impossible à {host}:{port} : {exc}") from exc

    try:
        for point in points:
            client.subscribe(point.topic)
        client.loop_start()
        all_received.wait(timeout=timeout)
    finally:
        client.loop_stop()
        client.disconnect()

    if invalid_payloads:
        names = ", ".join(sorted(invalid_payloads))
        raise MqttReadError(f"Valeur non numérique reçue pour : {names}")
    missing = [point.name for point in points if point.name not in values]
    if missing:
        raise MqttReadError(
            f"Aucune valeur reçue avant le délai ({timeout:g}s) pour : {', '.join(missing)}"
        )
    return values
