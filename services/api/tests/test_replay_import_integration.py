"""Palier INTEGRATION_TESTED du Replay Mode (ADR 017 §1 et §3) : un export
CSV rejoué par `scripts/replay_import.py` passe par le même chemin qu'une
mesure en direct et déclenche réellement la règle FDD déjà écrite et testée
pour un capteur réel (`app.rules.CorrelationRule`,
`simultaneous_heating_cooling`) — même motif que
tests/test_virtual_telemetry_failure_scenarios.py pour le Virtual Protocol
Adapter. Preuve que Replay Mode nourrit le même pipeline, jamais un second."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.config_versions import activate_version, create_version
from app.db import engine
from app.findings import list_findings
from app.points import create_point, decide_point
from app.rules import ALARM_RULE
from app.tenancy import set_tenant_context
from scripts.replay_import import run
from tests.db_helpers import purge_audit_log_for_tenant, purge_config_versions_for_tenant

# Volontairement récent (une heure avant l'exécution du test), jamais une
# date fixe : au-delà de 24h entre relevé et réception, `app.telemetry`
# marque honnêtement le relevé "arrivée tardive" (comportement voulu, voir
# le docstring de scripts/replay_import.py) — ce qui fait chuter le score de
# confiance sous le seuil requis par les règles (`MIN_TRUST_FOR_RULES`,
# app/trust.py) et empêcherait ce test de prouver la règle FDD. Rejouer un
# export réellement vieux de plusieurs mois enregistre bien l'historique,
# mais n'alimente pas la détection avant que la confiance ne soit rétablie
# — c'est la plateforme qui protège les règles d'une donnée arrivée tard,
# pas une limite propre à Replay Mode.
T0 = (datetime.now(UTC) - timedelta(hours=1)).replace(microsecond=0)


def _tenant_with_cta() -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    equipment_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'ReplayFDD', :slug)"),
            {"id": tenant_id, "slug": f"replay-fdd-{tenant_id}"},
        )
        set_tenant_context(connection, tenant_id)
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:id, :tenant_id, 'Site')"),
            {"id": site_id, "tenant_id": tenant_id},
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:id, :tenant_id, :site_id, 'CTA-01', 'CTA 01')"
            ),
            {"id": equipment_id, "tenant_id": tenant_id, "site_id": site_id},
        )
        heating = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA-01.vanne_chaude",
            name="Position vanne chaude",
            value_type="number",
            point_class="heating_valve_position",
            unit="%",
            functional_location_id=equipment_id,
            expected_interval_seconds=300,
            min_value=0,
            max_value=100,
            created_by="test",
        )
        cooling = create_point(
            connection,
            tenant_id=tenant_id,
            code="CTA-01.vanne_froide",
            name="Position vanne froide",
            value_type="number",
            point_class="cooling_valve_position",
            unit="%",
            functional_location_id=equipment_id,
            expected_interval_seconds=300,
            min_value=0,
            max_value=100,
            created_by="test",
        )
        for point_id in (heating, cooling):
            decide_point(connection, point_id=point_id, decision="validated")
        content = {
            "kind": "simultaneous_heating_cooling",
            "heating_point_id": str(heating),
            "cooling_point_id": str(cooling),
            "heating_threshold": 20,
            "cooling_threshold": 20,
            "severity": "major",
            "title": "Chauffage et refroidissement actifs en même temps (export rejoué)",
        }
        version_id = create_version(
            connection,
            tenant_id=tenant_id,
            config_type=ALARM_RULE,
            subject_key="cta-01-replay-chaud-froid",
            content=content,
            author="responsable",
            reason="test",
        )
        activate_version(
            connection, version_id=version_id, activated_by="approbateur", activated_at=T0
        )
    return {"tenant_id": tenant_id}


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in (
            "events",
            "finding_status_history",
            "findings",
            "alarm_status_history",
            "alarms",
            "work_order_status_history",
            "work_orders",
            "measurements",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    purge_config_versions_for_tenant(tenant_id)
    purge_audit_log_for_tenant(tenant_id)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        for table in ("points", "functional_locations", "sites"):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant_id}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})


@pytest.fixture
def tenant():
    tenant = _tenant_with_cta()
    yield tenant
    _cleanup(tenant)


def _write_export(tmp_path, body: str):
    path = tmp_path / "export.csv"
    path.write_text(body)
    return path


def test_replayed_export_raises_a_real_finding(tenant, tmp_path) -> None:
    t1 = T0 + timedelta(seconds=30)
    csv_path = _write_export(
        tmp_path,
        "Horodatage,Vanne_Chaude,Vanne_Froide\n"
        f"{T0.strftime('%Y-%m-%d %H:%M:%S')},50,0\n"
        f"{t1.strftime('%Y-%m-%d %H:%M:%S')},50,60\n",
    )
    summary = run(
        tenant_id=tenant["tenant_id"],
        csv_path=csv_path,
        timestamp_column="Horodatage",
        timestamp_format="%Y-%m-%d %H:%M:%S",
        column_to_point_code={
            "Vanne_Chaude": "CTA-01.vanne_chaude",
            "Vanne_Froide": "CTA-01.vanne_froide",
        },
        timezone=None,
        source="replay_import",
        dry_run=False,
    )
    assert summary["inserted"] == 4

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        findings = list_findings(connection)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["kind"] == "fault"
    assert finding["condition_state"] == "active"
    assert finding["reason_code"] == "RULE_SIMULTANEOUS_HEATING_COOLING"


def test_replay_never_invents_a_point(tenant, tmp_path) -> None:
    csv_path = _write_export(
        tmp_path, f"Horodatage,Inconnu\n{T0.strftime('%Y-%m-%d %H:%M:%S')},42\n"
    )
    with pytest.raises(SystemExit, match="Point introuvable"):
        run(
            tenant_id=tenant["tenant_id"],
            csv_path=csv_path,
            timestamp_column="Horodatage",
            timestamp_format="%Y-%m-%d %H:%M:%S",
            column_to_point_code={"Inconnu": "CTA-01.point_qui_nexiste_pas"},
            timezone=None,
            source="replay_import",
            dry_run=False,
        )


def test_dry_run_writes_nothing(tenant, tmp_path) -> None:
    csv_path = _write_export(
        tmp_path, f"Horodatage,Vanne_Chaude\n{T0.strftime('%Y-%m-%d %H:%M:%S')},50\n"
    )
    summary = run(
        tenant_id=tenant["tenant_id"],
        csv_path=csv_path,
        timestamp_column="Horodatage",
        timestamp_format="%Y-%m-%d %H:%M:%S",
        column_to_point_code={"Vanne_Chaude": "CTA-01.vanne_chaude"},
        timezone=None,
        source="replay_import",
        dry_run=True,
    )
    assert summary == {"inserted": 0, "duplicate": 0, "rejected": 0}

    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        count = connection.execute(
            text("SELECT count(*) FROM measurements WHERE tenant_id = :id"),
            {"id": tenant["tenant_id"]},
        ).scalar()
    assert count == 0
