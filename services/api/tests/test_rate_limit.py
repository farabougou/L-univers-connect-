"""app/rate_limit.py : la clé de limitation (audit V5 du 20/10/2026).

Le serveur Next.js appelle l'API au nom de toutes les personnes connectées,
sans transmettre leur adresse : avec une clé par adresse IP seule, tous les
utilisateurs de tous les clients partageaient un unique quota. Ces tests
prouvent, sur une vraie pile HTTP (middleware slowapi, vérification réelle
des jetons), que chaque identité vérifiée a son propre quota — et qu'un jeton
non vérifiable n'en obtient jamais un neuf.
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse

from app import auth
from app.auth import issue_device_token
from app.rate_limit import ip_rate_limit_key, rate_limit_key
from tests.jwt_helpers import JWKS, generate_keypair, make_token

LIMIT = 3


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setitem(auth._jwks_cache, "keys", JWKS)
    probe = Limiter(key_func=rate_limit_key, default_limits=[f"{LIMIT}/minute"])
    app = FastAPI()
    app.state.limiter = probe
    app.add_exception_handler(
        RateLimitExceeded,
        lambda request, exc: JSONResponse({"code": "RATE_LIMITED"}, status_code=429),
    )
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    return TestClient(app)


def _statuses(client: TestClient, token: str | None, count: int) -> list[int]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return [client.get("/ping", headers=headers).status_code for _ in range(count)]


def _exhaust(client: TestClient, token: str | None) -> None:
    assert _statuses(client, token, LIMIT) == [200] * LIMIT
    assert _statuses(client, token, 1) == [429]


def test_deux_personnes_derriere_la_meme_adresse_ont_chacune_leur_quota(client) -> None:
    alice = make_token(sub="alice")
    bob = make_token(sub="bob")

    _exhaust(client, alice)

    assert _statuses(client, bob, LIMIT) == [200] * LIMIT


def test_deux_appareils_ont_chacun_leur_quota(client) -> None:
    def device_token() -> str:
        return issue_device_token(
            device_id=uuid.uuid4(), tenant_id=uuid.uuid4(), site_id=None, scopes=["telemetry:write"]
        )

    _exhaust(client, device_token())

    assert _statuses(client, device_token(), LIMIT) == [200] * LIMIT


def test_un_jeton_falsifie_ou_expire_n_ouvre_jamais_un_quota_neuf(client) -> None:
    """Sans cette garantie, quiconque forge des jetons au `sub` différent
    contournerait la limite : chacun retombe sur le quota de son adresse."""
    _exhaust(client, None)

    other_private_key, _ = generate_keypair()
    forged = [make_token(sub=f"intrus-{i}", private_key=other_private_key) for i in range(3)]
    expired = make_token(sub="perime", expired=True)
    for token in [*forged, expired]:
        assert _statuses(client, token, 1) == [429]

    assert _statuses(client, make_token(sub="alice"), 1) == [200]


def test_sans_cle_en_cache_le_jeton_retombe_sur_l_adresse_sans_appel_reseau(
    client, monkeypatch
) -> None:
    """Le middleware tourne sur la boucle d'événements : un appel bloquant au
    fournisseur OIDC y gèlerait toutes les requêtes s'il est indisponible."""
    monkeypatch.setitem(auth._jwks_cache, "keys", None)
    monkeypatch.setattr(auth, "fetch_jwks", lambda: pytest.fail("appel réseau interdit ici"))

    _exhaust(client, make_token(sub="alice"))

    assert _statuses(client, make_token(sub="bob"), 1) == [429]


def test_la_sonde_de_sante_n_est_jamais_limitee_en_debit() -> None:
    """Audit V5 du 20/10/2026 : `/health` est appelée sans jeton, donc sur le quota
    de l'adresse IP — partagé par tout le trafic anonyme derrière un proxy. Limitée,
    elle répondrait 429 sous un excès de trafic, et la plateforme pourrait
    redémarrer un service en bonne santé."""
    from app.main import app as real_app

    real = TestClient(real_app)

    health = {real.get("/health").status_code for _ in range(150)}
    other = [real.get("/health/db").status_code for _ in range(130)]

    assert health == {200}
    assert 429 in other


# --- Adresse du client derrière le proxy de l'hébergeur ------------------
#
# Constat du 21/10/2026 : Railway transmet l'adresse du client dans `X-Real-IP`
# (documentation Railway, « Specs & Limits »). Sans lecture de cet en-tête, tous
# les clients anonymes partagent l'adresse du proxy, donc UN quota : n'importe qui
# peut épuiser celui de `/devices/auth` pour toute la flotte d'appareils.


@pytest.fixture
def ip_client(monkeypatch):
    """Application minimale dont la clé est la clé par adresse (route ouverte)."""

    def build(header: str) -> TestClient:
        monkeypatch.setattr("app.rate_limit.settings.client_ip_header", header)
        probe = Limiter(key_func=ip_rate_limit_key, default_limits=[f"{LIMIT}/minute"])
        app = FastAPI()
        app.state.limiter = probe
        app.add_exception_handler(
            RateLimitExceeded,
            lambda request, exc: JSONResponse({"code": "RATE_LIMITED"}, status_code=429),
        )
        app.add_middleware(SlowAPIMiddleware)

        @app.get("/ouvert")
        def ouvert() -> dict:
            return {"ok": True}

        return TestClient(app)

    return build


def _from(client: TestClient, header: str, value: str | None, count: int) -> list[int]:
    headers = {header: value} if value is not None else {}
    return [client.get("/ouvert", headers=headers).status_code for _ in range(count)]


def test_sans_configuration_l_en_tete_est_ignore_et_ne_fabrique_aucun_quota(ip_client) -> None:
    """Défaut sûr : un client qui invente des adresses ne multiplie pas son quota."""
    client = ip_client("")

    assert _from(client, "X-Real-IP", "198.51.100.1", LIMIT) == [200] * LIMIT
    assert _from(client, "X-Real-IP", "198.51.100.2", 1) == [429]


def test_configure_chaque_adresse_reelle_a_son_propre_quota(ip_client) -> None:
    client = ip_client("X-Real-IP")
    _from(client, "X-Real-IP", "198.51.100.1", LIMIT)

    assert _from(client, "X-Real-IP", "198.51.100.1", 1) == [429]
    assert _from(client, "X-Real-IP", "198.51.100.2", LIMIT) == [200] * LIMIT


@pytest.mark.parametrize("value", ["pas-une-adresse", "198.51.100.1, 203.0.113.9", "", "999.1.1.1"])
def test_une_valeur_invalide_retombe_sur_la_connexion(ip_client, value) -> None:
    client = ip_client("X-Real-IP")

    # Toutes ces valeurs partagent le quota de la connexion : aucune n'en ouvre un neuf.
    assert _from(client, "X-Real-IP", value, LIMIT) == [200] * LIMIT
    assert _from(client, "X-Real-IP", "also-bad", 1) == [429]


def test_sans_l_en_tete_configure_repli_sur_la_connexion(ip_client) -> None:
    client = ip_client("X-Real-IP")

    assert _from(client, "X-Real-IP", None, LIMIT) == [200] * LIMIT
    assert _from(client, "X-Real-IP", None, 1) == [429]


def test_une_adresse_ipv6_valide_est_acceptee(ip_client) -> None:
    client = ip_client("X-Real-IP")

    assert _from(client, "X-Real-IP", "2001:db8::1", LIMIT) == [200] * LIMIT
    assert _from(client, "X-Real-IP", "2001:db8::2", LIMIT) == [200] * LIMIT
