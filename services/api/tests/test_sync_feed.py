"""Flux de changements incrémental (app/sync_feed.py, app/routers/sync.py).

Ce que ces tests prouvent, contre une vraie base avec sécurité par ligne :
- un parcours par pages rend chaque ligne exactement une fois, y compris quand
  des centaines de lignes ont la même date ;
- une interruption puis une reprise depuis le dernier curseur ne perdent et ne
  dupliquent rien ;
- une ligne validée en retard (date plus ancienne que celles déjà livrées) est
  quand même livrée au parcours suivant, dans la fenêtre de recouvrement ;
- une modification et un archivage/désarchivage d'équipement sont livrés ;
- un client ne voit jamais les lignes d'un autre client.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from app.sync_feed import (
    OVERLAP,
    Cursor,
    FeedCursorInvalid,
    decode_cursor,
    encode_cursor,
    next_cursor,
)
from app.tenancy import set_tenant_context
from tests.jwt_helpers import JWKS, make_token
from tests.tenant_cleanup import purge_tenant

client = TestClient(app)

TOTAL = 25


def _seed(name: str, interventions: int) -> dict:
    tenant_id, site_id, location_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with engine.begin() as c:
        c.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:i, :n, :s)"),
            {"i": tenant_id, "n": name, "s": f"{name.lower()}-{tenant_id}"},
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
        # Une seule transaction : toutes ces lignes reçoivent LA MÊME date de
        # création. C'est le cas qui casse un curseur fondé sur la date seule.
        c.execute(
            text(
                "INSERT INTO interventions (id, tenant_id, functional_location_id, technician,"
                " started_at) SELECT gen_random_uuid(), :t, :l, 'test',"
                " now() - (g || ' minutes')::interval FROM generate_series(1, :n) g"
            ),
            {"t": tenant_id, "l": location_id, "n": interventions},
        )
    return {"tenant_id": tenant_id, "site_id": site_id, "location_id": location_id}


def _insert_intervention(tenant: dict, *, created_at: datetime) -> uuid.UUID:
    intervention_id = uuid.uuid4()
    with engine.begin() as c:
        set_tenant_context(c, tenant["tenant_id"])
        c.execute(
            text(
                "INSERT INTO interventions (id, tenant_id, functional_location_id, technician,"
                " started_at, created_at) VALUES (:i, :t, :l, 'test', now(), :c)"
            ),
            {
                "i": intervention_id,
                "t": tenant["tenant_id"],
                "l": tenant["location_id"],
                "c": created_at,
            },
        )
    return intervention_id


def _sql(tenant: dict, statement: str, **params) -> None:
    with engine.begin() as c:
        set_tenant_context(c, tenant["tenant_id"])
        c.execute(text(statement), params)


@pytest.fixture
def tenants():
    first, second = _seed("SyncA", TOTAL), _seed("SyncB", 3)
    yield first, second
    purge_tenant(first["tenant_id"])
    purge_tenant(second["tenant_id"])


def _get(tenant: dict, route: str, *, roles=None, **params):
    token = make_token(
        roles=roles or ["technicien"], tenant_id=str(tenant["tenant_id"]), sub="tech-sync"
    )
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.get(route, params=params, headers={"Authorization": f"Bearer {token}"})


def _pull_all(tenant: dict, route: str, *, limit: int, after: str | None = None) -> tuple:
    """Parcours complet comme le fait le client : page après page, jusqu'à la fin."""
    items, cursor = [], after
    for _ in range(1000):
        params = {"limit": limit, **({"after": cursor} if cursor else {})}
        page = _get(tenant, route, **params).json()
        items += page["items"]
        cursor = page["next_cursor"]
        if not page["has_more"]:
            return items, cursor
    raise AssertionError("le parcours ne se termine pas")


# --- Parcours par pages --------------------------------------------------


def test_un_parcours_rend_chaque_ligne_une_fois_meme_a_date_identique(tenants) -> None:
    with engine.connect() as c:
        set_tenant_context(c, tenants[0]["tenant_id"])
        distinct_dates = c.execute(
            text("SELECT count(DISTINCT created_at) FROM interventions")
        ).scalar_one()
    assert distinct_dates == 1, "le jeu d'essai doit avoir une date unique pour toutes les lignes"

    items, _ = _pull_all(tenants[0], "/sync/interventions", limit=4)

    ids = [item["id"] for item in items]
    assert len(ids) == TOTAL
    assert len(set(ids)) == TOTAL


def test_la_taille_de_page_ne_change_pas_le_resultat(tenants) -> None:
    petit, _ = _pull_all(tenants[0], "/sync/interventions", limit=1)
    grand, _ = _pull_all(tenants[0], "/sync/interventions", limit=500)

    assert [i["id"] for i in petit] == [i["id"] for i in grand]


