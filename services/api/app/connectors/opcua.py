"""Connecteur OPC UA générique, en lecture seule (ADR 012 §2.12 : SDK de
connecteur). Même principe que app/connectors/bacnet.py : le protocole
normalise déjà l'adressage d'une variable (NodeId), aucun catalogue de
registres propre à un fabricant n'est nécessaire ici.

Lecture seule par construction (règle non négociable 1) : ce module
n'utilise que le service Read (`Node.read_value`) et ne propose aucune
fonction d'écriture (`write_value` n'apparaît nulle part ici).

Pont synchrone : la bibliothèque OPC UA (asyncua) est asynchrone. Le reste
du noyau (démon, ingestion) reste synchrone comme pour Modbus et BACnet ;
chaque relève ouvre puis referme sa propre boucle asyncio (`asyncio.run`),
jamais de boucle asyncio qui vivrait en arrière-plan du reste de
l'application.
"""

import asyncio
from dataclasses import dataclass

from asyncua import Client, ua


class OpcuaReadError(Exception):
    """Échec de lecture d'une variable OPC UA (réseau, serveur, NodeId,
    délai dépassé)."""


@dataclass(frozen=True)
class OpcuaPoint:
    """Un point mesuré, décrit par son adressage OPC UA natif (NodeId sous
    forme texte, ex. "ns=2;i=2" ou "ns=3;s=Temperature")."""

    name: str
    node_id: str
    unit: str = ""


def find_point_by_name(points: list[OpcuaPoint], name: str) -> OpcuaPoint:
    for point in points:
        if point.name == name:
            return point
    known = ", ".join(point.name for point in points)
    raise ValueError(f"Point OPC UA inconnu : {name} (connus : {known})")


async def _read_opcua_points_async(
    endpoint_url: str,
    points: list[OpcuaPoint],
    *,
    timeout: float,
) -> dict[str, float]:
    values: dict[str, float] = {}
    try:
        async with Client(url=endpoint_url, timeout=timeout) as client:
            for point in points:
                try:
                    node_id = ua.NodeId.from_string(point.node_id)
                except (ua.UaError, ValueError) as exc:
                    raise OpcuaReadError(
                        f"NodeId invalide pour « {point.name} » : {point.node_id}"
                    ) from exc
                try:
                    value = await asyncio.wait_for(
                        client.get_node(node_id).read_value(), timeout=timeout
                    )
                except TimeoutError as exc:
                    raise OpcuaReadError(
                        f"Délai dépassé en lisant « {point.name} » à {endpoint_url}"
                    ) from exc
                except ua.UaError as exc:
                    raise OpcuaReadError(
                        f"Serveur en erreur pour « {point.name} » : {exc}"
                    ) from exc
                values[point.name] = float(value)
    except OpcuaReadError:
        raise
    except (OSError, TimeoutError, ua.UaError) as exc:
        raise OpcuaReadError(f"Connexion impossible à {endpoint_url} : {exc}") from exc

    return values


def read_opcua_points(
    endpoint_url: str,
    points: list[OpcuaPoint],
    *,
    timeout: float = 5.0,
) -> dict[str, float]:
    """Lit une liste de points sur un serveur OPC UA. Renvoie nom → valeur.

    `endpoint_url` est l'URL complète du point de terminaison (ex.
    `"opc.tcp://192.168.1.50:4840/"`) : contrairement à Modbus et BACnet, le
    protocole encode l'adresse et le chemin du serveur dans une seule URL.
    """
    return asyncio.run(_read_opcua_points_async(endpoint_url, points, timeout=timeout))
