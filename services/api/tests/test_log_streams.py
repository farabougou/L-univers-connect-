"""Répartition des journaux entre sortie standard et sortie d'erreur
(app/log_streams.py, scripts/uvicorn-logging.json).

Constat du 21/10/2026 sur Railway : uvicorn et alembic écrivaient leurs
messages d'information sur la sortie d'erreur, que Railway classe « error ».
Chaque démarrage sain apparaissait donc en rouge. Ces tests prouvent que
l'information sort sur la sortie standard et que les avertissements et
erreurs restent sur la sortie d'erreur : une vraie panne reste visible.

Chaque cas tourne dans un processus Python séparé : appliquer la
configuration dans le processus de test fermerait les gestionnaires de
journaux de pytest (`logging.config.dictConfig` ferme les gestionnaires
existants) et fausserait la lecture des deux sorties.
"""

import subprocess
import sys
from configparser import ConfigParser
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parent.parent

_EMIT = """
import json, logging, logging.config
with open("scripts/uvicorn-logging.json") as handle:
    logging.config.dictConfig(json.load(handle))
logging.getLogger({logger!r}).log(logging.{level}, {message!r})
"""


def _emit(logger: str, level: str, message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _EMIT.format(logger=logger, level=level, message=message)],
        capture_output=True,
        text=True,
        cwd=API_ROOT,
        check=True,
    )


def test_uvicorn_information_sort_sur_la_sortie_standard() -> None:
    result = _emit("uvicorn.error", "INFO", "Uvicorn running on http://0.0.0.0:8080")

    assert "Uvicorn running on http://0.0.0.0:8080" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("level", ["WARNING", "ERROR", "CRITICAL"])
def test_uvicorn_avertissements_et_erreurs_restent_sur_la_sortie_d_erreur(level: str) -> None:
    result = _emit("uvicorn.error", level, "Exception in ASGI application")

    assert "Exception in ASGI application" in result.stderr
    assert result.stdout == ""


def test_uvicorn_une_information_n_est_jamais_dupliquee_sur_la_sortie_d_erreur() -> None:
    """Deux gestionnaires sont attachés au même journal : l'information ne doit
    sortir qu'une fois, sur la sortie standard, jamais aussi sur l'autre."""
    result = _emit("uvicorn.error", "INFO", "Application startup complete.")

    assert result.stdout.count("Application startup complete.") == 1
    assert result.stderr == ""


def test_alembic_ecrit_sur_la_sortie_standard() -> None:
    parser = ConfigParser()
    parser.read(API_ROOT / "alembic.ini")

    assert parser.get("handler_console", "args").strip() == "(sys.stdout,)"


def test_le_demarrage_du_conteneur_utilise_la_configuration_des_journaux() -> None:
    entrypoint = (API_ROOT / "scripts" / "docker-entrypoint.sh").read_text()

    assert "--log-config" in entrypoint
    assert "uvicorn-logging.json" in entrypoint
