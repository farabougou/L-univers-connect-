"""Erreurs de l'API : codes stables, messages traduits, aucun détail technique
(ADR 013, étape L2).

Une erreur visible porte un code stable (sur lequel s'appuient les règles, les
clients et les tests), ses paramètres, l'identifiant de requête et un message
dans la langue demandée. Le message n'est jamais la source de vérité.
"""

import ast
import json
import re
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.errors import DomainError
from app.i18n import load_catalog, negotiate_locale
from app.main import app
from tests.jwt_helpers import JWKS, make_token

client = TestClient(app)
APP_DIR = Path(__file__).resolve().parents[1] / "app"
LOCALES = ("fr", "en")
_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")


def _get(path: str, *, token: bool = True, language: str | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {make_token(roles=['technicien'])}"
    if language:
        headers["Accept-Language"] = language
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.get(path, headers=headers)


# --- Format des réponses ------------------------------------------------


def test_domain_error_is_a_problem_details_response_in_french_by_default() -> None:
    response = _get(f"/graph/nodes/{uuid.uuid4()}/passport")

    body = response.json()
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["content-language"] == "fr"
    assert body["code"] == "NODE_NOT_FOUND"
    assert body["status"] == 404
    assert body["type"] == "urn:paios:error:NODE_NOT_FOUND"
    assert body["title"] == "Ressource introuvable"
    assert body["detail"] == "L’élément demandé est introuvable."
    assert body["params"] == {}
    assert body["request_id"] == response.headers["x-request-id"]


def test_accept_language_selects_english() -> None:
    response = _get(f"/graph/nodes/{uuid.uuid4()}/passport", language="en-GB,en;q=0.9")

    assert response.headers["content-language"] == "en"
    assert response.json()["detail"] == "The requested item could not be found."
    assert response.json()["code"] == "NODE_NOT_FOUND"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "fr"),
        ("", "fr"),
        ("en", "en"),
        ("en-US", "en"),
        ("de-DE,en;q=0.5", "en"),
        ("de-DE", "fr"),
        ("fr;q=0.2,en;q=0.8", "en"),
        ("en;q=0,fr", "fr"),
        ("n'importe quoi;;;", "fr"),
    ],
)
def test_language_negotiation(header, expected) -> None:
    assert negotiate_locale(header) == expected


def test_parameters_are_returned_and_inserted_in_the_message() -> None:
    response = _get("/measurements?point_id=" + str(uuid.uuid4()) + "&limit=5000")

    body = response.json()
    assert body["code"] == "QUERY_LIMIT_OUT_OF_RANGE"
    assert body["params"] == {"minimum": 1, "maximum": 1000}
    assert "1" in body["detail"] and "1000" in body["detail"]


def test_missing_token_has_a_stable_code() -> None:
    response = _get("/me", token=False)

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_MISSING"


def test_unknown_route_and_method() -> None:
    unknown = client.get("/adresse-inexistante")
    wrong_method = client.delete("/health")

    assert (unknown.status_code, unknown.json()["code"]) == (404, "ROUTE_NOT_FOUND")
    assert (wrong_method.status_code, wrong_method.json()["code"]) == (405, "METHOD_NOT_ALLOWED")


def test_validation_error_lists_fields_without_echoing_the_input() -> None:
    secret_like = "valeur avec espaces à ne pas renvoyer"
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        response = client.post(
            "/interventions",
            json={"client_ref": secret_like, "started_at": "2026-09-23T08:00:00Z"},
            headers={"Authorization": f"Bearer {make_token(roles=['technicien'])}"},
        )

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert {"field": "body.client_ref", "reason": "string_pattern_mismatch"} in body["errors"]
    assert secret_like not in response.text


def test_unhandled_error_is_a_problem_without_internal_detail() -> None:
    with patch("app.routers.passport.resolve_tag", side_effect=RuntimeError("SN-SECRET")):
        response = _get("/tags/CodeEtiquetteTest123")

    body = response.json()
    assert response.status_code == 500
    assert body["code"] == "INTERNAL_ERROR"
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["request_id"] in body["detail"]
    assert "SN-SECRET" not in response.text
    assert "RuntimeError" not in response.text


