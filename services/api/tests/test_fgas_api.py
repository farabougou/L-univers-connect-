"""API de la fiche d'intervention fluides frigorigènes fluorés (CERFA
15497*04) : POST/GET /interventions/{id}/fgas, GET /fgas-vocabulary. Même
discipline que la clôture structurée (tests/test_passport.py) : idempotence,
conflit sur renvoi différent, immutabilité en base, isolation tenant."""

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import engine
from app.fgas_vocabulary import SECTIONS as FGAS_SECTIONS
from app.i18n import load_catalog
from app.main import app
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)
T0 = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)


def _create_tenant(name: str) -> dict:
    ids = {k: uuid.uuid4() for k in ("tenant_id", "site", "loc")}
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            {"id": ids["tenant_id"], "name": name, "slug": f"{name.lower()}-{ids['tenant_id']}"},
        )
        set_tenant_context(connection, ids["tenant_id"])
        connection.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:site, :tenant_id, 'Site')"),
            ids,
        )
        connection.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:loc, :tenant_id, :site, 'pac-01', 'PAC 01')"
            ),
            ids,
        )
    return ids


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientFgasApiA")
    tenant_b = _create_tenant("ClientFgasApiB")
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


def _tech(tenant):
    return _headers(tenant, ["technicien"])


