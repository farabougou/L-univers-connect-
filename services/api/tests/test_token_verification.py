"""Vérification des jetons après le remplacement de python-jose par PyJWT (21/10/2026).

La table ci-dessous est celle du banc de comparaison exécuté avant la migration : mêmes
jetons, forgés à la main, soumis à l'ancien code (python-jose 3.5.0) et au nouveau.
45 décisions sur 49 étaient identiques ; les 4 autres sont des durcissements voulus, repérés
ici par « durcissement » : jeton sans `exp` (il n'expirerait jamais) et clé désignée par un
`kid` qui n'est pas une clé de signature du JWKS.

Point de sécurité à ne pas « corriger » sans décision : les jetons réels de Keycloak n'ont
aucune revendication `aud` (constaté sur le staging, `azp` = paios-api). L'audience n'est donc
contrôlée que si elle est présente, comme avant ; exiger `aud` mettrait toute l'authentification
en échec. Voir docs/security/registre-vulnerabilites.md, « Audience »."""

import base64
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.exceptions import PyJWTError

from app import auth, devices
from app.config import settings
from app.errors import ApiError
from tests.jwt_helpers import JWKS, KEY_ID, PRIVATE_KEY_PEM, make_token

NOW = int(time.time())
GOOD = {
    "sub": "u1",
    "iss": settings.oidc_issuer,
    "aud": settings.oidc_audience,
    "iat": NOW,
    "exp": NOW + 300,
    "realm_access": {"roles": ["technicien"]},
    "tenant_id": "11111111-1111-1111-1111-111111111111",
}


def _without(claims: dict, *names: str) -> dict:
    return {key: value for key, value in claims.items() if key not in names}


def _sign(claims: dict, *, key=PRIVATE_KEY_PEM, headers: dict | None = None) -> str:
    return jwt.encode(claims, key, algorithm="RS256", headers=headers or {"kid": KEY_ID})


# --- Flux humain (OIDC, RS256) ---------------------------------------------------------

ACCEPTED = {
    "jeton valide": GOOD,
    "audience absente (Keycloak réel)": _without(GOOD, "aud"),
    "audience en liste, la nôtre dedans": {**GOOD, "aud": ["account", settings.oidc_audience]},
    "nbf déjà passé": {**GOOD, "nbf": NOW - 60},
    "iat dans le futur (écart d'horloge entre machines)": {**GOOD, "iat": NOW + 120},
    "iat décimal": {**GOOD, "iat": float(NOW) + 0.5},
}

REFUSED = {
    "expiré": {**GOOD, "exp": NOW - 10},
    "exp absent (durcissement)": _without(GOOD, "exp"),
    "audience présente mais autre": {**GOOD, "aud": "autre-client"},
    "audience en liste sans la nôtre": {**GOOD, "aud": ["account"]},
    "audience ni texte ni liste de textes": {**GOOD, "aud": 12},
    "émetteur autre": {**GOOD, "iss": "https://autre.example/realms/paios"},
    "émetteur absent": _without(GOOD, "iss"),
    "nbf dans le futur": {**GOOD, "nbf": NOW + 3600},
    "iat texte": {**GOOD, "iat": "hier"},
    "iat nul": {**GOOD, "iat": None},
}


@pytest.mark.parametrize("claims", list(ACCEPTED.values()), ids=list(ACCEPTED))
def test_jetons_oidc_acceptes(claims) -> None:
    decoded = auth._verify_oidc_token(_sign(claims), JWKS)

    assert decoded["sub"] == "u1"


@pytest.mark.parametrize("claims", list(REFUSED.values()), ids=list(REFUSED))
def test_jetons_oidc_refuses(claims) -> None:
    with pytest.raises(PyJWTError):
        auth._verify_oidc_token(_sign(claims), JWKS)


def test_un_jeton_signe_par_une_autre_cle_est_refuse() -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = other.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    with pytest.raises(PyJWTError):
        auth._verify_oidc_token(_sign(GOOD, key=pem), JWKS)


