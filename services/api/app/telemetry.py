import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection


def record_measurement(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    metric: str,
    value: float,
    unit: str,
    measured_at: datetime,
    source: str = "simulator",
    functional_location_id: uuid.UUID | None = None,
    physical_unit_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Enregistre une mesure de télémétrie déjà relevée.

    Lecture seule par construction : cette fonction ne fait qu'insérer une
    valeur, jamais elle n'écrit vers un équipement (règle non négociable 1).
    Une mesure n'est jamais modifiée ni supprimée après coup.
    """
    measurement_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO measurements "
            "(id, tenant_id, functional_location_id, physical_unit_id, "
            "metric, value, unit, source, measured_at) "
            "VALUES (:id, :tenant_id, :functional_location_id, :physical_unit_id, "
            ":metric, :value, :unit, :source, :measured_at)"
        ),
        {
            "id": measurement_id,
            "tenant_id": tenant_id,
            "functional_location_id": functional_location_id,
            "physical_unit_id": physical_unit_id,
            "metric": metric,
            "value": value,
            "unit": unit,
            "source": source,
            "measured_at": measured_at,
        },
    )
    return measurement_id
