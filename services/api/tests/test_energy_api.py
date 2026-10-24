"""API du moteur énergétique (app/routers/energy.py), premier fichier de
tests au niveau API pour ce routeur : vérifie que le coût estimé
(app.economics, V2 02/10/2026) apparaît correctement sur les résultats
normalisés exposés, sans jamais être présent quand aucun tarif n'est actif."""

import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.config_versions import activate_version, create_version
from app.db import engine
from app.economics import ENERGY_TARIFF
from app.energy.baseline import ENERGY_BASELINE
from app.energy.weather import record_weather_observation
from app.main import app
from app.points import create_point, decide_point, get_point
from app.telemetry import record_measurement
from tests.energy_fixtures import cleanup_tenant, create_tenant_with_energy_meter, in_tenant
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)
T0 = datetime(2026, 9, 24, 8, 0, tzinfo=UTC)


@pytest.fixture
def tenant():
    created = create_tenant_with_energy_meter("ClientEnergyApi")
    yield created
    cleanup_tenant(created)


def _headers(tenant, roles=("responsable_exploitation",)):
    token = make_token(roles=list(roles), tenant_id=str(tenant["tenant_id"]))
    return {"Authorization": f"Bearer {token}"}


def _prepare_normalized_period(connection, tenant):
    """Reproduit exactement les données de
    test_a_normalized_result_carries_its_full_traceability (tests/test_energy.py) :
    310 degrés-jours, 620 kWh bruts, 806 kWh normalisés."""
    point = get_point(connection, tenant["meter"])
    record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=point,
        value=1000.0,
        measured_at=datetime(2025, 12, 31, 23, 0, tzinfo=UTC),
        origin="simulated",
        source="simulator",
        received_at=datetime(2025, 12, 31, 23, 0, tzinfo=UTC),
    )
    record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=point,
        value=1620.0,
        measured_at=datetime(2026, 1, 31, 23, 0, tzinfo=UTC),
        origin="simulated",
        source="simulator",
        received_at=datetime(2026, 1, 31, 23, 0, tzinfo=UTC),
    )
    for start, days, temperature in ((date(2025, 1, 1), 31, 5.0), (date(2026, 1, 1), 31, 8.0)):
        for offset in range(days):
            record_weather_observation(
                connection,
                tenant_id=tenant["tenant_id"],
                site_id=tenant["site"],
                observed_date=start + timedelta(days=offset),
                mean_temperature_celsius=temperature,
                created_by="technicien",
            )
    baseline_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ENERGY_BASELINE,
        subject_key=f"baseline:{tenant['meter']}",
        content={
            "point_id": str(tenant["meter"]),
            "method": "degree_day_ratio",
            "method_version": "v1",
            "reference_period": {"start": "2025-01-01", "end": "2025-01-31"},
            "degree_day_base_temperature_celsius": 18.0,
            "degree_day_kind": "heating",
        },
        author="responsable",
        reason="test",
    )
    activate_version(
        connection, version_id=baseline_id, activated_by="responsable", activated_at=T0
    )
    return baseline_id


def _prepare_normalized_period_for_second_meter(connection, tenant):
    """Un second équipement (autre functional_location, autre point) sur le
    même site, pour l'audit sécurité du 16/10/2026 : une comparaison ne doit
    jamais mélanger deux équipements différents, même du même site. Réutilise
    les observations météo déjà posées par `_prepare_normalized_period` (même
    site, mêmes dates) — `record_weather_observation` est idempotent sur une
    même date."""
    location_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
            "VALUES (:id, :tenant_id, :site_id, 'pac-02', 'PAC 02')"
        ),
        {"id": location_id, "tenant_id": tenant["tenant_id"], "site_id": tenant["site"]},
    )
    point_id = create_point(
        connection,
        tenant_id=tenant["tenant_id"],
        code="PAC02-ENERGIE",
        name="Énergie active totale",
        value_type="number",
        point_class="energy_meter_reading",
        unit="kW.h",
        functional_location_id=location_id,
        expected_interval_seconds=3600,
        min_value=0,
        created_by="test",
    )
    decide_point(connection, point_id=point_id, decision="validated")
    point = get_point(connection, point_id)
    record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=point,
        value=1000.0,
        measured_at=datetime(2025, 12, 31, 23, 0, tzinfo=UTC),
        origin="simulated",
        source="simulator",
        received_at=datetime(2025, 12, 31, 23, 0, tzinfo=UTC),
    )
    record_measurement(
        connection,
        tenant_id=tenant["tenant_id"],
        point=point,
        value=1620.0,
        measured_at=datetime(2026, 1, 31, 23, 0, tzinfo=UTC),
        origin="simulated",
        source="simulator",
        received_at=datetime(2026, 1, 31, 23, 0, tzinfo=UTC),
    )
    for start, days, temperature in ((date(2025, 1, 1), 31, 5.0), (date(2026, 1, 1), 31, 8.0)):
        for offset in range(days):
            record_weather_observation(
                connection,
                tenant_id=tenant["tenant_id"],
                site_id=tenant["site"],
                observed_date=start + timedelta(days=offset),
                mean_temperature_celsius=temperature,
                created_by="technicien",
            )
    baseline_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ENERGY_BASELINE,
        subject_key=f"baseline:{point_id}",
        content={
            "point_id": str(point_id),
            "method": "degree_day_ratio",
            "method_version": "v1",
            "reference_period": {"start": "2025-01-01", "end": "2025-01-31"},
            "degree_day_base_temperature_celsius": 18.0,
            "degree_day_kind": "heating",
        },
        author="responsable",
        reason="test",
    )
    activate_version(
        connection, version_id=baseline_id, activated_by="responsable", activated_at=T0
    )
    return baseline_id