def test_chaque_page_annonce_s_il_en_reste(tenants) -> None:
    first = _get(tenants[0], "/sync/interventions", limit=10).json()
    last = _get(tenants[0], "/sync/interventions", limit=100).json()

    assert first["has_more"] is True and len(first["items"]) == 10
    assert last["has_more"] is False and len(last["items"]) == TOTAL


def test_la_charge_ne_contient_que_les_champs_utiles_a_l_ecran(tenants) -> None:
    item = _get(tenants[0], "/sync/interventions", limit=1).json()["items"][0]

    assert set(item) == {
        "id",
        "intervention_type",
        "started_at",
        "ended_at",
        "summary",
        "functional_location_id",
        "work_order_id",
    }


# --- Reprise après interruption -----------------------------------------


def test_une_interruption_puis_une_reprise_ne_perdent_ni_ne_dupliquent(tenants) -> None:
    everything, _ = _pull_all(tenants[0], "/sync/interventions", limit=500)

    page_1 = _get(tenants[0], "/sync/interventions", limit=10).json()
    # Le téléphone perd le réseau ici : seul le curseur de la page 1 a été conservé.
    resumed, _ = _pull_all(tenants[0], "/sync/interventions", limit=7, after=page_1["next_cursor"])

    union = [i["id"] for i in page_1["items"]] + [i["id"] for i in resumed]
    assert union == [i["id"] for i in everything]


def test_rejouer_la_meme_page_donne_la_meme_reponse(tenants) -> None:
    """Une réponse perdue en route : le client redemande la même page."""
    first = _get(tenants[0], "/sync/interventions", limit=10).json()
    cursor = first["next_cursor"]

    again_a = _get(tenants[0], "/sync/interventions", limit=10, after=cursor).json()
    again_b = _get(tenants[0], "/sync/interventions", limit=10, after=cursor).json()

    assert again_a == again_b


# --- Écritures tardives --------------------------------------------------


def test_une_ligne_validee_en_retard_dans_la_fenetre_est_livree_au_parcours_suivant(
    tenants,
) -> None:
    _, cursor = _pull_all(tenants[0], "/sync/interventions", limit=500)

    # Une transaction démarrée il y a 2 minutes se valide maintenant : sa date de
    # création est plus ancienne que celles déjà livrées.
    late_id = _insert_intervention(tenants[0], created_at=datetime.now(UTC) - timedelta(minutes=2))

    items, _ = _pull_all(tenants[0], "/sync/interventions", limit=500, after=cursor)

    assert str(late_id) in [i["id"] for i in items]


def test_le_recouvrement_relit_des_lignes_deja_livrees_sans_les_dupliquer(tenants) -> None:
    """Le prix du recouvrement : des lignes déjà vues reviennent. Le client les
    reconnaît par leur identifiant (voir syncFeed.test.ts) ; le serveur, lui, les
    renvoie identiques."""
    first, cursor = _pull_all(tenants[0], "/sync/interventions", limit=500)

    again, _ = _pull_all(tenants[0], "/sync/interventions", limit=500, after=cursor)

    assert {i["id"] for i in again} <= {i["id"] for i in first}
    assert len(again) == len({i["id"] for i in again})


def test_limite_assumee_une_ligne_plus_ancienne_que_le_recouvrement_n_est_pas_relivree(
    tenants,
) -> None:
    """Documente la borne, pour qu'elle ne change pas sans que quelqu'un le décide."""
    _, cursor = _pull_all(tenants[0], "/sync/interventions", limit=500)
    too_old = _insert_intervention(
        tenants[0], created_at=datetime.now(UTC) - OVERLAP - timedelta(minutes=5)
    )

    items, _ = _pull_all(tenants[0], "/sync/interventions", limit=500, after=cursor)

    assert str(too_old) not in [i["id"] for i in items]


def test_un_nouvel_ajout_apres_le_curseur_est_livre(tenants) -> None:
    _, cursor = _pull_all(tenants[0], "/sync/interventions", limit=500)
    new_id = _insert_intervention(tenants[0], created_at=datetime.now(UTC))

    items, _ = _pull_all(tenants[0], "/sync/interventions", limit=500, after=cursor)

    assert str(new_id) in [i["id"] for i in items]


# --- Modifications et « suppressions » d'équipements ---------------------


