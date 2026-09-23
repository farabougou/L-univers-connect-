"""État de fonctionnement et état de communication d'un équipement (ADR 013,
étape L6). Deux axes distincts ; jamais un état présenté comme actuel sans
donnée récente."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.equipment_status import compute_equipment_status
from app.main import app
from app.points import create_point, decide_point, get_point
from app.telemetry import record_measurement
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

T0 = datetime(2026, 9, 24, 8, 0, tzinfo=UTC)
client = TestClient(app)


def _tenant(name: str) -> dict:
    ids = {
        "tenant_id": uuid.uuid4(),
        "site": uuid.uuid4(),
        "ahu": uuid.uuid4(),
        "bare": uuid.uuid4(),
    }
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": ids["tenant_id"], "name": name, "slug": f"{name.lower()}-{ids['tenant_id']}"},
        )
        set_tenant_context(connection, ids["tenant_id"])
        connection.execute(
            text(
                "INSERT INTO sites (id, tenant_id, name, timezone) "
                "VALUES (:id, :tenant_id, 'Site', 'Europe/Paris')"
            ),
            {"id": ids["site"], "tenant_id": ids["tenant_id"]},
        )
        for key, code in (("ahu", "CTA-01"), ("bare", "PAC-SANS-GTB")):
            connection.execute(
                text(
                    "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                    "VALUES (:id, :tenant_id, :site_id, :code, :code)"
                ),
                {
                    "id": ids[key],
                    "tenant_id": ids["tenant_id"],
                    "site_id": ids["site"],
                    "code": code,
                },
            )
        for key, point_class, interval in (
            ("run", "run_status", 300),
            ("fault", "fault_status", 300),
            ("enable", "enable_status", None),
        ):
            ids[key] = create_point(
                connection,
                tenant_id=ids["tenant_id"],
                code=f"CTA01-{key.upper()}",
                name=key,
                value_type="boolean",
                point_class=point_class,
                functional_location_id=ids["ahu"],
                expected_interval_seconds=interval,
                created_by="test",
            )
            decide_point(connection, point_id=ids[key], decision="validated")
    return ids


@pytest.fixture
def tenants():
    tenant_a, tenant_b = _tenant("ClientEtatA"), _tenant("ClientEtatB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        purge_tenant(tenant["tenant_id"])


def _measure(tenant, key, value, at, received_at=None):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        record_measurement(
            connection,
            tenant_id=tenant["tenant_id"],
            point=get_point(connection, tenant[key]),
            value=value,
            measured_at=at,
            origin="measured",
            source="test",
            received_at=received_at or at,
        )


def _status(tenant, at, location="ahu"):
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        return compute_equipment_status(connection, tenant[location], at)


def _axes(status):
    return (status["operational_status"], status["communication_status"], status["current"])


def test_equipment_without_status_point_has_an_unknown_state(tenants) -> None:
    tenant_a, _ = tenants
    status = _status(tenant_a, T0, location="bare")
    assert _axes(status) == ("unknown", "unknown", False)
    assert status["reason"] == "NO_STATUS_POINT"


def test_status_points_without_measurement_give_an_unknown_state(tenants) -> None:
    tenant_a, _ = tenants
    status = _status(tenant_a, T0)
    assert _axes(status) == ("unknown", "unknown", False)
    assert status["reason"] == "NO_MEASUREMENT"


@pytest.mark.parametrize(
    ("measurements", "expected"),
    [
        ({"run": 1}, "running"),
        ({"run": 0}, "stopped"),
        ({"run": 1, "fault": 1}, "fault"),
        ({"run": 0, "fault": 0, "enable": 0}, "disabled"),
        ({"fault": 0}, "unknown"),
    ],
)
def test_operational_status_from_fresh_status_points(tenants, measurements, expected) -> None:
    tenant_a, _ = tenants
    for key, value in measurements.items():
        _measure(tenant_a, key, value, T0)
    status = _status(tenant_a, T0 + timedelta(minutes=2))
    assert status["operational_status"] == expected
    assert status["communication_status"] == "online"


def test_offline_shows_the_last_known_state_and_its_date(tenants) -> None:
    """« Hors ligne » : dernier état connu et sa date, jamais un état supposé actuel."""
    tenant_a, _ = tenants
    _measure(tenant_a, "run", 1, T0)
    status = _status(tenant_a, T0 + timedelta(hours=1))
    assert _axes(status) == ("running", "offline", False)
    assert status["as_of"] == T0


def test_without_expected_interval_freshness_cannot_be_asserted(tenants) -> None:
    tenant_a, _ = tenants
    _measure(tenant_a, "enable", 0, T0)
    status = _status(tenant_a, T0 + timedelta(minutes=1))
    assert _axes(status) == ("disabled", "unknown", False)


def test_a_doubtful_value_is_never_used(tenants) -> None:
    tenant_a, _ = tenants
    _measure(tenant_a, "run", 0, T0)
    # Relevé daté dans le futur (horloge suspecte) : ignoré.
    _measure(tenant_a, "run", 1, T0 + timedelta(hours=2), received_at=T0 + timedelta(minutes=1))
    status = _status(tenant_a, T0 + timedelta(minutes=2))
    assert status["operational_status"] == "stopped"


def test_status_through_the_api_and_the_passport(tenants) -> None:
    tenant_a, tenant_b = tenants
    _measure(tenant_a, "run", 1, datetime.now(UTC))
    headers = {"Authorization": f"Bearer {make_token(tenant_id=str(tenant_a['tenant_id']))}"}
    other = {"Authorization": f"Bearer {make_token(tenant_id=str(tenant_b['tenant_id']))}"}
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        status = client.get(f"/functional-locations/{tenant_a['ahu']}/status", headers=headers)
        passport = client.get(f"/graph/nodes/{tenant_a['ahu']}/passport", headers=headers)
        hidden = client.get(f"/functional-locations/{tenant_a['ahu']}/status", headers=other)

    assert (status.json()["operational_status"], status.json()["communication_status"]) == (
        "running",
        "online",
    )
    assert passport.json()["status"]["operational_status"] == "running"
    assert hidden.status_code == 404
