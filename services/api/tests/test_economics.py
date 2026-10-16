"""Asset Economics Engine — premier maillon (V2, 02/10/2026, ADR 012 §15).

Périmètre testé ici : le tarif énergétique versionné (app.config_versions,
config_type energy_tariff) et le calcul à la lecture du coût estimé. Voir
app/economics.py pour le pourquoi de ce périmètre volontairement étroit."""

import uuid
from datetime import UTC, datetime

import pytest

from app.config_versions import ConfigInvalid, activate_version, create_version
from app.economics import ENERGY_TARIFF, estimate_energy_cost, get_active_tariff
from tests.energy_fixtures import cleanup_tenant, create_tenant_with_energy_meter, in_tenant
from tests.error_helpers import raises_code

T0 = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)


@pytest.fixture
def tenant():
    created = create_tenant_with_energy_meter("ClientEconomics")
    yield created
    cleanup_tenant(created)


def _create_tariff(connection, tenant, *, currency="EUR", price_per_kwh=0.2, **overrides):
    content = {"currency": currency, "price_per_kwh": price_per_kwh}
    content.update(overrides)
    return create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ENERGY_TARIFF,
        subject_key=str(tenant["site"]),
        content=content,
        author="responsable",
        reason="test",
    )


# --- Validation du contenu du tarif --------------------------------------------------------


def test_un_tarif_avec_une_devise_mal_formee_est_refuse(tenant) -> None:
    with in_tenant(tenant) as connection:
        with raises_code(ConfigInvalid, "ENERGY_TARIFF_CONTENT_INVALID"):
            _create_tariff(connection, tenant, currency="euros")


def test_un_tarif_avec_un_prix_negatif_ou_nul_est_refuse(tenant) -> None:
    with in_tenant(tenant) as connection:
        with raises_code(ConfigInvalid, "ENERGY_TARIFF_CONTENT_INVALID"):
            _create_tariff(connection, tenant, price_per_kwh=0)


def test_un_tarif_avec_un_champ_inconnu_est_refuse(tenant) -> None:
    with in_tenant(tenant) as connection:
        with raises_code(ConfigInvalid, "ENERGY_TARIFF_CONTENT_INVALID"):
            _create_tariff(connection, tenant, taxe_incluse=True)


# --- Un seul tarif actif par site -----------------------------------------------------------


def test_aucun_tarif_actif_tant_que_rien_n_a_ete_active(tenant) -> None:
    with in_tenant(tenant) as connection:
        _create_tariff(connection, tenant)
        assert get_active_tariff(connection, tenant["site"]) is None


def test_le_tarif_active_devient_le_tarif_actif_du_site(tenant) -> None:
    with in_tenant(tenant) as connection:
        version_id = _create_tariff(connection, tenant, currency="EUR", price_per_kwh=0.25)
        activate_version(
            connection, version_id=version_id, activated_by="responsable", activated_at=T0
        )
        active = get_active_tariff(connection, tenant["site"])
    assert active == {"currency": "EUR", "price_per_kwh": 0.25}


def test_activer_un_nouveau_tarif_remplace_l_ancien_sans_le_detruire(tenant) -> None:
    with in_tenant(tenant) as connection:
        first = _create_tariff(connection, tenant, price_per_kwh=0.20)
        activate_version(connection, version_id=first, activated_by="responsable", activated_at=T0)
        second = _create_tariff(connection, tenant, price_per_kwh=0.30)
        activate_version(
            connection, version_id=second, activated_by="responsable", activated_at=T0
        )
        active = get_active_tariff(connection, tenant["site"])
    assert active["price_per_kwh"] == 0.30


def test_un_autre_site_n_a_pas_de_tarif_actif(tenant) -> None:
    other_site = uuid.uuid4()
    with in_tenant(tenant) as connection:
        version_id = _create_tariff(connection, tenant)
        activate_version(
            connection, version_id=version_id, activated_by="responsable", activated_at=T0
        )
        assert get_active_tariff(connection, other_site) is None


# --- Calcul du coût estimé (fonction pure) ---------------------------------------------------


def test_le_cout_prefere_la_consommation_normalisee_a_la_brute() -> None:
    tariff = {"currency": "EUR", "price_per_kwh": 0.2}
    cost = estimate_energy_cost(raw_consumption=1000.0, normalized_consumption=806.0, tariff=tariff)
    assert cost == {"amount": 161.2, "currency": "EUR", "price_per_kwh": 0.2, "basis": "normalized"}


def test_le_cout_retombe_sur_la_consommation_brute_si_pas_de_normalisation() -> None:
    tariff = {"currency": "EUR", "price_per_kwh": 0.2}
    cost = estimate_energy_cost(raw_consumption=620.0, normalized_consumption=None, tariff=tariff)
    assert cost == {"amount": 124.0, "currency": "EUR", "price_per_kwh": 0.2, "basis": "raw"}


def test_le_montant_est_arrondi_a_deux_decimales() -> None:
    tariff = {"currency": "EUR", "price_per_kwh": 0.1337}
    cost = estimate_energy_cost(raw_consumption=100.0, normalized_consumption=None, tariff=tariff)
    assert cost["amount"] == 13.37