def test_une_modification_d_equipement_est_livree(tenants) -> None:
    _, cursor = _pull_all(tenants[0], "/sync/functional-locations", limit=500)
    # Reculer le curseur pour sortir de la fenêtre de recouvrement serait de la
    # triche : la modification doit être vue depuis un curseur réel.
    _sql(tenants[0], "UPDATE functional_locations SET name = 'CTA 01 renommée'")

    items, _ = _pull_all(tenants[0], "/sync/functional-locations", limit=500, after=cursor)

    assert [(i["code"], i["name"]) for i in items] == [("cta-01", "CTA 01 renommée")]


def test_l_archivage_puis_le_desarchivage_sont_livres_comme_modifications(tenants) -> None:
    _sql(tenants[0], "UPDATE functional_locations SET updated_at = now() - interval '1 hour'")
    _, cursor = _pull_all(tenants[0], "/sync/functional-locations", limit=500)

    _sql(tenants[0], "UPDATE functional_locations SET archived_at = now(), archived_by = 'test'")
    archived, cursor_2 = _pull_all(
        tenants[0], "/sync/functional-locations", limit=500, after=cursor
    )
    _sql(tenants[0], "UPDATE functional_locations SET archived_at = NULL, archived_by = NULL")
    restored, _ = _pull_all(tenants[0], "/sync/functional-locations", limit=500, after=cursor_2)

    assert [i["archived"] for i in archived][-1] is True
    assert [i["archived"] for i in restored][-1] is False


def test_le_declencheur_met_a_jour_la_date_de_modification(tenants) -> None:
    with engine.connect() as c:
        set_tenant_context(c, tenants[0]["tenant_id"])
        before = c.execute(text("SELECT updated_at FROM functional_locations")).scalar_one()
    _sql(tenants[0], "UPDATE functional_locations SET name = 'autre'")
    with engine.connect() as c:
        set_tenant_context(c, tenants[0]["tenant_id"])
        after = c.execute(text("SELECT updated_at FROM functional_locations")).scalar_one()

    assert after > before


# --- Isolation, droits, entrées invalides -------------------------------


@pytest.mark.parametrize("route", ["/sync/interventions", "/sync/functional-locations"])
def test_un_client_ne_voit_jamais_les_lignes_d_un_autre(tenants, route) -> None:
    ids_a = {i["id"] for i in _pull_all(tenants[0], route, limit=500)[0]}
    ids_b = {i["id"] for i in _pull_all(tenants[1], route, limit=500)[0]}

    assert ids_a and ids_b
    assert ids_a.isdisjoint(ids_b)


def test_le_curseur_d_un_client_ne_donne_rien_d_un_autre(tenants) -> None:
    """Le curseur n'est qu'une position : l'utiliser avec un autre client ne
    découvre aucune ligne qui ne lui appartient pas."""
    cursor = _get(tenants[0], "/sync/interventions", limit=5).json()["next_cursor"]

    items, _ = _pull_all(tenants[1], "/sync/interventions", limit=500, after=cursor)

    assert {i["id"] for i in items} <= {
        i["id"] for i in _pull_all(tenants[1], "/sync/interventions", limit=500)[0]
    }


@pytest.mark.parametrize("route", ["/sync/interventions", "/sync/functional-locations"])
def test_sans_jeton_la_route_est_refusee(route) -> None:
    assert client.get(route).status_code in (401, 403)


@pytest.mark.parametrize(
    "cursor",
    [
        "pas-un-curseur",
        encode_cursor(Cursor(at=datetime(2026, 1, 1, tzinfo=UTC), id=uuid.uuid4()))[:-6],
    ],
)
def test_un_curseur_invalide_est_refuse_avec_un_code_stable(tenants, cursor) -> None:
    response = _get(tenants[0], "/sync/interventions", after=cursor)

    assert response.status_code == 400
    assert response.json()["code"] == "SYNC_CURSOR_INVALID"


@pytest.mark.parametrize("limit", [0, 501, -1])
def test_des_bornes_de_page_invalides_sont_refusees(tenants, limit) -> None:
    assert _get(tenants[0], "/sync/interventions", limit=limit).status_code == 422


# --- Curseur : propriétés pures -----------------------------------------

_T0 = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def test_le_curseur_fait_l_aller_retour() -> None:
    cursor = Cursor(at=_T0 + timedelta(microseconds=123456), id=uuid.uuid4())

    assert decode_cursor(encode_cursor(cursor)) == cursor


def test_un_curseur_sans_fuseau_est_refuse() -> None:
    import base64

    naive = base64.urlsafe_b64encode(f"2026-10-21T12:00:00|{uuid.uuid4()}".encode()).decode()

    with pytest.raises(FeedCursorInvalid):
        decode_cursor(naive)


def test_au_milieu_d_un_parcours_le_curseur_avance_jusqu_a_la_derniere_ligne() -> None:
    last = Cursor(at=_T0, id=uuid.uuid4())

    assert next_cursor(requested=None, last=last, has_more=True, now=_T0) == last


