"""Contexte météorologique (Weather Context) : une température moyenne
quotidienne par site, saisie manuellement pour la V1 (aucune intégration
météo externe pour l'instant — voir app/energy/__init__.py, DEFER).

Les degrés-jours ne sont jamais stockés ici : ils dépendent d'une
température de base qui appartient à la référence énergétique
(`app/energy/baseline.py`), pas à la donnée météo elle-même. Une même
observation sert donc à n'importe quelle référence, présente ou future,
sans être recopiée.
"""

import datetime
import uuid
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection

WEATHER_SOURCES = frozenset({"manual"})

_COLUMNS = (
    "id, tenant_id, site_id, observed_date, mean_temperature_celsius, source, "
    "station_ref, created_by, created_at"
)


def record_weather_observation(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    observed_date: datetime.date,
    mean_temperature_celsius: float,
    created_by: str,
    source: str = "manual",
    station_ref: str | None = None,
) -> uuid.UUID:
    """Une observation par site et par jour : une nouvelle valeur pour un
    jour déjà saisi remplace l'ancienne (donnée corrigée), jamais un doublon
    silencieux — voir `upsert`."""
    observation_id = uuid.uuid4()
    existing = connection.execute(
        text(
            "SELECT id FROM weather_observations WHERE tenant_id = :tenant_id "
            "AND site_id = :site_id AND observed_date = :observed_date"
        ),
        {"tenant_id": tenant_id, "site_id": site_id, "observed_date": observed_date},
    ).scalar()
    if existing is not None:
        connection.execute(
            text(
                "UPDATE weather_observations SET mean_temperature_celsius = :value, "
                "source = :source, station_ref = :station_ref, created_by = :created_by, "
                "created_at = now() WHERE id = :id"
            ),
            {
                "value": mean_temperature_celsius,
                "source": source,
                "station_ref": station_ref,
                "created_by": created_by,
                "id": existing,
            },
        )
        return existing
    connection.execute(
        text(
            "INSERT INTO weather_observations (id, tenant_id, site_id, observed_date, "
            "mean_temperature_celsius, source, station_ref, created_by) VALUES "
            "(:id, :tenant_id, :site_id, :observed_date, :value, :source, :station_ref, "
            ":created_by)"
        ),
        {
            "id": observation_id,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "observed_date": observed_date,
            "value": mean_temperature_celsius,
            "source": source,
            "station_ref": station_ref,
            "created_by": created_by,
        },
    )
    return observation_id


def list_weather_observations(
    connection: Connection,
    *,
    site_id: uuid.UUID,
    period_start: datetime.date,
    period_end: datetime.date,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(
                f"SELECT {_COLUMNS} FROM weather_observations WHERE site_id = :site_id "
                "AND observed_date >= :start AND observed_date <= :end ORDER BY observed_date"
            ),
            {"site_id": site_id, "start": period_start, "end": period_end},
        ).mappings()
    ]


def aggregate_degree_days(
    connection: Connection,
    *,
    site_id: uuid.UUID,
    period_start: datetime.date,
    period_end: datetime.date,
    base_temperature_celsius: float,
    kind: Literal["heating", "cooling"],
) -> dict[str, Any]:
    """Degrés-jours (chauffage ou climatisation) sur une période, dérivés des
    températures moyennes quotidiennes observées. Renvoie aussi les jours
    manquants : une période mal couverte ne doit jamais être présentée
    comme fiable sans le dire (même principe que la complétude des mesures,
    app/trust.py)."""
    observations = list_weather_observations(
        connection, site_id=site_id, period_start=period_start, period_end=period_end
    )
    days_total = (period_end - period_start).days + 1
    degree_days = 0.0
    for observation in observations:
        delta = observation["mean_temperature_celsius"] - base_temperature_celsius
        if kind == "heating":
            degree_days += max(0.0, -delta)
        else:
            degree_days += max(0.0, delta)
    return {
        "degree_days": round(degree_days, 2) if observations else None,
        "days_total": days_total,
        "days_observed": len(observations),
        "days_missing": days_total - len(observations),
        "sources": sorted({observation["source"] for observation in observations}),
    }
