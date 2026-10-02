"""Fiche d'intervention fluides frigorigènes fluorés (CERFA 15497*04,
app.fgas) : une preuve légale, enregistrée une fois, jamais réécrite,
isolée par tenant comme le reste du dépôt."""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text

from app.db import engine
from app.fgas import FgasConflict, FgasError, FgasNotFound, get_fgas_intervention
from app.fgas import record_fgas_intervention as record
from app.fgas_vocabulary import NATURE_CODES, WASTE_CLASSIFICATION_CODES, labels
from app.tenancy import set_tenant_context
from tests.tenant_cleanup import purge_tenant

T0 = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)


def _create_tenant(name: str) -> dict:
    ids = {k: uuid.uuid4() for k in ("tenant_id", "site", "loc", "intervention")}
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
        connection.execute(
            text(
                "INSERT INTO interventions (id, tenant_id, functional_location_id, technician, "
                "started_at) VALUES (:intervention, :tenant_id, :loc, 'Mohamed', :started_at)"
            ),
            {**ids, "started_at": T0},
        )
    return ids


@pytest.fixture
def tenant():
    ids = _create_tenant("ClientFgasA")
    yield ids
    purge_tenant(ids["tenant_id"])


@pytest.fixture
def two_tenants():
    tenant_a = _create_tenant("ClientFgasA")
    tenant_b = _create_tenant("ClientFgasB")
    yield tenant_a, tenant_b
    for t in (tenant_a, tenant_b):
        purge_tenant(t["tenant_id"])


def _payload(**overrides) -> dict:
    base = dict(
        fiche_number="2026-001",
        operator_name="Froid Services SARL",
        operator_address="1 rue du Froid, 75000 Paris",
        operator_siret="12345678900012",
        operator_capacity_number="CAP-9999",
        detenteur_name="Client Demo",
        detenteur_address="2 avenue du Client, 75000 Paris",
        detenteur_siret=None,
        equipment_identification="PAC-01 — Chaufferie",
        refrigerant_name="R410A",
        total_charge_kg=12.5,
        co2_equivalent_tonnes=26.1,
        nature_of_intervention=["maintenance"],
        nature_other_detail=None,
        manual_leak_detector_identification="Détecteur XYZ",
        manual_leak_detector_checked_on=date(2026, 9, 1),
        permanent_detection_system=False,
        leaks_found=False,
        leaks=[],
        charged_virgin_kg=0.0,
        charged_recycled_kg=0.0,
        charged_regenerated_kg=0.0,
        charged_fluid_name_if_changed=None,
        recovered_for_treatment_kg=0.0,
        recovered_for_reuse_kg=0.0,
        bsff_number=None,
        container_identification=None,
        waste_classification=[],
        waste_classification_other_non_flammable=None,
        waste_classification_other_flammable=None,
        destination_installation=None,
        observations=None,
        operator_signatory_name="Mohamed",
        operator_signatory_role="Technicien",
        detenteur_signatory_name=None,
        detenteur_signatory_role=None,
        signed_at=date(2026, 10, 2),
        created_by="Mohamed",
    )
    base.update(overrides)
    return base


def test_records_a_complete_fiche_and_returns_it(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        record_id, created = record(
            connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
            **_payload(),
        )
        assert created is True
        stored = get_fgas_intervention(connection, tenant["intervention"])
        assert stored["id"] == record_id
        assert stored["refrigerant_name"] == "R410A"
        assert stored["total_charge_kg"] == 12.5


def test_resending_the_same_fiche_is_idempotent(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        first_id, first_created = record(
            connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
            **_payload(),
        )
        second_id, second_created = record(
            connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
            **_payload(),
        )
        assert second_id == first_id
        assert first_created is True
        assert second_created is False


def test_resending_a_different_fiche_is_refused(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        record(
            connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
            **_payload(),
        )
        with pytest.raises(FgasConflict) as excinfo:
            record(
                connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
                **_payload(observations="Deuxième version, jamais acceptée"),
            )
        assert excinfo.value.code == "FGAS_ALREADY_RECORDED"


def test_unknown_nature_code_is_rejected(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(FgasError) as excinfo:
            record(
                connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
                **_payload(nature_of_intervention=["invented_code"]),
            )
        assert excinfo.value.code == "FGAS_CODE_UNKNOWN"


def test_empty_nature_is_rejected(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(FgasError) as excinfo:
            record(
                connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
                **_payload(nature_of_intervention=[]),
            )
        assert excinfo.value.code == "FGAS_NATURE_REQUIRED"


def test_other_nature_requires_detail(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(FgasError) as excinfo:
            record(
                connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
                **_payload(nature_of_intervention=["other"], nature_other_detail=None),
            )
        assert excinfo.value.code == "FGAS_OTHER_DETAIL_REQUIRED"

        record_id, created = record(
            connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
            **_payload(nature_of_intervention=["other"], nature_other_detail="Transfert de fluide"),
        )
        assert created is True
        assert record_id is not None


def test_other_waste_classification_requires_detail(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(FgasError) as excinfo:
            record(
                connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
                **_payload(
                    waste_classification=["other_non_flammable"],
                    waste_classification_other_non_flammable=None,
                ),
            )
        assert excinfo.value.code == "FGAS_OTHER_DETAIL_REQUIRED"


def test_negative_quantity_is_rejected(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(FgasError) as excinfo:
            record(
                connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
                **_payload(total_charge_kg=-1.0),
            )
        assert excinfo.value.code == "FGAS_QUANTITY_NEGATIVE"


def test_leak_without_location_is_rejected(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(FgasError) as excinfo:
            record(
                connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
                **_payload(leaks_found=True, leaks=[{"location": "", "repaired": False}]),
            )
        assert excinfo.value.code == "FGAS_LEAK_LOCATION_REQUIRED"


def test_charged_and_recovered_totals_are_computed_not_trusted(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        record(
            connection, tenant_id=tenant["tenant_id"], intervention_id=tenant["intervention"],
            **_payload(
                charged_virgin_kg=2.0,
                charged_recycled_kg=1.0,
                charged_regenerated_kg=0.5,
                recovered_for_treatment_kg=1.0,
                recovered_for_reuse_kg=0.25,
            ),
        )
        stored = get_fgas_intervention(connection, tenant["intervention"])
        assert stored["charged_total_kg"] == pytest.approx(3.5)
        assert stored["recovered_total_kg"] == pytest.approx(1.25)


def test_unknown_intervention_is_not_found(tenant) -> None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant["tenant_id"])
        with pytest.raises(FgasNotFound):
            record(
                connection, tenant_id=tenant["tenant_id"], intervention_id=uuid.uuid4(),
                **_payload(),
            )


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_vocabulary_catalogs_cover_every_code_in_both_languages(locale) -> None:
    assert set(labels("nature_of_intervention", locale)) == set(NATURE_CODES)
    assert set(labels("waste_classification", locale)) == set(WASTE_CLASSIFICATION_CODES)


def test_isolation_between_tenants(two_tenants) -> None:
    tenant_a, tenant_b = two_tenants
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_a["tenant_id"])
        record(
            connection, tenant_id=tenant_a["tenant_id"], intervention_id=tenant_a["intervention"],
            **_payload(),
        )
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_b["tenant_id"])
        assert get_fgas_intervention(connection, tenant_a["intervention"]) is None