def test_en_fin_de_parcours_un_curseur_recent_est_recule_de_la_fenetre() -> None:
    last = Cursor(at=_T0, id=uuid.uuid4())

    settled = next_cursor(
        requested=None, last=last, has_more=False, now=_T0 + timedelta(seconds=30)
    )

    assert settled.at == _T0 + timedelta(seconds=30) - OVERLAP
    assert settled < last


def test_en_fin_de_parcours_un_curseur_ancien_n_est_pas_recule() -> None:
    last = Cursor(at=_T0 - timedelta(days=3), id=uuid.uuid4())

    assert next_cursor(requested=None, last=last, has_more=False, now=_T0) == last


def test_sans_nouvelle_ligne_le_curseur_demande_est_conserve() -> None:
    requested = Cursor(at=_T0 - timedelta(days=1), id=uuid.uuid4())

    assert next_cursor(requested=requested, last=None, has_more=False, now=_T0) == requested


def test_une_base_vide_n_invente_pas_de_curseur() -> None:
    assert next_cursor(requested=None, last=None, has_more=False, now=_T0) is None


# --- Compression (connexions faibles) -----------------------------------


def _get_raw(tenant: dict, route: str, headers: dict, **params):
    token = make_token(roles=["technicien"], tenant_id=str(tenant["tenant_id"]))
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.get(
            route,
            params=params,
            headers={"Authorization": f"Bearer {token}", **headers},
        )


def test_la_reponse_est_compressee_quand_le_client_l_accepte(tenants) -> None:
    response = _get_raw(tenants[0], "/sync/interventions", {"Accept-Encoding": "gzip"}, limit=500)

    assert response.headers["content-encoding"] == "gzip"
    on_the_wire = int(response.headers["content-length"])
    assert on_the_wire < len(response.content) / 2
    assert len(response.json()["items"]) == TOTAL


def test_la_reponse_n_est_pas_compressee_sans_accord_du_client(tenants) -> None:
    response = _get_raw(
        tenants[0], "/sync/interventions", {"Accept-Encoding": "identity"}, limit=500
    )

    assert "content-encoding" not in response.headers
    assert len(response.json()["items"]) == TOTAL


def test_une_petite_reponse_n_est_pas_compressee(tenants) -> None:
    response = _get_raw(tenants[1], "/sync/interventions", {"Accept-Encoding": "gzip"}, limit=1)

    assert "content-encoding" not in response.headers


def test_la_compression_conserve_les_en_tetes_de_pagination(tenants) -> None:
    response = _get_raw(tenants[0], "/interventions", {"Accept-Encoding": "gzip"}, limit=20)

    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["x-total-count"] == str(TOTAL)


# --- Fenêtre récente au premier parcours (`since`) ----------------------


def test_since_ne_livre_que_les_lignes_recentes_au_premier_parcours(tenants) -> None:
    old_id = _insert_intervention(tenants[0], created_at=datetime.now(UTC) - timedelta(days=60))
    since = (datetime.now(UTC) - timedelta(days=30)).isoformat()

    items, _ = _pull_all(tenants[0], "/sync/interventions", limit=500)
    recent, _ = _pull_all_since(tenants[0], limit=500, since=since)

    assert str(old_id) in [i["id"] for i in items]
    assert str(old_id) not in [i["id"] for i in recent]
    assert len(recent) == TOTAL


def _pull_all_since(tenant: dict, *, limit: int, since: str) -> tuple:
    page = _get(tenant, "/sync/interventions", limit=limit, since=since).json()
    items, cursor = list(page["items"]), page["next_cursor"]
    while page["has_more"]:
        page = _get(tenant, "/sync/interventions", limit=limit, after=cursor).json()
        items += page["items"]
        cursor = page["next_cursor"]
    return items, cursor


def test_since_est_ignore_quand_un_curseur_est_fourni(tenants) -> None:
    """Une reprise ne doit jamais être tronquée par la fenêtre du premier parcours."""
    cursor = _get(tenants[0], "/sync/interventions", limit=5).json()["next_cursor"]
    far_future = (datetime.now(UTC) + timedelta(days=1)).isoformat()

    resumed = _get(tenants[0], "/sync/interventions", limit=500, after=cursor, since=far_future)

    assert len(resumed.json()["items"]) == TOTAL - 5


def test_since_sans_fuseau_est_refuse(tenants) -> None:
    response = _get(tenants[0], "/sync/interventions", since="2026-10-01T00:00:00")

    assert response.status_code == 400
    assert response.json()["code"] == "SYNC_CURSOR_INVALID"