def test_un_algorithme_non_autorise_est_refuse_meme_avec_la_bonne_cle() -> None:
    rs512 = jwt.encode(GOOD, PRIVATE_KEY_PEM, algorithm="RS512", headers={"kid": KEY_ID})

    with pytest.raises(PyJWTError):
        auth._verify_oidc_token(rs512, JWKS)


@pytest.mark.parametrize("garbage", ["", "a.b", "n.importe.quoi", "a.b.c.d", "   "])
def test_des_jetons_malformes_sont_refuses_sans_exception_inattendue(garbage) -> None:
    with pytest.raises(PyJWTError):
        auth._verify_oidc_token(garbage, JWKS)


# --- Choix de la clé dans le JWKS -----------------------------------------------------


def _jwks_with_encryption_key() -> dict:
    enc = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    enc_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(enc.public_key(), as_dict=True)
    enc_jwk.update({"kid": "enc1", "use": "enc", "alg": "RSA-OAEP"})
    return {"keys": [enc_jwk, *JWKS["keys"]]}


def test_la_cle_de_chiffrement_du_jwks_est_ignoree_et_la_cle_de_signature_trouvee() -> None:
    """Keycloak publie aussi une clé `RSA-OAEP` (use: enc) dans son JWKS."""
    decoded = auth._verify_oidc_token(_sign(GOOD), _jwks_with_encryption_key())

    assert decoded["sub"] == "u1"


def test_un_kid_inconnu_est_refuse_durcissement() -> None:
    with pytest.raises(PyJWTError):
        auth._verify_oidc_token(_sign(GOOD, headers={"kid": "inconnu"}), JWKS)


def test_un_kid_qui_designe_une_cle_de_chiffrement_est_refuse_durcissement() -> None:
    with pytest.raises(PyJWTError):
        auth._verify_oidc_token(_sign(GOOD, headers={"kid": "enc1"}), _jwks_with_encryption_key())


def test_sans_kid_toutes_les_cles_de_signature_sont_essayees() -> None:
    decoded = auth._verify_oidc_token(_sign(GOOD, headers={}), _jwks_with_encryption_key())

    assert decoded["sub"] == "u1"


@pytest.mark.parametrize("jwks", [{"keys": []}, {}, {"keys": None}, {"keys": [{"kty": "oct"}]}])
def test_un_jwks_inutilisable_refuse_tout(jwks) -> None:
    with pytest.raises(PyJWTError):
        auth._verify_oidc_token(_sign(GOOD), jwks)


# --- Correspondance avec les erreurs de l'API ---------------------------------------------


def test_decode_token_traduit_chaque_refus_en_401_token_invalid(monkeypatch) -> None:
    monkeypatch.setattr(auth, "fetch_jwks", lambda: JWKS)

    for claims in REFUSED.values():
        with pytest.raises(ApiError) as excinfo:
            auth.decode_token(_sign(claims))
        assert excinfo.value.status == 401


def test_decode_token_with_cached_keys_ne_leve_jamais_d_exception(monkeypatch) -> None:
    """Il s'exécute dans le middleware de limitation de débit : une 500 y serait pire qu'un
    repli sur l'adresse IP."""
    for cache in (None, JWKS, {"keys": None}, {"keys": [{"kty": "oct"}]}, {}, "pas-un-jwks"):
        monkeypatch.setitem(auth._jwks_cache, "keys", cache)
        for token in (_sign(GOOD), "", "a.b.c", _sign(REFUSED["expiré"])):
            result = auth.decode_token_with_cached_keys(token)
            assert result is None or result["sub"] == "u1"


def test_decode_token_with_cached_keys_accepte_un_jeton_valide(monkeypatch) -> None:
    monkeypatch.setitem(auth._jwks_cache, "keys", JWKS)

    assert auth.decode_token_with_cached_keys(make_token())["sub"] == "technicien-test"


# --- Jetons d'appareil (HS256, secret local) ---------------------------------------------

DEVICE = {
    "device_id": "d1",
    "tenant_id": "t1",
    "site_id": None,
    "scopes": ["telemetry:write"],
    "iat": NOW,
    "exp": NOW + 900,
}


def _device_token(claims: dict, secret: str | None = None) -> str:
    return jwt.encode(claims, secret or settings.device_token_secret, algorithm="HS256")