def _intervention(tenant) -> str:
    response = _call(
        "POST",
        "/interventions",
        _tech(tenant),
        json={"functional_location_id": str(tenant["loc"]), "summary": "Recharge de fluide"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


_FGAS = {
    "fiche_number": "2026-001",
    "operator_name": "Froid Services SARL",
    "operator_address": "1 rue du Froid, 75000 Paris",
    "operator_siret": "12345678900012",
    "operator_capacity_number": "CAP-9999",
    "detenteur_name": "Client Demo",
    "detenteur_address": "2 avenue du Client, 75000 Paris",
    "equipment_identification": "PAC-01 — Chaufferie",
    "refrigerant_name": "R410A",
    "total_charge_kg": 12.5,
    "co2_equivalent_tonnes": 26.1,
    "nature_of_intervention": ["maintenance"],
    "manual_leak_detector_identification": "Détecteur XYZ",
    "manual_leak_detector_checked_on": "2026-09-01",
    "permanent_detection_system": False,
    "leaks_found": False,
    "leaks": [],
    "charged_virgin_kg": 1.0,
    "charged_recycled_kg": 0.0,
    "charged_regenerated_kg": 0.0,
    "recovered_for_treatment_kg": 0.0,
    "recovered_for_reuse_kg": 0.0,
    "waste_classification": [],
    "operator_signatory_name": "Mohamed",
    "operator_signatory_role": "Technicien",
    "signed_at": "2026-10-02",
}


def test_creates_a_fgas_record(two_tenants) -> None:
    tenant_a, _ = two_tenants
    intervention_id = _intervention(tenant_a)

    created = _call(
        "POST", f"/interventions/{intervention_id}/fgas", _tech(tenant_a), json=_FGAS
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["refrigerant_name"] == "R410A"
    assert body["charged_total_kg"] == 1.0  # calculé : A+B+C, jamais saisi


def test_reading_the_record_back(two_tenants) -> None:
    tenant_a, _ = two_tenants
    intervention_id = _intervention(tenant_a)
    _call("POST", f"/interventions/{intervention_id}/fgas", _tech(tenant_a), json=_FGAS)

    read = _call("GET", f"/interventions/{intervention_id}/fgas", _tech(tenant_a))

    assert read.status_code == 200
    assert read.json()["equipment_identification"] == "PAC-01 — Chaufferie"


def test_reading_a_missing_record_is_not_found(two_tenants) -> None:
    tenant_a, _ = two_tenants
    intervention_id = _intervention(tenant_a)
    response = _call("GET", f"/interventions/{intervention_id}/fgas", _tech(tenant_a))
    assert response.status_code == 404
    assert response.json()["code"] == "FGAS_RECORD_NOT_FOUND"


@pytest.mark.parametrize(
    ("overrides", "status_code"),
    [
        ({"nature_of_intervention": []}, 422),  # au moins une case cochée
        ({"nature_of_intervention": ["invented_code"]}, 400),
        ({"nature_of_intervention": ["other"]}, 400),  # détail manquant
        ({"total_charge_kg": -1.0}, 422),
        ({"operator_name": ""}, 422),
    ],
)
def test_invalid_fgas_records_are_refused(two_tenants, overrides, status_code) -> None:
    tenant_a, _ = two_tenants
    intervention_id = _intervention(tenant_a)
    response = _call(
        "POST",
        f"/interventions/{intervention_id}/fgas",
        _tech(tenant_a),
        json={**_FGAS, **overrides},
    )
    assert response.status_code == status_code


def test_a_fgas_record_is_created_once_and_is_immutable(two_tenants) -> None:
    tenant_a, _ = two_tenants
    intervention_id = _intervention(tenant_a)
    url = f"/interventions/{intervention_id}/fgas"

    first = _call("POST", url, _tech(tenant_a), json=_FGAS)
    # Renvoi identique (réponse perdue côté terrain) : la même fiche.
    resent = _call("POST", url, _tech(tenant_a), json=_FGAS)
    different = _call(
        "POST", url, _tech(tenant_a), json={**_FGAS, "observations": "Deuxième version"}
    )
    assert (first.status_code, resent.status_code) == (201, 200)
    assert resent.json()["id"] == first.json()["id"]
    assert (different.status_code, different.json()["code"]) == (409, "FGAS_ALREADY_RECORDED")

    for statement, message in (
        ("UPDATE fgas_intervention_records SET observations = 'x'", "modification interdite"),
        ("DELETE FROM fgas_intervention_records", "suppression interdite"),
    ):
        with pytest.raises(DBAPIError, match=message):
            with engine.begin() as connection:
                set_tenant_context(connection, tenant_a["tenant_id"])
                connection.execute(text(statement))


def test_fgas_vocabulary_is_published(two_tenants) -> None:
    tenant_a, _ = two_tenants
    vocabulary = _call("GET", "/fgas-vocabulary", _tech(tenant_a)).json()
    assert vocabulary["nature_of_intervention"]["maintenance"] == "Maintenance de l’équipement"
    assert set(vocabulary["waste_classification"]) == {
        "un1078_non_flammable", "other_non_flammable", "un3161_flammable", "other_flammable",
    }


def test_fgas_vocabulary_follows_the_requested_language(two_tenants) -> None:
    tenant_a, _ = two_tenants
    english = _call(
        "GET", "/fgas-vocabulary", {**_tech(tenant_a), "Accept-Language": "en"}
    ).json()
    assert english["nature_of_intervention"]["maintenance"] == "Maintenance of the equipment"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_fgas_catalog_matches_the_codes_exactly(locale) -> None:
    catalog = load_catalog(locale, "fgas")
    for section, codes in FGAS_SECTIONS.items():
        assert list(catalog[section]) == list(codes), section


def test_tenant_isolation_on_fgas_records(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    intervention_id = _intervention(tenant_a)
    _call("POST", f"/interventions/{intervention_id}/fgas", _tech(tenant_a), json=_FGAS)

    query = text("SELECT 1 FROM fgas_intervention_records WHERE tenant_id = :id")
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        seen_by_a = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b["tenant_id"])
        seen_by_b = connection.execute(query, {"id": tenant_a["tenant_id"]}).fetchall()
    assert seen_by_a and seen_by_b == []

    # Une intervention d'un autre tenant n'existe pas de son point de vue.
    cross = _call("POST", f"/interventions/{intervention_id}/fgas", _tech(tenant_b), json=_FGAS)
    assert cross.status_code == 404


def test_cerfa_pdf_download_contains_the_recorded_values(two_tenants) -> None:
    """GET .../fgas/cerfa.pdf (app.fgas_pdf) : le CERFA 15497*04 officiel,
    rempli depuis la fiche déjà enregistrée — pas une saisie séparée."""
    tenant_a, _ = two_tenants
    intervention_id = _intervention(tenant_a)
    _call(
        "POST",
        f"/interventions/{intervention_id}/fgas",
        _tech(tenant_a),
        json={**_FGAS, "leaks_found": True, "leaks": [{"location": "Vanne", "repaired": True}]},
    )

    response = _call("GET", f"/interventions/{intervention_id}/fgas/cerfa.pdf", _tech(tenant_a))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "cerfa-15497-2026-001.pdf" in response.headers["content-disposition"]

    reader = PdfReader(io.BytesIO(response.content))
    fields = reader.get_fields()
    assert fields["Fiche_no"]["/V"] == "2026-001"
    assert fields["Equipement_Fluide"]["/V"] == "R410A"
    assert fields["Case_Maintenance"]["/V"] == "/Yes"
    assert fields["Case_Fuite_Oui"]["/V"] == "/Yes"
    assert fields["Fuite_Loca_1"]["/V"] == "Vanne"
    assert fields["Case_Rep_Fuite1_realisee"]["/V"] == "/Yes"


def test_cerfa_pdf_download_requires_an_existing_record(two_tenants) -> None:
    tenant_a, _ = two_tenants
    intervention_id = _intervention(tenant_a)
    response = _call("GET", f"/interventions/{intervention_id}/fgas/cerfa.pdf", _tech(tenant_a))
    assert response.status_code == 404
    assert response.json()["code"] == "FGAS_RECORD_NOT_FOUND"


def test_cerfa_pdf_download_is_tenant_isolated(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    intervention_id = _intervention(tenant_a)
    _call("POST", f"/interventions/{intervention_id}/fgas", _tech(tenant_a), json=_FGAS)

    response = _call(
        "GET", f"/interventions/{intervention_id}/fgas/cerfa.pdf", _tech(tenant_b)
    )
    assert response.status_code == 404
