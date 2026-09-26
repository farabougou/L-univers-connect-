"""Erreurs de l'API : code stable + paramètres, jamais une phrase comme source
de vérité (ADR 013, étape L2).

- `DomainError` : levée par le code métier. Son texte français sert aux logs et
  au débogage ; ce qui compte est son `code` et ses `params`.
- `ApiError` : erreur destinée à la personne, avec son statut HTTP.
- Les réponses suivent le format « Problem Details » (RFC 9457), complété par
  `code`, `params` et `request_id`. Le message (`detail`) est traduit selon
  l'en-tête Accept-Language. Jamais de trace, d'exception interne ni de valeur
  saisie renvoyée telle quelle (point 13 de la directive).
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.i18n import negotiate_locale, render, title
from app.observability import current_request_id

PROBLEM_MEDIA_TYPE = "application/problem+json"


class DomainError(Exception):
    # Statut par défaut si aucune route ne précise le sien : 404 pour les
    # erreurs « introuvable », 409 pour les conflits (voir les sous-classes).
    status = 422

    # Code positionnel seulement : un paramètre du message peut lui-même
    # s'appeler « code » (code saisi, code d'espace…).
    def __init__(self, error_code: str, /, **params: Any) -> None:
        super().__init__(error_code)
        self.code = error_code
        self.params = params

    def __str__(self) -> str:
        return render(self.code, self.params)

    @classmethod
    def from_error(cls, error: "DomainError") -> "DomainError":
        """Même code et mêmes paramètres, sous le type d'erreur de l'appelant."""
        return cls(error.code, **error.params)


class ApiError(DomainError):
    def __init__(self, status: int, error_code: str, /, **params: Any) -> None:
        super().__init__(error_code, **params)
        self.status = status


def api_error(error: DomainError, status: int) -> ApiError:
    """Traduit une erreur métier en réponse, avec le statut choisi par la route."""
    return ApiError(status, error.code, **error.params)


def problem_response(
    request: Request,
    *,
    status: int,
    code: str,
    params: dict[str, Any] | None = None,
    request_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    locale = negotiate_locale(request.headers.get("accept-language"))
    params = jsonable_encoder(params or {})
    body = {
        "type": f"urn:paios:error:{code}",
        "title": title(status, locale),
        "status": status,
        "detail": render(code, params, locale),
        "code": code,
        "params": params,
        "request_id": request_id or current_request_id(),
        **(extra or {}),
    }
    return JSONResponse(
        status_code=status,
        content=body,
        media_type=PROBLEM_MEDIA_TYPE,
        headers={"Content-Language": locale},
    )


async def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return problem_response(request, status=exc.status, code=exc.code, params=exc.params)


async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Seuls l'emplacement du champ et le type d'erreur sont renvoyés : ni la
    # valeur saisie (elle peut contenir des données personnelles), ni le
    # message technique en anglais de la bibliothèque de validation.
    errors = [
        {"field": ".".join(str(part) for part in error["loc"]), "reason": error["type"]}
        for error in exc.errors()
    ]
    return problem_response(request, status=422, code="VALIDATION_ERROR", extra={"errors": errors})


_HTTP_CODES = {404: "ROUTE_NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}


async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    response = problem_response(
        request, status=exc.status_code, code=_HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
    )
    for name, value in (exc.headers or {}).items():
        response.headers[name] = value
    return response


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
