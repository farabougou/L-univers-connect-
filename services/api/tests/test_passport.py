import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)
T0 = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)


def _create_tenant(name: str) -> dict:
    """Un bâtiment avec une chaufferie, une PAC installée dans cette pièce."""
    ids = {
        k: uuid.uuid4() for k in ("tenant_id", "site", "building", "room", "loc", "model", "unit")
    }
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": ids["tenant_id"], "name": name, "slug": f"{name.lower()}-{ids['tenant_id']}"},
        )
        set_tenant_context(connection, ids["tenant_id"])
        p = {**ids}
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:site, :tenant_id, 'Site')"), p
        )
        connection.execute(
            text(
                "INSERT INTO spaces (id, tenant_id, site_id, space_type, code, name, valid_from) "
                "VALUES (:building, :tenant_id, :site, 'building', 'BAT-A', 'Bâtiment A', now())"
            ),
            p,
        )
        connection.execute(
            text(
                "INSERT INTO spaces (id, tenant_id, site_id, parent_id, space_type, code, name, "
                "valid_from) VALUES (:room, :tenant_id, :site, :building, 'zone', 'CHAUF', "
                "'Chaufferie', now())"
            ),
            p,
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name, kind, "
                "space_id) VALUES (:loc, :tenant_id, :site, 'pac-01', 'PAC 01', 'equipment', :room)"
            ),
            p,
        )
        connection.execute(
            text(
                "INSERT INTO product_models (id, tenant_id, manufacturer, reference, category) "
                "VALUES (:model, :tenant_id, 'Fabricant Demo', 'PAC-X', 'pac')"
            ),
            p,
        )
        connection.execute(
            text(
                "INSERT INTO physical_units (id, tenant_id, product_model_id, serial_number, "
                "lifecycle_state) VALUES (:unit, :tenant_id, :model, 'SN-PAC-1', 'installed')"
            ),
            p,
        )
        connection.execute(
            text(
                "INSERT INTO functional_location_assignments (id, tenant_id, "
                "functional_location_id, physical_unit_id, valid_from) VALUES "
                "(gen_random_uuid(), :tenant_id, :loc, :unit, now())"
            ),
            p,
        )
    return ids


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientPassportA")
    tenant_b = _create_tenant("ClientPassportB")
    yield tenant_a, tenant_b
    for tenant in (tenant_a, tenant_b):
        purge_tenant(tenant["tenant_id"])


def _headers(tenant: dict, roles: list[str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(tenant_id=str(tenant['tenant_id']), roles=roles)}"
    }


def _call(method, path, headers, **kwargs):
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def _manager(tenant):
    return _headers(tenant, ["responsable_exploitation"])


def _tech(tenant):
    return _headers(tenant, ["technicien"])


# --- Étiquettes QR ------------------------------------------------


def test_scanning_a_tag_opens_the_passport(two_tenants) -> None:
    tenant_a, _ = two_tenants
    tag = _call("POST", f"/graph/nodes/{tenant_a['loc']}/tags", _manager(tenant_a), json={})
    assert tag.status_code == 201, tag.text
    payload = tag.json()["payload"]

    scanned = _call("GET", f"/tags/{payload}", _tech(tenant_a))

    assert payload.startswith("paios:tag:")
    assert str(tenant_a["loc"]) not in payload  # le QR ne révèle aucun identifiant interne
    assert scanned.status_code == 200, scanned.text
    passport = scanned.json()["passport"]
    assert passport["functional_location"]["code"] == "pac-01"
    assert [s["code"] for s in passport["space_path"]] == ["BAT-A", "CHAUF"]
    assert passport["current_unit"]["serial_number"] == "SN-PAC-1"


def test_tag_codes_are_random_and_unique(two_tenants) -> None:
    tenant_a, _ = two_tenants
    codes = {
        _call("POST", f"/graph/nodes/{tenant_a['loc']}/tags", _manager(tenant_a), json={}).json()[
            "code"
        ]
        for _ in range(5)
    }
    assert len(codes) == 5
    assert all(len(code) >= 20 for code in codes)


def test_revoked_tag_is_reported_as_such(two_tenants) -> None:
    tenant_a, _ = two_tenants
    code = _call(
        "POST", f"/graph/nodes/{tenant_a['loc']}/tags", _manager(tenant_a), json={}
    ).json()["code"]

    revoked = _call(
        "POST", f"/tags/{code}/revoke", _manager(tenant_a), json={"reason": "Étiquette arrachée"}
    )
    scanned = _call("GET", f"/tags/{code}", _tech(tenant_a))
    again = _call("POST", f"/tags/{code}/revoke", _manager(tenant_a), json={"reason": "x"})

    assert revoked.json()["status"] == "revoked"
    assert scanned.status_code == 410
    assert scanned.json()["code"] == "TAG_REVOKED"
    assert scanned.json()["params"] == {"reason": "Étiquette arrachée"}
    assert again.status_code == 409


