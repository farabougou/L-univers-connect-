"""Tests de l'interface CommandExecutor (ADR 017 §4.1, incrément 4) — contre
un vrai relais Modbus simulé (pymodbus), pas un mock : un test qui passe ici
prouve que `SimulatedExecutor` écrit et relit réellement, exactement comme le
faisait l'appel direct qu'il remplace dans scripts/modbus_daemon.py (voir
tests/test_modbus_daemon_commands.py pour la preuve de bout en bout à
travers le vrai démon, inchangée par ce refactor)."""

import threading
import time

import pytest
from pymodbus.server import ServerStop, StartTcpServer

from app.connectors.executors import SimulatedExecutor, resolve_executor
from app.connectors.simulated_relay import SIMULATED_RELAY_POINTS
from scripts.simulated_relay_simulator import build_context

PORT = 5923


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


def test_resolve_executor_returns_the_simulated_executor_for_simulated_relay() -> None:
    assert isinstance(resolve_executor("simulated_relay"), SimulatedExecutor)


def test_resolve_executor_rejects_an_unknown_device_type() -> None:
    with pytest.raises(ValueError, match="aucun exécuteur de commande"):
        resolve_executor("sdm120")


def test_execute_writes_and_reads_back_the_real_value() -> None:
    executor = resolve_executor("simulated_relay")
    register = SIMULATED_RELAY_POINTS[0]

    result = executor.execute(host="127.0.0.1", port=PORT, register=register, requested_value=1.0)
    assert result.success is True
    assert result.actual_value == 1.0
    assert result.failure_reason is None

    result = executor.execute(host="127.0.0.1", port=PORT, register=register, requested_value=0.0)
    assert result.success is True
    assert result.actual_value == 0.0


def test_execute_reports_a_stable_failure_code_when_unreachable() -> None:
    executor = resolve_executor("simulated_relay")
    register = SIMULATED_RELAY_POINTS[0]

    # Port fermé, jamais un vrai équipement : voir CLAUDE.md, règle non
    # négociable 1 — cet exécuteur n'écrit jamais ailleurs qu'ici.
    result = executor.execute(host="127.0.0.1", port=1, register=register, requested_value=1.0)
    assert result.success is False
    assert result.actual_value is None
    assert result.failure_reason == "MODBUS_WRITE_ERROR"
