"""Pagination facultative des listes qui grossissent sans fin (audit V5 du
20/10/2026, app/pagination.py).

Sans `limit`, la réponse reste exactement celle d'avant (aucun plafond silencieux).
Avec `limit`/`offset`, les pages sont disjointes, complètes, dans un ordre stable,
et `X-Total-Count` ne compte jamais les lignes d'un autre client.
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.tenancy import set_tenant_context
from tests.db_helpers import purge_audit_log_for_tenant, purge_documents_for_tenant
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)

ROWS_A = 25
ROWS_B = 3
ROUTES = ["/work-orders", "/interventions", "/alarms", "/findings", "/documents/portfolio"]


def _seed(tenant_name: str, rows: int) -> dict:
    tenant_id, site_id, location_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with engine.begin() as c:
        c.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:i, :n, :s)"),
            {"i": tenant_id, "n": tenant_name, "s": f"{tenant_name.lower()}-{tenant_id}"},
        )
        set_tenant_context(c, tenant_id)
        c.execute(
            text("INSERT INTO sites (id, tenant_id, name) VALUES (:i, :t, 'Site')"),
            {"i": site_id, "t": tenant_id},
        )
        c.execute(
            text(
                "INSERT INTO functional_locations (id, tenant_id, site_id, code, name) "
                "VALUES (:i, :t, :s, 'cta-01', 'CTA 01')"
            ),
            {"i": location_id, "t": tenant_id, "s": site_id},
        )
        bind = {"t": tenant_id, "l": location_id, "n": rows}
        c.execute(
            text(
                "INSERT INTO work_orders (id, tenant_id, functional_location_id, title, created_by,"
                " created_at) SELECT gen_random_uuid(), :t, :l, 'OT ' || g, 'test',"
                " now() - (g || ' minutes')::interval FROM generate_series(1, :n) g"
            ),
            bind,
        )
        c.execute(
            text(
                "INSERT INTO interventions (id, tenant_id, functional_location_id, technician,"
                " started_at) SELECT gen_random_uuid(), :t, :l, 'test',"
                " now() - (g || ' minutes')::interval FROM generate_series(1, :n) g"
            ),
            bind,
        )
        c.execute(
            text(
                "INSERT INTO alarms (id, tenant_id, functional_location_id, severity, message,"
                " raised_by, raised_at, handling_status) SELECT gen_random_uuid(), :t, :l,"
                " 'warning', 'Alarme ' || g, 'test', now() - (g || ' minutes')::interval,"
                " CASE WHEN g % 5 = 0 THEN 'open' ELSE 'closed' END FROM generate_series(1, :n) g"
            ),
            bind,
        )
        c.execute(
            text(
                "INSERT INTO findings (id, tenant_id, subject_node_id, kind, method, dedup_key,"
                " severity, title, first_seen_at, last_seen_at, reason_code, certainty,"
                " action_required, handling_status) SELECT gen_random_uuid(), :t, :l, 'anomaly',"
                " 'statistical', 'k-' || g, 'warning', 'Constat ' || g,"
                " now() - (g || ' minutes')::interval, now() - (g || ' minutes')::interval,"
                " 'RULE_X', 'detected', false,"
                " CASE WHEN g % 5 = 0 THEN 'open' ELSE 'closed' END FROM generate_series(1, :n) g"
            ),
            bind,
        )
        c.execute(
            text(
                "INSERT INTO documents (id, tenant_id, functional_location_id, category,"
                " storage_key, content_type, filename, sha256, uploaded_by, uploaded_at)"
                " SELECT gen_random_uuid(), :t, :l, 'manual', 'k/' || :t || '/' || g,"
                " 'application/pdf', 'doc-' || g || '.pdf', repeat('a', 64), 'test',"
                " now() - (g || ' minutes')::interval FROM generate_series(1, :n) g"
            ),
            bind,
        )
    return {"tenant_id": tenant_id, "site_id": site_id}


def _cleanup(tenant: dict) -> None:
    tenant_id = tenant["tenant_id"]
    purge_audit_log_for_tenant(tenant_id)
    purge_documents_for_tenant(tenant_id)
    with engine.begin() as c:
        set_tenant_context(c, tenant_id)
        for table in (
            "findings",
            "alarms",
            "interventions",
            "work_orders",
            "functional_locations",
            "sites",
        ):
            c.execute(text(f"DELETE FROM {table} WHERE tenant_id = :t"), {"t": tenant_id})
    with engine.begin() as c:
        c.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tenant_id})


@pytest.fixture
def tenants():
    first, second = _seed("PaginationA", ROWS_A), _seed("PaginationB", ROWS_B)
    yield first, second
    _cleanup(first)
    _cleanup(second)


def _get(tenant: dict, route: str, **params):
    token = make_token(roles=["responsable_exploitation"], tenant_id=str(tenant["tenant_id"]))
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.get(route, params=params, headers={"Authorization": f"Bearer {token}"})


@pytest.mark.parametrize("route", ROUTES)
def test_sans_limit_la_reponse_est_complete_et_sans_total(tenants, route) -> None:
    response = _get(tenants[0], route)

    assert response.status_code == 200, response.text
    assert len(response.json()) == ROWS_A
    assert "x-total-count" not in response.headers


@pytest.mark.parametrize("route", ROUTES)
def test_les_pages_sont_disjointes_completes_et_dans_le_meme_ordre(tenants, route) -> None:
    everything = [row["id"] for row in _get(tenants[0], route).json()]

    pages = [_get(tenants[0], route, limit=10, offset=offset) for offset in (0, 10, 20)]

    assert all(page.status_code == 200 for page in pages)
    assert [len(page.json()) for page in pages] == [10, 10, 5]
    assert {page.headers["x-total-count"] for page in pages} == {str(ROWS_A)}
    assert [row["id"] for page in pages for row in page.json()] == everything


@pytest.mark.parametrize("route", ROUTES)
def test_un_decalage_au_dela_du_total_renvoie_une_liste_vide_avec_le_total(tenants, route) -> None:
    response = _get(tenants[0], route, limit=10, offset=1000)

    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["x-total-count"] == str(ROWS_A)


@pytest.mark.parametrize("route", ROUTES)
def test_le_total_ne_compte_jamais_les_lignes_d_un_autre_client(tenants, route) -> None:
    response = _get(tenants[1], route, limit=10)

    assert len(response.json()) == ROWS_B
    assert response.headers["x-total-count"] == str(ROWS_B)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 1001}, {"offset": -1}])
def test_des_bornes_invalides_sont_refusees(tenants, route, params) -> None:
    assert _get(tenants[0], route, **params).status_code == 422


@pytest.mark.parametrize("route", ["/alarms", "/findings"])
def test_la_pagination_se_combine_aux_filtres(tenants, route) -> None:
    """5 lignes sur 25 sont « open » : le total suit le filtre, pas la table."""
    first = _get(tenants[0], route, handling_status="open", limit=2)
    last = _get(tenants[0], route, handling_status="open", limit=2, offset=4)

    assert [len(first.json()), len(last.json())] == [2, 1]
    assert first.headers["x-total-count"] == "5"
    assert {row["handling_status"] for row in first.json() + last.json()} == {"open"}
