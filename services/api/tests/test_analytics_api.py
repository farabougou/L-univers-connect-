from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.analytics_fixtures import cleanup_tenant, create_tenant_with_points
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)


def _recent(minutes_ago: int = 1) -> str:
    """Horodatage récent, jamais une date calendaire figée qui finirait par
    déclencher le drapeau d'arrivée tardive au fil du temps."""
    return (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()


@pytest.fixture
def two_tenants():
    tenant_a = create_tenant_with_points("ClientAnalyticsApiA")
    tenant_b = create_tenant_with_points("ClientAnalyticsApiB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        cleanup_tenant(tenant)


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    token = make_token(tenant_id=str(tenant["tenant_id"]), roles=roles)
    return {"Authorization": f"Bearer {token}"}


def _call(method: str, path: str, headers: dict, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def _rule_body(tenant: dict, **overrides) -> dict:
    content = {
        "kind": "threshold",
        "point_id": str(tenant["sensor"]),
        "operator": ">",
        "threshold": 80,
        "severity": "critical",
        "title": "Départ d'eau trop chaud",
        "create_work_order": True,
    }
    content.update(overrides)
    return {
        "config_type": "alarm_rule",
        "subject_key": "cta01-tdep-haute",
        "content": content,
        "reason": "Seuil fixé avec l'exploitant",
    }


def _active_rule(tenant: dict, **overrides) -> str:
    manager = _headers(tenant, ["responsable_exploitation"])
    version = _call("POST", "/configs", manager, json=_rule_body(tenant, **overrides))
    assert version.status_code == 201, version.text
    activated = _call("POST", f"/configs/{version.json()['id']}/activate", manager)
    assert activated.status_code == 200, activated.text
    return version.json()["id"]


def test_squelette_de_bout_en_bout_mesure_regle_constat_alarme_ordre_de_travail(
    two_tenants,
) -> None:
    """Critère de sortie M2 (cahier des charges 36.2) : point simulé → stockage
    → règle → alerte → ordre de travail → traitement par le technicien."""
    tenant_a, _ = two_tenants
    _active_rule(tenant_a)
    technicien = _headers(tenant_a, ["technicien"])

    measurement = _call(
        "POST",
        "/measurements",
        technicien,
        json={
            "point_id": str(tenant_a["sensor"]),
            "value": 86.5,
            "measured_at": _recent(5),
            "origin": "simulated",
            "source": "simulator",
        },
    )
    findings = _call("GET", "/findings", technicien, params={"handling_status": "open"})
    work_orders = _call("GET", "/work-orders", technicien)

    assert measurement.status_code == 201, measurement.text
    assert len(findings.json()) == 1
    finding = findings.json()[0]
    assert (finding["kind"], finding["severity"]) == ("fault", "critical")
    assert (finding["reason_code"], finding["certainty"]) == ("RULE_THRESHOLD_EXCEEDED", "detected")
    assert finding["work_order_id"] in {wo["id"] for wo in work_orders.json()}
    url = f"/findings/{finding['id']}"

    acknowledged = _call("POST", f"{url}/acknowledge", technicien, json={})
    too_early = _call("PATCH", f"{url}/handling", technicien, json={"handling_status": "closed"})
    _call(
        "POST",
        "/measurements",
        technicien,
        json={
            "point_id": str(tenant_a["sensor"]),
            "value": 45.0,
            "measured_at": _recent(0),
            "origin": "simulated",
            "source": "simulator",
        },
    )
    confirmed = _call(
        "POST", f"{url}/confirm", technicien, json={"note": "Vanne trois voies grippée"}
    )
    closed = _call(
        "PATCH",
        f"{url}/handling",
        technicien,
        json={"handling_status": "closed", "note": "Vanne trois voies débloquée"},
    )
    history = _call("GET", f"{url}/history", technicien)

    assert acknowledged.json()["ack_state"] == "acknowledged"
    assert too_early.status_code == 409
    assert too_early.json()["code"] == "SIGNAL_CONDITION_STILL_ACTIVE"
    assert confirmed.json()["certainty"] == "confirmed"
    assert (closed.json()["condition_state"], closed.json()["handling_status"]) == (
        "cleared",
        "closed",
    )
    assert [(row["field"], row["value"]) for row in history.json()] == [
        ("handling_status", "open"),
        ("ack_state", "acknowledged"),
        ("condition_state", "cleared"),
        ("certainty", "confirmed"),
        ("handling_status", "closed"),
    ]


def test_finding_titles_follow_the_requested_language(two_tenants) -> None:
    tenant_a, _ = two_tenants
    _active_rule(tenant_a)
    technicien = _headers(tenant_a, ["technicien"])
    _call(
        "POST",
        "/measurements",
        technicien,
        json={
            "point_id": str(tenant_a["sensor"]),
            "value": 150.0,
            "measured_at": "2026-09-23T08:00:00+00:00",
            "origin": "simulated",
            "source": "simulator",
        },
    )
    english = _call(
        "GET", "/findings", {**technicien, "Accept-Language": "en"}, params={"kind": "data_quality"}
    )
    french = _call("GET", "/findings", technicien, params={"kind": "data_quality"})

    assert english.json()[0]["title"].startswith("Value outside the sensor's physical range")
    assert french.json()[0]["title"].startswith("Valeur hors de la plage physique")


def test_technicien_cannot_change_rules(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call(
        "POST", "/configs", _headers(tenant_a, ["technicien"]), json=_rule_body(tenant_a)
    )
    assert response.status_code == 403


def test_invalid_rule_is_explained(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call(
        "POST",
        "/configs",
        _headers(tenant_a, ["admin_tenant"]),
        json=_rule_body(tenant_a, point_id=str(tenant_a["run_status"])),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "RULE_THRESHOLD_REQUIRES_NUMBER"


def test_diff_and_restore_through_the_api(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _headers(tenant_a, ["admin_tenant"])
    first = _active_rule(tenant_a)
    second = _active_rule(tenant_a, threshold=90)

    diff = _call("GET", f"/configs/{second}/diff", manager, params={"against": first})
    restored = _call(
        "POST", f"/configs/{first}/restore", manager, json={"reason": "90 °C trop tardif"}
    )
    versions = _call("GET", "/configs", manager, params={"subject_key": "cta01-tdep-haute"})

    assert diff.json()["changed"] == {"threshold": {"from": 80.0, "to": 90.0}}
    assert restored.status_code == 201
    assert restored.json()["version"] == 3
    assert [(v["version"], v["status"]) for v in versions.json()] == [
        (1, "superseded"),
        (2, "superseded"),
        (3, "active"),
    ]


def test_desired_state_api(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _headers(tenant_a, ["responsable_exploitation"])
    url = f"/points/{tenant_a['run_status']}/desired-states"
    body = {
        "value": 0,
        "daily_start": "20:00",
        "daily_end": "07:00",
        "timezone": "Europe/Paris",
        "reason": "CTA arrêtée la nuit",
    }

    created = _call("POST", url, manager, json=body)
    naive = _call("POST", url, manager, json={**body, "valid_from": "2026-09-23T08:00:00"})
    bad_zone = _call("POST", url, manager, json={**body, "timezone": "Paris"})
    ended = _call("POST", f"/desired-states/{created.json()['id']}/end", manager, json={})
    active = _call("GET", url, manager)
    history = _call("GET", url, manager, params={"include_ended": True})

    assert created.status_code == 201, created.text
    assert created.json()["source"] == "declared_expectation"
    assert naive.status_code == 422
    assert bad_zone.status_code == 400
    assert ended.status_code == 200
    assert active.json() == []
    assert len(history.json()) == 1


def test_trust_endpoint(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call(
        "GET", f"/points/{tenant_a['sensor']}/trust", _headers(tenant_a, ["technicien"])
    )
    assert response.status_code == 200
    assert response.json()["algorithm"] == "trust-v1"
    assert "components" in response.json()


def test_other_tenant_rules_and_findings_are_invisible(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    version_a = _active_rule(tenant_a)
    headers_b = _headers(tenant_b, ["admin_tenant"])

    assert _call("GET", f"/configs/{version_a}", headers_b).status_code == 404
    assert _call("GET", "/configs", headers_b).json() == []
    assert _call("GET", "/findings", headers_b).json() == []
