"""CommandExecutor (ADR 017 §4.1, Virtual Commissioning Lab, incrément 4) :
formalise le point où le démon choisit COMMENT exécuter une commande déjà
autorisée, pour que ce choix soit explicite et remplaçable — jamais un
deuxième moteur de commande par rapport à `app/commands.py`, qui reste
inchangé (cycle `pending → sent → acknowledged → verified`, mêmes rôles,
même audit ; voir ADR 016, « jamais un second moteur »).

Avant cette interface, le démon (`scripts/modbus_daemon.py`) appelait
directement `write_modbus_coil` puis `read_modbus_points`, sans point de
sélection explicite — un REFACTOR de seam, aucune nouvelle logique métier :
le comportement observable ne change pas (mêmes tests,
`tests/test_modbus_daemon_commands.py`, inchangés et toujours au vert).

Une seule implémentation aujourd'hui : `SimulatedExecutor`, qui appelle
`app.connectors.simulated_actuator.write_modbus_coil` — la seule fonction
d'écriture du dépôt, réservée au `device_type` explicitement simulé
("simulated_relay", voir `app.connectors.device_mapping.SIMULATED_DEVICE_TYPES`
et `app.commands._assert_point_is_commandable`, qui restent les deux
vérifications indépendantes avant qu'une commande n'atteigne cet exécuteur).
Le jour où le terrain BACnet ou Modbus réel sera autorisé (ADR 016,
conditions inchangées : validation terrain de la lecture seule + décision
explicite séparée de Mohamed), un exécuteur réel s'ajoutera derrière cette
même interface, sans toucher au moteur métier ni à la boucle du démon.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from app.connectors.modbus import ModbusReadError, ModbusRegisterPoint, read_modbus_points
from app.connectors.simulated_actuator import write_modbus_coil

logger = logging.getLogger("paios.connectors.executors")


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    actual_value: float | None
    failure_reason: str | None


class CommandExecutor(Protocol):
    """Exécute une commande déjà autorisée (`app.commands` a déjà vérifié que
    le point est commandable) et relit l'état réel pour vérification —
    jamais l'inverse : une commande n'est jamais déclarée réussie avant
    relecture (même principe que le démon avant cette interface)."""

    def execute(
        self, *, host: str, port: int, register: ModbusRegisterPoint, requested_value: float
    ) -> ExecutionResult: ...


class SimulatedExecutor:
    """Unique implémentation aujourd'hui — écrit vers l'appareil Modbus
    explicitement simulé, jamais un équipement réel (vérifié par
    l'appelant avant de choisir cet exécuteur, voir `resolve_executor`)."""

    def execute(
        self, *, host: str, port: int, register: ModbusRegisterPoint, requested_value: float
    ) -> ExecutionResult:
        try:
            write_modbus_coil(host, port, register.address, bool(requested_value))
            actual_value = read_modbus_points(host, port, [register])[register.name]
            return ExecutionResult(success=True, actual_value=actual_value, failure_reason=None)
        except ModbusReadError as exc:
            # Code stable stocké et affiché (ADR 013) ; le détail de
            # l'exception reste dans les journaux, jamais dans la donnée
            # persistée ou montrée à une personne.
            logger.error(f"exécution de commande impossible sur {host}:{port} : {exc}")
            return ExecutionResult(
                success=False, actual_value=None, failure_reason="MODBUS_WRITE_ERROR"
            )


# Un seul type commandable aujourd'hui (voir CLAUDE.md, règle non
# négociable 1) — une table, pas une condition, pour que l'ajout d'un futur
# exécuteur réel reste un ajout d'entrée, jamais une nouvelle branche de code.
_EXECUTORS: dict[str, CommandExecutor] = {"simulated_relay": SimulatedExecutor()}


def resolve_executor(device_type: str) -> CommandExecutor:
    try:
        return _EXECUTORS[device_type]
    except KeyError:
        raise ValueError(
            f"aucun exécuteur de commande pour device_type={device_type!r} "
            f"(disponibles : {', '.join(sorted(_EXECUTORS))})"
        ) from None
