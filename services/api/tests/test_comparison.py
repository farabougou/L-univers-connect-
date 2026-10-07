"""Comparaison d'équipements (07/10/2026, V3 — priorité « Compare »,
app/comparison.py). Même calcul que `_evaluate_statistical_anomaly`
(app/rules.py) sur une population de pairs plutôt que sur l'historique d'un
seul point — mais une lecture pure, jamais un constat : aucun de ces tests
ne doit faire apparaître une ligne dans `findings`."""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.comparison import PointInvalid, PointNotFound, compare_point_to_peers
from app.db import engine
from app.findings import list_findings
from app.main import app
from app.points import create_point, decide_point, get_point
from app.telemetry import record_measurement
from app.tenancy import set_tenant_context
from tests.analytics_fixtures import cleanup_tenant
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)
T0 = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)


def _create_fleet_tenant(name: str, *, equipment_count: int) -> dict:
    """Un site, `equipment_count` CTA, chacune avec une sonde de température
    de départ (même point_class, pour que la comparaison de parc ait un
    sens) et un état de marche (point_class différente : jamais un pair)."""
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    equipment_ids = []
    sensor_ids = []
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
        for index in range(equipment_count):
            fl_id = uuid.uuid4()
            connection.execute(
                text(
                    "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                    "VALUES (:id, :tenant_id, :site_id, :code, :name)"
                ),
                {
                    "id": fl_id,
                    "tenant_id": tenant_id,
                    "site_id": site_id,
                    "code": f"cta-{index:02d}",
                    "name": f"CTA {index:02d}",
                },
            )
            equipment_ids.append(fl_id)
            sensor_id = create_point(
                connection,
                tenant_id=tenant_id,
                code=f"CTA{index:02d}-TDEP",
                name="Température départ eau",
                value_type="number",
                point_class="supply_water_temperature_sensor",
                unit="Cel",
                functional_location_id=fl_id,
                expected_interval_seconds=60,
                min_value=0,
                max_value=100,
                created_by="test",
            )
            decide_point(connection, point_id=sensor_id, decision="validated")
            sensor_ids.append(sensor_id)
            run_status_id = create_point(
                connection,
                tenant_id=tenant_id,
                code=f"CTA{index:02d}-MARCHE",
                name="État de marche",
                value_type="boolean",
                point_class="run_status",
                functional_location_id=fl_id,
                created_by="test",
            )
            decide_point(connection, point_id=run_status_id, decision="validated")
    return {
        "tenant_id": tenant_id,
        "site": site_id,
        "equipment": equipment_ids,
        "sensors": sensor_ids,
    }


def _measure(connection, tenant, point_id, value, at=T0):
    record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=get_point(connection, point_id),
        value=value,
        measured_at=at,
        origin="simulated",
        source="simulator",
        received_at=at,
    )


@pytest.fixture
def fleet_of_four():
    tenant = _create_fleet_tenant("ClientComparisonFleet", equipment_count=4)
    yield tenant
    cleanup_tenant(tenant)


def test_an_equipment_far_from_its_peers_is_flagged_an_outlier(fleet_of_four) -> None:
    tenant = fleet_of_four
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        for sensor_id, value in zip(tenant["sensors"], [20.0, 21.0, 19.0, 50.0], strict=True):
            _measure(connection, tenant, sensor_id, value)

        outlier = compare_point_to_peers(connection, tenant["sensors"][3], T0)
        normal = compare_point_to_peers(connection, tenant["sensors"][0], T0)
        findings_after = list_findings(connection)

    assert outlier["comparable"] is True
    assert outlier["peer_count"] == 3
    assert outlier["mean"] == 20.0
    assert outlier["std_dev"] == 1.0
    assert outlier["z_score"] == 30.0
    assert outlier["is_outlier"] is True
    assert outlier["confidence"] is not None
    assert 0.0 < outlier["confidence"] < 1.0
    assert {peer["point_code"] for peer in outlier["peers"]} == {
        "CTA00-TDEP",
        "CTA01-TDEP",
        "CTA02-TDEP",
    }

    assert normal["comparable"] is True
    assert normal["is_outlier"] is False
    assert normal["confidence"] is None

    # Une comparaison à la demande ne crée jamais de constat.
    assert findings_after == []


