"""Répartition des journaux entre sortie standard et sortie d'erreur.

Railway classe un message « error » dès qu'il sort sur la sortie d'erreur.
Uvicorn et Alembic y écrivent par défaut leurs messages d'information
(« Uvicorn running on ... », « Will assume transactional DDL »), si bien que
chaque démarrage sain apparaissait en rouge dans la console Railway et
noyait les vraies erreurs.

Principe : les messages d'information sortent sur la sortie standard, les
avertissements et erreurs restent sur la sortie d'erreur. Une vraie panne
reste donc visible comme telle (voir scripts/uvicorn-logging.json).
"""

import logging


class BelowWarning(logging.Filter):
    """Ne laisse passer que les enregistrements inférieurs à WARNING."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.WARNING