def test_domain_error_renders_french_for_logs_and_keeps_code() -> None:
    error = DomainError("LIFECYCLE_TRANSITION_FORBIDDEN", from_state="in_stock", to_state="x")

    assert error.code == "LIFECYCLE_TRANSITION_FORBIDDEN"
    assert error.params == {"from_state": "in_stock", "to_state": "x"}
    assert "in_stock" in str(error)


# --- Qualité des catalogues ------------------------------------------------


def test_catalogs_have_the_same_codes_and_placeholders() -> None:
    fr, en = (load_catalog(locale) for locale in LOCALES)

    assert fr["codes"].keys() == en["codes"].keys()
    assert fr["titles"].keys() == en["titles"].keys()
    for code, message in fr["codes"].items():
        assert set(_PLACEHOLDER.findall(message)) == set(_PLACEHOLDER.findall(en["codes"][code])), (
            code
        )


@pytest.mark.parametrize("locale", LOCALES)
def test_messages_are_complete_sentences_with_simple_placeholders(locale) -> None:
    for code, message in load_catalog(locale)["codes"].items():
        assert _CODE.match(code), code
        assert message[0].isupper(), code
        assert message.endswith("."), code
        for name in _PLACEHOLDER.findall(message):
            assert re.fullmatch(r"[a-z_]+", name), f"{code} : {{{name}}}"
        assert "  " not in message, code


def _strings(node, prefix=""):
    if isinstance(node, str):
        yield prefix, node
    else:
        for key, value in node.items():
            yield from _strings(value, f"{prefix}.{key}" if prefix else key)


@pytest.mark.parametrize("namespace", ["errors", "findings", "closure"])
def test_french_typography(namespace) -> None:
    """Apostrophe typographique, espace insécable avant « : ; ? ! » et à
    l'intérieur des guillemets français, dans tous les catalogues de l'API."""
    for key, message in _strings(load_catalog("fr", namespace)):
        assert "'" not in message, f"{key} : apostrophe droite"
        for mark in (":", ";", "?", "!"):
            assert f" {mark}" not in message, f"{key} : espace ordinaire avant {mark}"
        assert "« " not in message and " »" not in message, f"{key} : guillemets"
        for mark in (";", "?", "!"):
            index = message.find(mark)
            assert index <= 0 or message[index - 1] == "\u00a0", f"{key} : {mark}"


def _string_constants(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _codes_used_in_code() -> set[str]:
    used: set[str] = set()
    for path in APP_DIR.rglob("*.py"):
        used |= {value for value in _string_constants(path) if _CODE.match(value)}
    return used


def test_every_code_used_in_the_code_has_a_message_and_none_is_orphaned() -> None:
    error_codes = set(load_catalog("fr")["codes"])
    finding_codes = set(load_catalog("fr", "findings")["titles"])
    # Chaînes au même format qui ne sont pas des codes de message.
    used = _codes_used_in_code() - {"I18N_DIR"}

    assert used - error_codes - finding_codes == set(), "codes sans message"
    assert error_codes - used == set(), "messages d'erreur jamais utilisés"
    assert finding_codes - used == set(), "messages de constat jamais utilisés"


def test_finding_catalogs_are_consistent_and_typographically_correct() -> None:
    fr, en = (load_catalog(locale, "findings") for locale in LOCALES)
    for section in ("titles", "actions"):
        assert fr[section].keys() == en[section].keys() == fr["titles"].keys()
        for code, message in fr[section].items():
            assert set(_PLACEHOLDER.findall(message)) == set(
                _PLACEHOLDER.findall(en[section][code])
            ), code
            assert "'" not in message, f"{code} : apostrophe droite"
            assert " :" not in message, f"{code} : espace ordinaire avant les deux-points"
    for message in fr["actions"].values():
        assert message.endswith(".")


def test_no_http_exception_with_free_text_remains() -> None:
    offenders = [
        str(path.relative_to(APP_DIR))
        for path in APP_DIR.rglob("*.py")
        if "HTTPException(" in path.read_text()
    ]
    assert offenders == []


def test_catalog_files_are_valid_json_sorted_by_code() -> None:
    root = Path(__file__).resolve().parents[3] / "shared" / "i18n"
    for locale in LOCALES:
        data = json.loads((root / locale / "errors.json").read_text())
        assert list(data["codes"]) == sorted(data["codes"])
