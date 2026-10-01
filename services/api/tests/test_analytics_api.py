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


def _headers(tenant: dict, roles: list[str], sub: str = "technicien-test") -> dict[str, str]:
    token = make_token(tenant_id=str(tenant["tenant_id"]), roles=roles, sub=sub)
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
    """Approbation à deux (app/config_versions.py) : proposée et activée par
    deux personnes distinctes, même dans un test."""
    author = _headers(tenant, ["responsable_exploitation"], sub="auteur-regle")
    approver = _headers(tenant, ["responsable_exploitation"], sub="approbateur-regle")
    version = _call("POST", "/configs", author, json=_rule_body(tenant, **overrides))
    assert version.status_code == 201, version.text
    activated = _call("POST", f"/configs/{version.json()['id']}/activate", approver)
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


def test_creer_un_ordre_de_travail_depuis_un_constat(two_tenants) -> None:
    """Un constat sans ordre de travail automatique (create_work_order=False
    dans la règle) peut quand même en recevoir un ensuite, décidé par une
    personne — jamais l'inverse d'automatique (app/routers/maintenance.py)."""
    tenant_a, _ = two_tenants
    _active_rule(tenant_a, create_work_order=False)
    technicien = _headers(tenant_a, ["technicien"])
    manager = _headers(tenant_a, ["responsable_exploitation"])

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
    assert measurement.status_code == 201, measurement.text
    finding = _call("GET", "/findings", technicien, params={"handling_status": "open"}).json()[0]
    assert finding["work_order_id"] is None
    url = f"/findings/{finding['id']}/work-order"

    forbidden = _call("POST", url, technicien, json={})
    assert forbidden.status_code == 403

    created = _call("POST", url, manager, json={})
    assert created.status_code == 201, created.text
    work_order = created.json()
    assert work_order["title"] == "Départ d'eau trop chaud"
    assert work_order["priority"] == "urgent"
    assert work_order["functional_location_id"] == str(tenant_a["ahu"])
    assert work_order["work_order_type"] == "corrective"

    refreshed = _call("GET", f"/findings/{finding['id']}", technicien)
    assert refreshed.json()["work_order_id"] == work_order["id"]

    conflict = _call("POST", url, manager, json={})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "FINDING_WORK_ORDER_ALREADY_LINKED"


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


def test_portfolio_active_desired_states_montre_le_point_et_exclut_les_terminees(
    two_tenants,
) -> None:
    """Page Automation (section 36, point 13) : GET /desired-states/portfolio-active
    liste les attentes actives de tout le portefeuille, jamais celles déjà
    terminées, avec le point visé."""
    tenant_a, tenant_b = two_tenants
    manager = _headers(tenant_a, ["responsable_exploitation"])
    url = f"/points/{tenant_a['run_status']}/desired-states"
    active = _call(
        "POST",
        url,
        manager,
        json={
            "value": 0,
            "daily_start": "20:00",
            "daily_end": "07:00",
            "timezone": "Europe/Paris",
            "reason": "CTA arrêtée la nuit",
        },
    )
    ended = _call(
        "POST",
        url,
        manager,
        json={"value": 1, "reason": "Test terminé aussitôt"},
    )
    assert active.status_code == 201, active.text
    assert ended.status_code == 201, ended.text
    _call("POST", f"/desired-states/{ended.json()['id']}/end", manager, json={})

    portfolio = _call("GET", "/desired-states/portfolio-active", manager)
    assert portfolio.status_code == 200
    entries = portfolio.json()
    assert [e["id"] for e in entries] == [active.json()["id"]]
    assert entries[0]["point_code"] == "CTA01-MARCHE"
    assert entries[0]["functional_location_id"] is not None

    other_tenant_view = _call(
        "GET", "/desired-states/portfolio-active", _headers(tenant_b, ["responsable_exploitation"])
    )
    assert other_tenant_view.json() == []