def test_identical_peers_are_comparable_but_never_claim_an_outlier(fleet_of_four) -> None:
    """Écart-type nul chez les pairs : un z-score serait une division par
    zéro, jamais un calcul — pas de verdict, même si la valeur diffère."""
    tenant = fleet_of_four
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        for sensor_id, value in zip(tenant["sensors"], [20.0, 20.0, 20.0, 99.0], strict=True):
            _measure(connection, tenant, sensor_id, value)

        result = compare_point_to_peers(connection, tenant["sensors"][3], T0)

    assert result["comparable"] is True
    assert result["mean"] == 20.0
    assert result["std_dev"] == 0.0
    assert result["z_score"] is None
    assert result["is_outlier"] is False


def test_not_enough_peers_with_a_recent_value_is_not_comparable(fleet_of_four) -> None:
    tenant = fleet_of_four
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        # Un seul autre point mesuré : jamais assez pour une population.
        _measure(connection, tenant, tenant["sensors"][0], 20.0)
        _measure(connection, tenant, tenant["sensors"][1], 21.0)

        result = compare_point_to_peers(connection, tenant["sensors"][0], T0)

    assert result["comparable"] is False
    assert result["mean"] is None
    assert result["is_outlier"] is False


def test_a_point_without_a_recent_value_is_not_comparable(fleet_of_four) -> None:
    tenant = fleet_of_four
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        for sensor_id, value in zip(tenant["sensors"][1:], [20.0, 21.0, 19.0], strict=True):
            _measure(connection, tenant, sensor_id, value)

        result = compare_point_to_peers(connection, tenant["sensors"][0], T0)

    assert result["comparable"] is False
    assert result["value"] is None
    assert result["peer_count"] == 3


def test_comparison_requires_a_numeric_point(fleet_of_four) -> None:
    tenant = fleet_of_four
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        run_status_point = connection.execute(
            text(
                "SELECT id FROM points WHERE functional_location_id = :fl "
                "AND point_class = 'run_status'"
            ),
            {"fl": tenant["equipment"][0]},
        ).scalar()
        with pytest.raises(PointInvalid) as exc_info:
            compare_point_to_peers(connection, run_status_point, T0)
    assert exc_info.value.code == "POINT_COMPARISON_REQUIRES_NUMBER"


def test_comparison_of_an_unknown_point_is_not_found(fleet_of_four) -> None:
    tenant = fleet_of_four
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(PointNotFound):
            compare_point_to_peers(connection, uuid.uuid4(), T0)


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant["tenant_id"]), roles=roles)
    return {"Authorization": f"Bearer {token}"}


def _call(method: str, path: str, headers: dict, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def test_api_never_lets_a_tenant_compare_against_another_tenants_equipment() -> None:
    """Isolation entre clients : les pairs d'une comparaison ne doivent
    jamais traverser la frontière RLS, même si la même point_class existe
    chez un autre client."""
    tenant_a = _create_fleet_tenant("ClientComparisonIsoA", equipment_count=1)
    tenant_b = _create_fleet_tenant("ClientComparisonIsoB", equipment_count=3)
    try:
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_b["tenant_id"])
            for sensor_id, value in zip(tenant_b["sensors"], [20.0, 21.0, 19.0], strict=True):
                _measure(connection, tenant_b, sensor_id, value)
            set_tenant_context(connection, tenant_a["tenant_id"])
            _measure(connection, tenant_a, tenant_a["sensors"][0], 99.0)

        response = _call(
            "GET",
            f"/points/{tenant_a['sensors'][0]}/compare",
            _headers(tenant_a, ["technicien"]),
        )
        assert response.status_code == 200, response.text
        body = response.json()
    finally:
        cleanup_tenant(tenant_a)
        cleanup_tenant(tenant_b)

    assert body["peer_count"] == 0
    assert body["comparable"] is False


def test_api_rejects_a_point_that_does_not_exist() -> None:
    tenant = _create_fleet_tenant("ClientComparisonMissing", equipment_count=1)
    try:
        response = _call(
            "GET", f"/points/{uuid.uuid4()}/compare", _headers(tenant, ["technicien"])
        )
    finally:
        cleanup_tenant(tenant)
    assert response.status_code == 404
    assert response.json()["code"] == "POINT_NOT_FOUND"
