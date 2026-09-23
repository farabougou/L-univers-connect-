"""Nomenclature des équipements et code d'inventaire par l'API (ADR 013, L5)."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)


def _create_tenant(name: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": tenant_id, "name": name, "slug": f"{name.lower()}-{tenant_id}"},
        )
    return tenant_id


@pytest.fixture
def tenants():
    tenant_a, tenant_b = (
        _create_tenant("ClientNomenclatureA"),
        _create_tenant("ClientNomenclatureB"),
    )
    yield tenant_a, tenant_b
    for tenant_id in (tenant_a, tenant_b):
        purge_tenant(tenant_id)


def _call(method, path, tenant_id, roles=("admin_tenant",), language=None, **kwargs):
    headers = {"Authorization": f"Bearer {make_token(tenant_id=str(tenant_id), roles=list(roles))}"}
    if language:
        headers["Accept-Language"] = language
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.request(method, path, headers=headers, **kwargs)


def _model(tenant_id, equipment_type="chiller"):
    return _call(
        "POST",
        "/product-models",
        tenant_id,
        json={
            "manufacturer": "Fabricant Démo",
            "reference": "GF-400",
            "equipment_type": equipment_type,
            "manufacturer_designation": "Groupe d'eau glacée à condensation par air",
        },
    )


def _unit(tenant_id, model_id, serial, asset_code=None):
    body = {"product_model_id": model_id, "serial_number": serial}
    if asset_code:
        body["asset_code"] = asset_code
    return _call("POST", "/physical-units", tenant_id, json=body)


def test_equipment_types_are_listed_in_the_requested_language(tenants) -> None:
    tenant_a, _ = tenants
    french = _call("GET", "/equipment-types", tenant_a, roles=("technicien",)).json()
    english = _call("GET", "/equipment-types", tenant_a, roles=("technicien",), language="en")

    labels_fr = {t["code"]: t["label"] for t in french["types"]}
    labels_en = {t["code"]: t["label"] for t in english.json()["types"]}
    assert labels_fr["air_handling_unit"] == "Centrale de traitement d’air"
    assert labels_en["air_handling_unit"] == "Air handling unit"
    assert {t["code"]: t["brick"] for t in french["types"]}["heat_pump"] is None


def test_manufacturer_wording_gets_a_suggestion_never_an_imposed_type(tenants) -> None:
    tenant_a, _ = tenants
    suggested = _call(
        "GET", "/equipment-types/suggestion", tenant_a, params={"text": "PAC air/eau"}
    )
    unknown = _call("GET", "/equipment-types/suggestion", tenant_a, params={"text": "Machine"})
    assert suggested.json() == {"equipment_type": "heat_pump"}
    assert unknown.json() == {"equipment_type": None}


def test_a_model_keeps_the_manufacturer_designation_and_the_universal_type(tenants) -> None:
    tenant_a, _ = tenants
    created = _model(tenant_a)
    refused = _model(tenant_a, equipment_type="machine")

    assert created.status_code == 201
    assert (created.json()["equipment_type"], created.json()["manufacturer_designation"]) == (
        "chiller",
        "Groupe d'eau glacée à condensation par air",
    )
    assert (refused.status_code, refused.json()["code"]) == (422, "EQUIPMENT_TYPE_UNKNOWN")


def test_asset_code_is_unique_within_a_customer_only(tenants) -> None:
    tenant_a, tenant_b = tenants
    model_a = _model(tenant_a).json()["id"]
    model_b = _model(tenant_b).json()["id"]

    first = _unit(tenant_a, model_a, "SN-1", asset_code="INV-0001")
    duplicate = _unit(tenant_a, model_a, "SN-2", asset_code="INV-0001")
    other_customer = _unit(tenant_b, model_b, "SN-1", asset_code="INV-0001")

    assert first.json()["asset_code"] == "INV-0001"
    assert (duplicate.status_code, duplicate.json()["code"]) == (409, "ASSET_CODE_ALREADY_USED")
    assert other_customer.status_code == 201


def test_asset_code_can_be_set_later_and_is_audited(tenants) -> None:
    tenant_a, _ = tenants
    unit_id = _unit(tenant_a, _model(tenant_a).json()["id"], "SN-9").json()["id"]

    set_code = _call(
        "PUT", f"/physical-units/{unit_id}/asset-code", tenant_a, json={"asset_code": "INV-9"}
    )
    as_technicien = _call(
        "PUT",
        f"/physical-units/{unit_id}/asset-code",
        tenant_a,
        roles=("technicien",),
        json={"asset_code": "INV-10"},
    )
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a)
        payload = connection.execute(
            text("SELECT payload FROM audit_log WHERE action = 'physical_unit.asset_code_set'")
        ).scalar()

    assert set_code.json()["asset_code"] == "INV-9"
    assert as_technicien.status_code == 403
    assert payload == {"previous": None, "asset_code": "INV-9"}
