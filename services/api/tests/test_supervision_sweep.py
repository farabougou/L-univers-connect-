"""Balayage périodique (app/supervision_sweep.py) : la supervision doit
détecter une transition même si personne ne consulte l'application
(directive de Mohamed du 24/09/2026, complément)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import text

from app.db import engine
from app.points import create_point, decide_point
from app.supervision_sweep import sweep_once
from app.telemetry import ingest_measurements
from app.tenancy import set_tenant_context

T0 = datetime(2026, 9, 24, 16, 0, tzinfo=UTC)


def _tenant_with_status_point(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    location_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site')"),
            {"id": site_id, "tenant_id": tenant_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'pac-01', 'PAC 01')"
            ),
            {"id": location_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        status_point_id = create_point(
            connection,
            tenant_id=tenant_id,
            code="PAC01-MARCHE",
            name="Marche",
            value_type="boolean",
            point_class="run_status",
            functional_location_id=location_id,
            expected_interval_seconds=60,
            created_by="test",
        )
        decide_point(connection, point_id=status_point_id, decision="validated")
    return {
        "tenant_id": tenant_id,
        "location_id": location_id,
        "status_point_id": status_point_id,
    }


def _cleanup(tenant_id: uuid.UUID) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "events",
            "finding_status_history",
            "findings",
            "alarm_status_history",
            "alarms",
            "measurements",
            "points",
            "functional_locations",
            "sites",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


def _measure(tenant: dict, value: float, at: datetime) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        ingest_measurements(
            connection,
            tenant_id=tenant["tenant_id"],
            items=[
                {
                    "point_id": tenant["status_point_id"],
                    "value": value,
                    "measured_at": at,
                    "origin": "measured",
                }
            ],
            source="test",
            received_at=at,
        )


def _findings(tenant: dict) -> list[dict]:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT reason_code, condition_state FROM findings "
                    "WHERE subject_node_id = :id OR point_id = :point_id"
                ),
                {"id": tenant["location_id"], "point_id": tenant["status_point_id"]},
            ).mappings()
        ]


def test_le_balayage_detecte_hors_ligne_et_donnee_perimee_sans_aucune_lecture_utilisateur():
    """Aucun appel à GET /functional-locations/{id}/status ni à GET
    /points/{id}/trust dans ce test : seul sweep_once() est invoqué,
    exactement comme le ferait une tâche planifiée sans utilisateur connecté."""
    tenant_a = _tenant_with_status_point("ClientBalayageA")
    tenant_b = _tenant_with_status_point("ClientBalayageB")
    try:
        _measure(tenant_a, 1, T0)
        _measure(tenant_b, 1, T0)

        later = T0 + timedelta(minutes=10)
        summary = sweep_once(engine, at=later)
        assert summary["tenants_failed"] == 0
        assert summary["tenants_ok"] >= 2
        assert summary["equipment_evaluated"] >= 2
        assert summary["points_evaluated"] >= 2

        for tenant in (tenant_a, tenant_b):
            reasons = {f["reason_code"]: f["condition_state"] for f in _findings(tenant)}
            assert reasons["COMMUNICATION_OFFLINE"] == "active"
            assert reasons["DATA_QUALITY_STALE"] == "active"

        # Retour à la normale, toujours sans aucune lecture utilisateur.
        recovery = later + timedelta(minutes=1)
        _measure(tenant_a, 1, recovery)
        _measure(tenant_b, 1, recovery)
        sweep_once(engine, at=recovery)

        for tenant in (tenant_a, tenant_b):
            reasons = {f["reason_code"]: f["condition_state"] for f in _findings(tenant)}
            assert reasons["COMMUNICATION_OFFLINE"] == "cleared"
            assert reasons["DATA_QUALITY_STALE"] == "cleared"
    finally:
        _cleanup(tenant_a["tenant_id"])
        _cleanup(tenant_b["tenant_id"])


def test_un_tenant_en_erreur_n_empeche_pas_le_balayage_des_autres():
    tenant_a = _tenant_with_status_point("ClientBalayageErreurA")
    tenant_b = _tenant_with_status_point("ClientBalayageErreurB")
    try:
        with engine.connect() as connection:
            total_tenants = connection.execute(text("SELECT count(*) FROM tenants")).scalar()

        def _boom_for_a(connection, tenant_id, at):
            if tenant_id == tenant_a["tenant_id"]:
                raise RuntimeError("panne simulée")
            return {"equipment_evaluated": 0, "points_evaluated": 0}

        with patch("app.supervision_sweep._sweep_tenant", side_effect=_boom_for_a) as mock_sweep:
            summary = sweep_once(engine, at=T0)

        called_tenant_ids = {call.args[1] for call in mock_sweep.call_args_list}
        assert {tenant_a["tenant_id"], tenant_b["tenant_id"]} <= called_tenant_ids
        assert summary["tenants_failed"] >= 1
        assert summary["tenants_ok"] + summary["tenants_failed"] == total_tenants
    finally:
        _cleanup(tenant_a["tenant_id"])
        _cleanup(tenant_b["tenant_id"])
