"""Logs structurés (ADR 012, étape F6).

Une ligne JSON par événement, sur la sortie standard : l'hébergeur (Railway
aujourd'hui, un autre demain) les collecte sans rien changer au code.

Chaque ligne porte l'identifiant de la requête et le tenant, pour suivre une
panne d'un bout à l'autre. Ce qui n'y figure jamais : le jeton, l'identifiant
de la personne, le chemin brut (il contient des codes d'étiquette et des
identifiants), les paramètres de la requête, le message d'une erreur (il peut
contenir des valeurs métier). Le formateur ne publie que des champs connus :
un champ ajouté par erreur à un log est ignoré, pas diffusé.
"""

import contextvars
import json
import logging
import re
import sys
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
# Un identifiant reçu (Edge, application) est gardé s'il est court et sans
# caractère spécial ; sinon on en crée un : un en-tête ne doit pas pouvoir
# injecter du texte dans les logs.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# Seuls champs publiés en plus du socle (horodatage, niveau, logger, message).
EVENT_FIELDS = (
    "event",
    "method",
    "route",
    "status",
    "duration_ms",
    "error_type",
    "frames",
)

logger = logging.getLogger("paios.http")


@dataclass
class RequestContext:
    """Objet partagé : la dépendance d'authentification y inscrit le tenant,
    le middleware le relit (les dépendances synchrones tournent dans un autre
    fil d'exécution, avec une copie du contexte mais le même objet)."""

    request_id: str
    tenant_id: str | None = None


_current: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar(
    "paios_request_context", default=None
)


def current_request_id() -> str | None:
    context = _current.get()
    return context.request_id if context else None


def set_tenant(tenant_id: uuid.UUID) -> None:
    context = _current.get()
    if context is not None:
        context.tenant_id = str(tenant_id)


def _install_record_factory() -> None:
    """Fige la requête et le tenant sur chaque événement au moment où il se
    produit, et non au moment où la ligne est écrite (qui peut être plus tard,
    dans un autre fil d'exécution)."""
    previous = logging.getLogRecordFactory()
    if getattr(previous, "_paios", False):
        return

    def factory(*args, **kwargs) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        context = _current.get()
        record.request_id = context.request_id if context else None
        record.tenant_id = context.tenant_id if context else None
        return record

    factory._paios = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "tenant_id": getattr(record, "tenant_id", None),
        }
        for field in EVENT_FIELDS:
            if hasattr(record, field):
                line[field] = getattr(record, field)
        return json.dumps(line, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Idempotent : peut être appelé plusieurs fois (tests, rechargement)."""
    _install_record_factory()
    root = logging.getLogger("paios")
    root.setLevel(level.upper())
    if not any(getattr(h, "_paios", False) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler._paios = True  # type: ignore[attr-defined]
        root.addHandler(handler)


def _frames(exc: BaseException) -> list[str]:
    """Où l'erreur s'est produite (fichier, ligne, fonction), sans son texte."""
    return [
        f"{frame.filename.rsplit('/', 1)[-1]}:{frame.lineno} {frame.name}"
        for frame in traceback.extract_tb(exc.__traceback__)
    ][-15:]


def _route_template(request: Request) -> str | None:
    route = request.scope.get("route")
    return getattr(route, "path", None)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        context = RequestContext(request_id=request_id)
        token = _current.set(context)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                # Le détail reste côté serveur (type et emplacement) ; la
                # personne reçoit l'identifiant à transmettre au support.
                logger.error(
                    "erreur non gérée",
                    extra={
                        "event": "http.unhandled_error",
                        "error_type": type(exc).__name__,
                        "frames": _frames(exc),
                        "route": _route_template(request),
                    },
                )
                # Import tardif : le module des erreurs dépend de celui-ci.
                from app.errors import problem_response

                response = problem_response(
                    request,
                    status=500,
                    code="INTERNAL_ERROR",
                    params={"request_id": request_id},
                    request_id=request_id,
                )
            response.headers[REQUEST_ID_HEADER] = request_id
            logger.info(
                "requête traitée",
                extra={
                    "event": "http.request",
                    "method": request.method,
                    "route": _route_template(request),
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return response
        finally:
            _current.reset(token)
