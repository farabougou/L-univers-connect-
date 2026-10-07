"""Logs structurés (ADR 012, étape F6).

Un log sert à diagnostiquer, jamais à tracer des personnes : identifiant de
requête et tenant oui ; jeton, identifiant de l'utilisateur, chemin brut
(qui contient des codes d'étiquette), paramètres et messages d'erreur non.
"""

import json
import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import JsonFormatter
from tests.jwt_helpers import DEMO_TENANT_ID, JWKS, make_token

client = TestClient(app)
TAG_CODE = "CodeEtiquetteTest123"
USER_SUB = "utilisateur-a-ne-pas-journaliser"


def _lines(caplog) -> list[dict]:
    formatter = JsonFormatter()
    return [json.loads(formatter.format(record)) for record in caplog.records]


def _request_line(caplog) -> dict:
    lines = [line for line in _lines(caplog) if line.get("event") == "http.request"]
    assert len(lines) == 1
    return lines[0]


def _scan(headers: dict | None = None):
    token = make_token(sub=USER_SUB)
    with patch("app.auth.fetch_jwks", return_value=JWKS):
        return client.get(
            f"/tags/{TAG_CODE}?origine=test",
            headers={"Authorization": f"Bearer {token}", **(headers or {})},
        )


def test_each_response_carries_a_request_id() -> None:
    first = client.get("/health")
    second = client.get("/health")

    assert first.headers["X-Request-ID"]
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_a_valid_incoming_request_id_is_kept() -> None:
    response = client.get("/health", headers={"X-Request-ID": "edge-site42-000123"})

    assert response.headers["X-Request-ID"] == "edge-site42-000123"


@pytest.mark.parametrize("unsafe", ["a" * 200, "id avec espace", "<script>", ""])
def test_an_unsafe_incoming_request_id_is_replaced(unsafe) -> None:
    response = client.get("/health", headers={"X-Request-ID": unsafe})

    assert response.headers["X-Request-ID"] != unsafe


def test_request_log_is_json_with_request_id_tenant_route_status_and_duration(caplog) -> None:
    caplog.set_level(logging.INFO, logger="paios")

    response = _scan()

    line = _request_line(caplog)
    assert response.status_code == 404
    assert line["level"] == "INFO"
    assert line["request_id"] == response.headers["X-Request-ID"]
    assert line["tenant_id"] == DEMO_TENANT_ID
    assert line["method"] == "GET"
    assert line["route"] == "/tags/{code}"
    assert line["status"] == 404
    assert isinstance(line["duration_ms"], float)
    assert line["timestamp"].endswith("Z")


def test_request_log_contains_no_token_user_code_or_query(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="paios")
    token = make_token(sub=USER_SUB)

    _scan()

    text = caplog.text + json.dumps(_lines(caplog))
    for forbidden in (token, USER_SUB, TAG_CODE, "origine=test", "Bearer"):
        assert forbidden not in text


def test_unauthenticated_request_is_logged_without_tenant(caplog) -> None:
    caplog.set_level(logging.INFO, logger="paios")

    response = client.get("/me")

    line = _request_line(caplog)
    assert response.status_code == 401
    assert line["tenant_id"] is None
    assert line["route"] == "/me"


def test_unknown_route_is_logged_without_the_raw_path(caplog) -> None:
    caplog.set_level(logging.INFO, logger="paios")

    client.get(f"/chemin-inconnu/{TAG_CODE}")

    line = _request_line(caplog)
    assert line["route"] is None
    assert TAG_CODE not in json.dumps(line)


def test_unhandled_error_logs_type_and_frames_but_not_the_message(caplog) -> None:
    caplog.set_level(logging.INFO, logger="paios")
    secret_detail = "numéro de série SN-CONFIDENTIEL"

    with patch("app.routers.passport.resolve_tag", side_effect=RuntimeError(secret_detail)):
        response = _scan()

    errors = [line for line in _lines(caplog) if line.get("event") == "http.unhandled_error"]
    assert response.status_code == 500
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert len(errors) == 1
    assert errors[0]["level"] == "ERROR"
    assert errors[0]["error_type"] == "RuntimeError"
    assert any("passport.py" in frame for frame in errors[0]["frames"])
    assert _request_line(caplog)["status"] == 500
    assert secret_detail not in caplog.text + json.dumps(_lines(caplog))
    assert secret_detail not in response.text


def test_formatter_drops_arbitrary_extra_fields() -> None:
    record = logging.LogRecord("paios.test", logging.INFO, __file__, 1, "message", None, None)
    record.email = "personne@exemple.test"

    line = json.loads(JsonFormatter().format(record))

    assert "email" not in line
    assert line["message"] == "message"