def _activate_tariff(connection, tenant, *, currency="EUR", price_per_kwh=0.2):
    version_id = create_version(
        connection,
        tenant_id=tenant["tenant_id"],
        config_type=ENERGY_TARIFF,
        subject_key=str(tenant["site"]),
        content={"currency": currency, "price_per_kwh": price_per_kwh},
        author="responsable",
        reason="test",
    )
    activate_version(connection, version_id=version_id, activated_by="responsable", activated_at=T0)


def test_un_resultat_normalise_sans_tarif_actif_n_a_pas_de_cout_estime(tenant) -> None:
    with in_tenant(tenant) as connection:
        baseline_id = _prepare_normalized_period(connection, tenant)

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/energy/normalized-results",
            json={
                "baseline_config_version_id": str(baseline_id),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
            headers=_headers(tenant),
        )
    assert response.status_code == 201, response.text
    assert response.json()["estimated_cost"] is None


def test_un_resultat_normalise_avec_tarif_actif_porte_son_cout_estime(tenant) -> None:
    with in_tenant(tenant) as connection:
        baseline_id = _prepare_normalized_period(connection, tenant)
        _activate_tariff(connection, tenant, currency="EUR", price_per_kwh=0.2)

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        computed = client.post(
            "/energy/normalized-results",
            json={
                "baseline_config_version_id": str(baseline_id),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
            headers=_headers(tenant),
        )
        assert computed.status_code == 201, computed.text
        body = computed.json()
        # 806 kWh normalisés (voir test_energy.py) à 0,20 EUR/kWh.
        assert body["estimated_cost"] == {
            "amount": 161.2,
            "currency": "EUR",
            "price_per_kwh": 0.2,
            "basis": "normalized",
        }
        result_id = body["id"]

        listed = client.get(
            "/energy/normalized-results",
            params={"functional_location_id": str(tenant["location"])},
            headers=_headers(tenant),
        )
        assert listed.status_code == 200, listed.text
        assert listed.json()[0]["estimated_cost"]["amount"] == 161.2

        fetched = client.get(f"/energy/normalized-results/{result_id}", headers=_headers(tenant))
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["estimated_cost"]["amount"] == 161.2


def test_changer_le_tarif_ne_modifie_pas_un_resultat_deja_calcule_mais_son_cout_a_la_lecture(
    tenant,
) -> None:
    with in_tenant(tenant) as connection:
        baseline_id = _prepare_normalized_period(connection, tenant)
        _activate_tariff(connection, tenant, price_per_kwh=0.2)

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        computed = client.post(
            "/energy/normalized-results",
            json={
                "baseline_config_version_id": str(baseline_id),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
            headers=_headers(tenant),
        )
        result_id = computed.json()["id"]
        assert computed.json()["estimated_cost"]["amount"] == 161.2

        with in_tenant(tenant) as connection:
            _activate_tariff(connection, tenant, price_per_kwh=0.3)

        refetched = client.get(f"/energy/normalized-results/{result_id}", headers=_headers(tenant))
    # Le résultat persisté (consommations, méthode...) ne change jamais ;
    # seul le coût, calculé à la lecture, suit le nouveau tarif actif.
    assert refetched.json()["normalized_consumption"] == pytest.approx(806.0)
    assert refetched.json()["estimated_cost"]["amount"] == pytest.approx(806.0 * 0.3, abs=0.01)


def test_comparer_deux_resultats_du_meme_equipement_est_accepte(tenant) -> None:
    with in_tenant(tenant) as connection:
        baseline_id = _prepare_normalized_period(connection, tenant)

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        body = {
            "baseline_config_version_id": str(baseline_id),
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        }
        # Un nouvel appel pour la même période crée une nouvelle ligne
        # (jamais une mise à jour) : deux résultats distincts pour le même
        # point, exactement ce qu'une comparaison légitime met en regard.
        reference = client.post("/energy/normalized-results", json=body, headers=_headers(tenant))
        analyzed = client.post("/energy/normalized-results", json=body, headers=_headers(tenant))
        assert reference.status_code == 201, reference.text
        assert analyzed.status_code == 201, analyzed.text

        comparison = client.get(
            "/energy/comparison",
            params={
                "reference_result_id": reference.json()["id"],
                "analyzed_result_id": analyzed.json()["id"],
            },
            headers=_headers(tenant),
        )
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["comparable"] is True


def test_comparer_deux_resultats_d_equipements_differents_est_refuse(tenant) -> None:
    """Audit sécurité du 16/10/2026 (« capacités et limites restent propres
    à chaque site ») : rien ne doit permettre de comparer la consommation
    normalisée d'un équipement à celle d'un équipement sans rapport —
    capacités, usages et climats différents rendraient le pourcentage
    d'écart arithmétiquement valide mais sans aucun sens."""
    with in_tenant(tenant) as connection:
        baseline_id = _prepare_normalized_period(connection, tenant)
        other_baseline_id = _prepare_normalized_period_for_second_meter(connection, tenant)

    with patch("app.auth.fetch_jwks", return_value=JWKS):
        reference = client.post(
            "/energy/normalized-results",
            json={
                "baseline_config_version_id": str(baseline_id),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
            headers=_headers(tenant),
        )
        other_equipment = client.post(
            "/energy/normalized-results",
            json={
                "baseline_config_version_id": str(other_baseline_id),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
            headers=_headers(tenant),
        )
        assert reference.status_code == 201, reference.text
        assert other_equipment.status_code == 201, other_equipment.text

        comparison = client.get(
            "/energy/comparison",
            params={
                "reference_result_id": reference.json()["id"],
                "analyzed_result_id": other_equipment.json()["id"],
            },
            headers=_headers(tenant),
        )
    assert comparison.status_code == 422, comparison.text
    assert comparison.json()["code"] == "ENERGY_COMPARISON_CROSS_EQUIPMENT"


def test_lister_n_resultats_ne_cherche_le_site_et_le_tarif_qu_une_seule_fois(tenant) -> None:
    """Audit V5 du 20/10/2026 : une liste de N résultats d'un même équipement
    déclenchait N recherches identiques du site et du tarif actif (2 x N
    requêtes). Le tarif ne dépend que de l'équipement : une seule recherche
    suffit, quel que soit le nombre de résultats."""
    with in_tenant(tenant) as connection:
        baseline_id = _prepare_normalized_period(connection, tenant)
        _activate_tariff(connection, tenant, price_per_kwh=0.2)

    statements: list[str] = []

    def _record(_connection, _cursor, statement, _parameters, _context, _executemany) -> None:
        statements.append(statement)

    body = {
        "baseline_config_version_id": str(baseline_id),
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
    }
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        for _ in range(4):
            created = client.post("/energy/normalized-results", json=body, headers=_headers(tenant))
            assert created.status_code == 201, created.text

        event.listen(engine, "before_cursor_execute", _record)
        try:
            listed = client.get(
                "/energy/normalized-results",
                params={"functional_location_id": str(tenant["location"])},
                headers=_headers(tenant),
            )
        finally:
            event.remove(engine, "before_cursor_execute", _record)

    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 4
    assert all(item["estimated_cost"]["amount"] == 161.2 for item in listed.json())
    site_lookups = [s for s in statements if "SELECT site_id FROM functional_locations" in s]
    tariff_lookups = [s for s in statements if "FROM config_versions WHERE config_type" in s]
    assert len(site_lookups) == 1
    assert len(tariff_lookups) == 1