def test_another_tenant_tag_is_unknown(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    code = _call(
        "POST", f"/graph/nodes/{tenant_a['loc']}/tags", _manager(tenant_a), json={}
    ).json()["code"]
    assert _call("GET", f"/tags/{code}", _tech(tenant_b)).status_code == 404
    assert _call("GET", "/tags/code-invente", _tech(tenant_a)).status_code == 404


def test_a_tag_is_never_reassigned(two_tenants) -> None:
    tenant_a, _ = two_tenants
    tag_id = _call(
        "POST", f"/graph/nodes/{tenant_a['loc']}/tags", _manager(tenant_a), json={}
    ).json()["id"]
    with pytest.raises(DBAPIError, match="non modifiable"):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            connection.execute(
                text("UPDATE asset_tags SET node_id = :unit WHERE id = :id"),
                {"unit": tenant_a["unit"], "id": tag_id},
            )


# --- Actions autorisées ------------------------------------------------


def test_allowed_actions_depend_on_the_role_and_never_include_a_command(two_tenants) -> None:
    tenant_a, _ = two_tenants
    url = f"/graph/nodes/{tenant_a['loc']}/passport"

    as_tech = _call("GET", url, _tech(tenant_a)).json()["allowed_actions"]
    as_manager = _call("GET", url, _manager(tenant_a)).json()["allowed_actions"]

    assert "log_intervention" in as_tech and "create_work_order" not in as_tech
    assert "create_work_order" in as_manager and "assign_physical_unit" in as_manager
    for action in as_tech + as_manager:
        assert "command" not in action and "write" not in action


def test_passport_of_another_tenant_node_is_not_found(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    response = _call("GET", f"/graph/nodes/{tenant_a['loc']}/passport", _tech(tenant_b))
    assert response.status_code == 404


# --- Propriétés techniques ------------------------------------------------


def _set(tenant, **body):
    body.setdefault("source", "nameplate")
    body.setdefault("reason", "Relevé plaque signalétique")
    return _call("POST", f"/graph/nodes/{tenant['unit']}/properties", _manager(tenant), json=body)


def test_refrigerant_and_charge_with_history(two_tenants) -> None:
    tenant_a, _ = two_tenants
    fluid = _set(tenant_a, key="refrigerant_type", value="R32")
    first = _set(
        tenant_a, key="refrigerant_charge", value=2.5, unit="kg", valid_from=T0.isoformat()
    )
    second = _set(
        tenant_a,
        key="refrigerant_charge",
        value=2.8,
        unit="kg",
        source="measurement",
        valid_from=(T0 + timedelta(days=90)).isoformat(),
        reason="Recharge après recherche de fuite",
    )
    url = f"/graph/nodes/{tenant_a['unit']}/properties"
    current = _call("GET", url, _tech(tenant_a)).json()
    history = _call("GET", url, _tech(tenant_a), params={"include_history": True}).json()

    assert (fluid.status_code, first.status_code, second.status_code) == (201, 201, 201)
    assert {p["property_key"]: p["value"] for p in current} == {
        "refrigerant_charge": 2.8,
        "refrigerant_type": "R32",
    }
    charges = [
        (p["value"], p["valid_to"] is None)
        for p in history
        if p["property_key"] == "refrigerant_charge"
    ]
    assert charges == [(2.5, False), (2.8, True)]


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (
            {"key": "refrigerant_charge", "value": 2.5, "unit": "bar"},
            "PROPERTY_UNIT_QUANTITY_MISMATCH",
        ),
        ({"key": "refrigerant_charge", "value": 2.5}, "PROPERTY_UNIT_MISSING"),
        ({"key": "refrigerant_type", "value": "R9999"}, "PROPERTY_VALUE_NOT_ALLOWED"),
        ({"key": "couleur", "value": "rouge"}, "PROPERTY_UNKNOWN"),
        ({"key": "manufacture_year", "value": 1850}, "PROPERTY_BELOW_MINIMUM"),
    ],
)
def test_invalid_properties_are_explained(two_tenants, body, code) -> None:
    tenant_a, _ = two_tenants
    response = _set(tenant_a, **body)
    assert response.status_code == 400
    assert response.json()["code"] == code