def test_un_jeton_d_appareil_valide_est_accepte() -> None:
    assert auth.decode_device_token(_device_token(DEVICE))["device_id"] == "d1"


@pytest.mark.parametrize(
    "claims",
    [
        {**DEVICE, "exp": NOW - 5},
        _without(DEVICE, "exp"),
        {**DEVICE, "iat": "hier"},
        {**DEVICE, "nbf": NOW + 3600},
    ],
    ids=["expiré", "exp absent (durcissement)", "iat texte", "nbf futur"],
)
def test_jetons_d_appareil_refuses(claims) -> None:
    with pytest.raises(ApiError) as excinfo:
        auth.decode_device_token(_device_token(claims))

    assert excinfo.value.status == 401 and excinfo.value.code == "DEVICE_TOKEN_INVALID"


def test_un_jeton_d_appareil_avec_un_autre_secret_est_refuse() -> None:
    with pytest.raises(ApiError):
        auth.decode_device_token(_device_token(DEVICE, secret="x" * 40))


def test_l_emission_et_la_lecture_d_un_jeton_d_appareil_font_l_aller_retour() -> None:
    import uuid

    device_id, tenant_id = uuid.uuid4(), uuid.uuid4()
    token = auth.issue_device_token(
        device_id=device_id, tenant_id=tenant_id, site_id=None, scopes=["telemetry:write"]
    )

    claims = auth.decode_device_token(token)

    assert claims["device_id"] == str(device_id) and claims["scopes"] == ["telemetry:write"]
    assert claims["exp"] - claims["iat"] == 15 * 60, "durée de vie inchangée : 15 minutes"


# --- Preuves d'appareil (ES256, clé publique enregistrée) ---------------------------------


def _ec_pair() -> tuple[str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private, public


PRIVATE, PUBLIC = _ec_pair()
OTHER_PRIVATE, _ = _ec_pair()
ASSERTION = {"device_id": "d1", "tenant_id": "t1", "jti": "j1", "iat": NOW, "exp": NOW + 60}


def _assertion(claims: dict = ASSERTION, key: str = PRIVATE) -> str:
    return jwt.encode(claims, key, algorithm=devices.ASSERTION_ALGORITHM)


def test_une_preuve_signee_par_la_cle_enregistree_est_acceptee() -> None:
    assert devices._decode_assertion(_assertion(), PUBLIC)["jti"] == "j1"


def test_une_preuve_signee_par_une_autre_cle_est_refusee() -> None:
    with pytest.raises(PyJWTError):
        devices._decode_assertion(_assertion(key=OTHER_PRIVATE), PUBLIC)


@pytest.mark.parametrize(
    "claims",
    [{**ASSERTION, "exp": NOW - 500}, {**ASSERTION, "iat": NOW + 9999}],
    ids=["expirée", "iat futur"],
)
def test_les_dates_d_une_preuve_ne_sont_pas_jugees_ici(claims) -> None:
    """Elles le sont par `authenticate_device_by_assertion`, contre `at` et non contre
    l'horloge du serveur (voir tests/test_devices.py)."""
    assert devices._decode_assertion(_assertion(claims), PUBLIC)["jti"] == "j1"


def test_nbf_futur_d_une_preuve_reste_refuse_comme_avant() -> None:
    with pytest.raises(PyJWTError):
        devices._decode_assertion(_assertion({**ASSERTION, "nbf": NOW + 9999}), PUBLIC)


def test_une_preuve_avec_une_audience_est_refusee() -> None:
    with pytest.raises(PyJWTError):
        devices._decode_assertion(_assertion({**ASSERTION, "aud": "x"}), PUBLIC)


def test_une_preuve_sans_signature_ou_en_hs256_avec_la_cle_publique_est_refusee() -> None:
    def part(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    unsigned = f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(ASSERTION)}."

    with pytest.raises(PyJWTError):
        devices._decode_assertion(unsigned, PUBLIC)
    with pytest.raises(PyJWTError):
        # PyJWT refuse déjà, à la signature, d'employer une clé publique comme secret HMAC
        devices._decode_assertion(jwt.encode(ASSERTION, PUBLIC, algorithm="HS256"), PUBLIC)
