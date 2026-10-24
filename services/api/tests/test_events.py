"""Journal des événements (app/events.py) : isolation tenant obligatoire
pour toute nouvelle table (règle non négociable 2)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from app.db import engine
from app.events import list_events_for_subject, record_event
from app.tenancy import set_tenant_context

T0 = datetime(2026, 9, 24, 14, 0, tzinfo=UTC)


def _tenant() -> uuid.UUID:
    tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'ClientEvents', :slug)"),
            {"id": tenant_id, "slug": f"events-{tenant_id}"},
        )
    return tenant_id


def _cleanup(tenant_id: uuid.UUID) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        connection.execute(text("DELETE FROM events WHERE tenant_id = :id"), {"id": tenant_id})
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def test_enregistrer_puis_lister_les_evenements_d_un_sujet():
    tenant_id = _tenant()
    subject_id = uuid.uuid4()
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_id)
            record_event(
                connection,
                tenant_id=tenant_id,
                event_type="DEVICE_WENT_OFFLINE",
                subject_type="functional_location",
                subject_id=subject_id,
                payload={"as_of": "2026-09-24T13:00:00Z"},
                occurred_at=T0,
            )
            record_event(
                connection,
                tenant_id=tenant_id,
                event_type="DEVICE_CAME_ONLINE",
                subject_type="functional_location",
                subject_id=subject_id,
                occurred_at=T0,
            )
            events = list_events_for_subject(
                connection, subject_type="functional_location", subject_id=subject_id
            )
        # Même transaction, même horodatage (now() est figé par transaction) :
        # l'ordre entre les deux n'est pas garanti, seul l'ensemble compte ici.
        assert {e["event_type"] for e in events} == {"DEVICE_CAME_ONLINE", "DEVICE_WENT_OFFLINE"}
        offline_event = next(e for e in events if e["event_type"] == "DEVICE_WENT_OFFLINE")
        assert offline_event["payload"] == {"as_of": "2026-09-24T13:00:00Z"}
    finally:
        _cleanup(tenant_id)


def test_un_tenant_ne_voit_pas_les_evenements_de_l_autre():
    tenant_a = _tenant()
    tenant_b = _tenant()
    subject_id = uuid.uuid4()
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a)
            record_event(
                connection,
                tenant_id=tenant_a,
                event_type="DEVICE_WENT_OFFLINE",
                subject_type="functional_location",
                subject_id=subject_id,
                occurred_at=T0,
            )
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_b)
            events = list_events_for_subject(
                connection, subject_type="functional_location", subject_id=subject_id
            )
        assert events == []
    finally:
        _cleanup(tenant_a)
        _cleanup(tenant_b)