def test_nameplate_data_belongs_to_the_unit_not_the_position(two_tenants) -> None:
    tenant_a, _ = two_tenants
    response = _call(
        "POST",
        f"/graph/nodes/{tenant_a['loc']}/properties",
        _manager(tenant_a),
        json={"key": "refrigerant_type", "value": "R32", "source": "nameplate", "reason": "x"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "PROPERTY_NODE_TYPE_INVALID"


def test_a_property_value_is_never_rewritten(two_tenants) -> None:
    tenant_a, _ = two_tenants
    _set(tenant_a, key="refrigerant_type", value="R32")
    with pytest.raises(DBAPIError, match="non modifiable"):
        with engine.begin() as connection:
            set_tenant_context(connection, tenant_a["tenant_id"])
            connection.execute(text("UPDATE node_properties SET value_text = 'R410A'"))


def test_passport_shows_the_unit_properties(two_tenants) -> None:
    tenant_a, _ = two_tenants
    _set(tenant_a, key="refrigerant_type", value="R32")
    passport = _call("GET", f"/graph/nodes/{tenant_a['loc']}/passport", _tech(tenant_a)).json()
    assert [(p["property_key"], p["value"]) for p in passport["current_unit"]["properties"]] == [
        ("refrigerant_type", "R32")
    ]


# --- Clôture structurée ------------------------------------------------


def _intervention(tenant) -> str:
    response = _call(
        "POST",
        "/interventions",
        _tech(tenant),
        json={"functional_location_id": str(tenant["loc"]), "summary": "Pas de chauffage"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


_CLOSURE = {
    "symptom_code": "no_heating",
    "cause_code": "component_failure",
    "action_code": "replacement",
    "parts": [{"reference": "VANNE-3V-DN25", "quantity": 1}],
    "labor_minutes": 90,
    "verification_result": "ok",
    "note": "Vanne trois voies bloquée remplacée",
}


def test_structured_closure_appears_in_the_passport(two_tenants) -> None:
    tenant_a, _ = two_tenants
    intervention_id = _intervention(tenant_a)

    closed = _call(
        "POST", f"/interventions/{intervention_id}/closure", _tech(tenant_a), json=_CLOSURE
    )
    passport = _call("GET", f"/graph/nodes/{tenant_a['loc']}/passport", _tech(tenant_a)).json()

    assert closed.status_code == 201, closed.text
    assert closed.json()["parts"] == [{"reference": "VANNE-3V-DN25", "quantity": 1.0}]
    recent = passport["recent_interventions"][0]
    assert (recent["symptom_label"], recent["action_label"]) == (
        "Pas de chauffage",
        "Remplacement de pièce",
    )


@pytest.mark.parametrize(
    ("overrides", "status_code"),
    [
        ({"symptom_code": "panne_bizarre"}, 400),
        ({"parts": []}, 400),  # un remplacement sans pièce n'a pas de sens
        ({"labor_minutes": -5}, 422),
        ({"verification_result": "peut-etre"}, 422),
    ],
)
def test_invalid_closures_are_refused(two_tenants, overrides, status_code) -> None:
    tenant_a, _ = two_tenants
    intervention_id = _intervention(tenant_a)
    response = _call(
        "POST",
        f"/interventions/{intervention_id}/closure",
        _tech(tenant_a),
        json={**_CLOSURE, **overrides},
    )
    assert response.status_code == status_code


def test_an_intervention_is_closed_once_and_the_closure_is_immutable(two_tenants) -> None:
    tenant_a, _ = two_tenants
    intervention_id = _intervention(tenant_a)
    url = f"/interventions/{intervention_id}/closure"

    first = _call("POST", url, _tech(tenant_a), json=_CLOSURE)
    second = _call("POST", url, _tech(tenant_a), json=_CLOSURE)
    assert (first.status_code, second.status_code) == (201, 409)

    for statement, message in (
        ("UPDATE intervention_closures SET labor_minutes = 5", "modification interdite"),
        ("DELETE FROM intervention_closures", "suppression interdite"),
    ):
        with pytest.raises(DBAPIError, match=message):
            with engine.begin() as connection:
                set_tenant_context(connection, tenant_a["tenant_id"])
                connection.execute(text(statement))


def test_closure_vocabulary_is_published(two_tenants) -> None:
    tenant_a, _ = two_tenants
    vocabulary = _call("GET", "/closure-vocabulary", _tech(tenant_a)).json()
    assert vocabulary["symptoms"]["no_heating"] == "Pas de chauffage"
    assert set(vocabulary["verification_results"]) == {"ok", "partial", "failed"}


# --- Isolation ------------------------------------------------


@pytest.mark.parametrize("table", ["asset_tags", "node_properties", "intervention_closures"])
def test_tenant_isolation_on_passport_tables(two_tenants, table) -> None:
    tenant_a, tenant_b = two_tenants
    _call("POST", f"/graph/nodes/{tenant_a['loc']}/tags", _manager(tenant_a), json={})
    _set(tenant_a, key="refrigerant_type", value="R32")
    intervention_id = _intervention(tenant_a)
    _call("POST", f"/interventions/{intervention_id}/closure", _tech(tenant_a), json=_CLOSURE)

    query = text(f"SELECT 1 FROM {table} WHERE tenant_id = :id")
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        seen_by_a = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b["tenant_id"])
        seen_by_b = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()
    assert seen_by_a and seen_by_b == []
