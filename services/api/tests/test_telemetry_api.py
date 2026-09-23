import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)


def _create_tenant(name: str) -> dict:
    tenant_id = uuid.uuid4()
    site_id = uuid.uuid4()
    ahu_id = uuid.uuid4()
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
                "VALUES (:id, :tenant_id, :site_id, 'cta-01', 'CTA 01')"
            ),
            {"id": ahu_id, "tenant_id": tenant_id, "site_id": site_id},
        )
    return {"tenant_id": tenant_id, "site": site_id, "ahu": ahu_id}


def _cleanup(tenant: dict) -> None:
    purge_audit_log_for_tenant(tenant["tenant_id"])
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        for table in (
            "measurements",
            "external_identifiers",
            "points",
            "functional_locations",
            "sites",
        ):
            connection.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tenant["tenant_id"]}
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant["tenant_id"]})


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientTelemetryApiA")
    tenant_b = _create_tenant("ClientTelemetryApiB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        _cleanup(tenant)


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant["tenant_id"]), roles=roles)
    return {"Authorization": f"Bearer {token}"}


def _call(method: str, path: str, headers: dict, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def _validated_sensor(tenant: dict) -> str:
    headers = _headers(tenant, ["responsable_exploitation"])
    created = _call(
        "POST",
        "/points",
        headers,
        json={
            "code": "CTA01-TDEP",
            "name": "Température départ eau",
            "value_type": "number",
            "point_class": "supply_water_temperature_sensor",
            "unit": "Cel",
            "functional_location_id": str(tenant["ahu"]),
            "min_value": 0,
            "max_value": 100,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["mapping_status"] == "proposed"
    assert created.json()["is_writable"] is False
    point_id = created.json()["id"]
    validated = _call(
        "POST", f"/points/{point_id}/validate", headers, json={"reason": "Contrôlé sur site"}
    )
    assert validated.status_code == 200, validated.text
    return point_id


def test_squelette_de_bout_en_bout_point_simule_puis_lecture(two_tenants) -> None:
    """Scénario M2 (cahier des charges 36.2) : un point est mis en service,
    reçoit une mesure simulée, qui est relue avec son origine."""
    tenant_a, _ = two_tenants
    point_id = _validated_sensor(tenant_a)
    headers = _headers(tenant_a, ["technicien"])

    created = _call(
        "POST",
        "/measurements",
        headers,
        json={
            "point_id": point_id,
            "value": 45.5,
            "measured_at": "2026-09-23T08:00:00+00:00",
            "origin": "simulated",
            "source": "simulator",
        },
    )
    listed = _call("GET", "/measurements", headers, params={"point_id": point_id})

    assert created.status_code == 201, created.text
    assert created.json()["origin"] == "simulated"
    assert created.json()["quality_flags"] == []
    assert [(row["value"], row["origin"]) for row in listed.json()] == [(45.5, "simulated")]


def test_resend_is_200_and_conflict_is_409(two_tenants) -> None:
    tenant_a, _ = two_tenants
    point_id = _validated_sensor(tenant_a)
    headers = _headers(tenant_a, ["technicien"])
    body = {"point_id": point_id, "value": 45.5, "measured_at": "2026-09-23T08:00:00+00:00"}

    first = _call("POST", "/measurements", headers, json=body)
    again = _call("POST", "/measurements", headers, json=body)
    other_value = _call("POST", "/measurements", headers, json={**body, "value": 50.0})

    assert (first.status_code, again.status_code, other_value.status_code) == (201, 200, 409)


def test_batch_endpoint(two_tenants) -> None:
    tenant_a, _ = two_tenants
    point_id = _validated_sensor(tenant_a)

    response = _call(
        "POST",
        "/measurements/batch",
        _headers(tenant_a, ["technicien"]),
        json={
            "source": "edge-test",
            "items": [
                {"point_id": point_id, "value": 45.0, "measured_at": "2026-09-23T08:00:00+00:00"},
                {"point_id": point_id, "value": 1e9, "measured_at": "2026-09-23T08:01:00+00:00"},
                {"point_id": str(uuid.uuid4()), "value": 1, "measured_at": "2026-09-23T08:00:00Z"},
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["inserted"] == 2
    assert response.json()["rejected"] == 1


@pytest.mark.parametrize(
    "body_overrides",
    [
        {"measured_at": "2026-09-23T08:00:00"},
        {"value": "NaN"},
        {"origin": "estimated"},
    ],
)
def test_invalid_measurements_are_refused(two_tenants, body_overrides) -> None:
    tenant_a, _ = two_tenants
    point_id = _validated_sensor(tenant_a)
    body = {"point_id": point_id, "value": 45.5, **body_overrides}

    response = _call("POST", "/measurements", _headers(tenant_a, ["technicien"]), json=body)
    assert response.status_code == 422


def test_other_tenant_point_is_not_found(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    point_b = _validated_sensor(tenant_b)
    headers_a = _headers(tenant_a, ["technicien"])

    measurement = _call("POST", "/measurements", headers_a, json={"point_id": point_b, "value": 1})
    point = _call("GET", f"/points/{point_b}", headers_a)

    assert measurement.status_code == 404
    assert point.status_code == 404


def test_technicien_cannot_create_or_validate_points(two_tenants) -> None:
    tenant_a, _ = two_tenants
    point_id = _validated_sensor(tenant_a)
    headers = _headers(tenant_a, ["technicien"])

    create = _call(
        "POST", "/points", headers, json={"code": "X", "name": "X", "value_type": "number"}
    )
    validate = _call("POST", f"/points/{point_id}/validate", headers, json={})

    assert create.status_code == 403
    assert validate.status_code == 403


def test_unit_incompatible_with_class_is_explained(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call(
        "POST",
        "/points",
        _headers(tenant_a, ["admin_tenant"]),
        json={
            "code": "BAD",
            "name": "Sonde mal déclarée",
            "value_type": "number",
            "point_class": "supply_water_temperature_sensor",
            "unit": "bar",
        },
    )
    assert response.status_code == 400
    assert "incompatible" in response.json()["detail"]


def test_rejecting_a_point_requires_a_reason(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["admin_tenant"])
    point_id = _call(
        "POST", "/points", headers, json={"code": "AI-7", "name": "AI-7", "value_type": "number"}
    ).json()["id"]

    without_reason = _call("POST", f"/points/{point_id}/reject", headers, json={})
    with_reason = _call(
        "POST", f"/points/{point_id}/reject", headers, json={"reason": "Point inexistant sur site"}
    )

    assert without_reason.status_code == 422
    assert with_reason.json()["mapping_status"] == "rejected"


def test_external_identifier_is_unique_per_tenant(two_tenants) -> None:
    tenant_a, _ = two_tenants
    headers = _headers(tenant_a, ["admin_tenant"])
    point_id = _validated_sensor(tenant_a)
    body = {"scheme": "bacnet_object", "external_id": "analog-input:12"}

    first = _call("POST", f"/graph/nodes/{point_id}/external-ids", headers, json=body)
    again = _call("POST", f"/graph/nodes/{tenant_a['ahu']}/external-ids", headers, json=body)
    unknown_scheme = _call(
        "POST",
        f"/graph/nodes/{point_id}/external-ids",
        headers,
        json={"scheme": "fantaisie", "external_id": "x"},
    )
    listed = _call("GET", f"/graph/nodes/{point_id}/external-ids", headers)

    assert first.status_code == 201
    assert again.status_code == 409
    assert unknown_scheme.status_code == 400
    assert [row["external_id"] for row in listed.json()] == ["analog-input:12"]