def test_trust_endpoint(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call(
        "GET", f"/points/{tenant_a['sensor']}/trust", _headers(tenant_a, ["technicien"])
    )
    assert response.status_code == 200
    assert response.json()["algorithm"] == "trust-v1"
    assert "components" in response.json()


def test_lire_la_confiance_d_un_point_perime_leve_puis_referme_une_alerte(two_tenants) -> None:
    """Directive de Mohamed du 24/09/2026 (État → Événement → Politique →
    Alerte) : lire la confiance d'un point périmé par l'API en fait plus
    qu'un simple affichage — une vraie alerte apparaît, qu'un relevé frais
    referme automatiquement."""
    tenant_a, _ = two_tenants
    technicien = _headers(tenant_a, ["technicien"])
    old_measurement = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    _call(
        "POST",
        "/measurements",
        technicien,
        json={
            "point_id": str(tenant_a["sensor"]),
            "value": 42.0,
            "measured_at": old_measurement,
            "origin": "measured",
            "source": "test",
        },
    )

    stale = _call("GET", f"/points/{tenant_a['sensor']}/trust", technicien)
    assert stale.json()["components"]["stale"] is True
    findings = _call(
        "GET", "/findings", technicien, params={"subject_node_id": str(tenant_a["ahu"])}
    ).json()
    stale_finding = next(f for f in findings if f["point_id"] == str(tenant_a["sensor"]))
    assert stale_finding["reason_code"] == "DATA_QUALITY_STALE"
    assert stale_finding["condition_state"] == "active"

    _call(
        "POST",
        "/measurements",
        technicien,
        json={
            "point_id": str(tenant_a["sensor"]),
            "value": 42.0,
            "measured_at": _recent(),
            "origin": "measured",
            "source": "test",
        },
    )
    fresh = _call("GET", f"/points/{tenant_a['sensor']}/trust", technicien)
    assert fresh.json()["components"]["stale"] is False
    # Le constat n'est pas supprimé : il repasse « revenu à la normale »
    # (seule une personne le clôt, voir app/findings.py::clear_finding_by_key).
    findings_after = _call(
        "GET", "/findings", technicien, params={"subject_node_id": str(tenant_a["ahu"])}
    ).json()
    cleared_finding = next(f for f in findings_after if f["point_id"] == str(tenant_a["sensor"]))
    assert cleared_finding["condition_state"] == "cleared"


def test_other_tenant_rules_and_findings_are_invisible(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    version_a = _active_rule(tenant_a)
    headers_b = _headers(tenant_b, ["admin_tenant"])

    assert _call("GET", f"/configs/{version_a}", headers_b).status_code == 404
    assert _call("GET", "/configs", headers_b).json() == []
    assert _call("GET", "/findings", headers_b).json() == []


def _measure_via_api(tenant, headers, value: float, minutes_ago: int) -> None:
    response = _call(
        "POST",
        "/measurements",
        headers,
        json={
            "point_id": str(tenant["sensor"]),
            "value": value,
            "measured_at": _recent(minutes_ago),
            "origin": "simulated",
            "source": "simulator",
        },
    )
    assert response.status_code == 201, response.text


def test_simulate_reports_which_measurements_would_breach_a_draft_rule(two_tenants) -> None:
    """Simulation préalable (feature-benchmark-matrix.md, ligne « Gestion des
    changements ») : une règle en brouillon, jamais activée, ne crée ni
    constat ni alarme — seul l'historique dit ce qu'elle aurait fait."""
    tenant_a, _ = two_tenants
    technicien = _headers(tenant_a, ["technicien"])
    for value in (50.0, 90.0, 95.0, 60.0):
        _measure_via_api(tenant_a, technicien, value, minutes_ago=5)

    draft = _call(
        "POST",
        "/configs",
        _headers(tenant_a, ["responsable_exploitation"]),
        json=_rule_body(tenant_a, threshold=80),
    )
    assert draft.status_code == 201, draft.text
    version_id = draft.json()["id"]

    simulation = _call("GET", f"/configs/{version_id}/simulate", technicien)

    assert simulation.status_code == 200, simulation.text
    assert simulation.json()["sample_size"] == 4
    assert simulation.json()["breach_count"] == 2
    # Un brouillon jamais activé ne déclenche jamais rien réellement.
    assert _call("GET", "/findings", technicien).json() == []


def test_simulate_refuses_a_config_type_that_is_not_a_rule(two_tenants) -> None:
    tenant_a, _ = two_tenants
    manager = _headers(tenant_a, ["responsable_exploitation"])
    mapping = _call(
        "POST",
        "/configs",
        manager,
        json={
            "config_type": "modbus_device_mapping",
            "subject_key": str(tenant_a["ahu"]),
            "content": {
                "device_type": "sdm120",
                "host": "127.0.0.1",
                "port": 502,
                "points": [{"point_id": str(tenant_a["sensor"]), "register_name": "voltage"}],
            },
            "reason": "test",
        },
    )
    assert mapping.status_code == 201, mapping.text

    simulation = _call(
        "GET", f"/configs/{mapping.json()['id']}/simulate", _headers(tenant_a, ["technicien"])
    )

    assert simulation.status_code == 400
    assert simulation.json()["code"] == "CONFIG_SIMULATION_NOT_SUPPORTED"
