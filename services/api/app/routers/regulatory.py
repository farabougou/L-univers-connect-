"""Adaptateurs réglementaires exposés en API (voir app/regulatory/ et
docs/regulatory/). Tâche de bureau (déclaration annuelle), pas un geste
terrain : réservé aux rôles de gestion, comme les documents d'équipement.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.engine import Connection

from app.audit import append_audit_entry
from app.auth import require_any_role
from app.deps import get_tenant_connection, get_tenant_id
from app.errors import ApiError, api_error
from app.regulatory.operat import (
    OperatDeclarationConflict,
    OperatDeclarationNotFound,
    OperatError,
    create_draft_declaration,
    export_operat_summary,
    get_declaration,
    list_declarations,
    list_portfolio_declarations,
    mark_ready,
    record_manual_submission,
    update_declaration,
)
from app.schemas import (
    OperatDeclarationCreate,
    OperatDeclarationOut,
    OperatDeclarationUpdate,
    OperatSubmissionCreate,
    OperatSummaryOut,
)

router = APIRouter()

_MANAGE_ROLES = ("responsable_exploitation", "admin_tenant")


def _actor(claims: dict) -> str:
    return claims.get("sub") or "inconnu"


@router.post(
    "/sites/{site_id}/operat-declarations",
    response_model=OperatDeclarationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_operat_declaration(
    site_id: uuid.UUID,
    body: OperatDeclarationCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> OperatDeclarationOut:
    try:
        declaration = create_draft_declaration(
            connection,
            tenant_id=tenant_id,
            site_id=site_id,
            reference_year=body.reference_year,
            created_by=_actor(claims),
        )
    except OperatDeclarationNotFound as exc:
        raise api_error(exc, 404) from exc
    except OperatDeclarationConflict as exc:
        raise api_error(exc, 409) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="operat_declaration.created",
        entity_type="operat_declaration",
        entity_id=str(declaration["id"]),
        payload={"site_id": str(site_id), "reference_year": body.reference_year},
    )
    return OperatDeclarationOut(**declaration)


@router.get("/sites/{site_id}/operat-declarations", response_model=list[OperatDeclarationOut])
def list_operat_declarations(
    site_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> list[OperatDeclarationOut]:
    return [OperatDeclarationOut(**row) for row in list_declarations(connection, site_id=site_id)]


@router.get("/operat-declarations/portfolio", response_model=list[OperatDeclarationOut])
def list_portfolio_operat_declarations(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> list[OperatDeclarationOut]:
    """Toutes les déclarations du portefeuille, tous sites confondus (page
    `/operat`) — déclaré avant `/operat-declarations/{declaration_id}` pour
    que « portfolio » ne soit jamais lu comme un identifiant."""
    return [OperatDeclarationOut(**row) for row in list_portfolio_declarations(connection)]


def _get_or_404(connection: Connection, declaration_id: uuid.UUID) -> dict:
    declaration = get_declaration(connection, declaration_id)
    if declaration is None:
        raise ApiError(404, "OPERAT_DECLARATION_NOT_FOUND")
    return declaration


@router.get("/operat-declarations/{declaration_id}", response_model=OperatDeclarationOut)
def read_operat_declaration(
    declaration_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> OperatDeclarationOut:
    return OperatDeclarationOut(**_get_or_404(connection, declaration_id))


@router.put("/operat-declarations/{declaration_id}", response_model=OperatDeclarationOut)
def update_operat_declaration(
    declaration_id: uuid.UUID,
    body: OperatDeclarationUpdate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> OperatDeclarationOut:
    try:
        declaration = update_declaration(
            connection,
            declaration_id=declaration_id,
            floor_area_m2=body.floor_area_m2,
            activity_category=body.activity_category,
            electricity_kwh=body.electricity_kwh,
            gas_kwh=body.gas_kwh,
            heat_network_kwh=body.heat_network_kwh,
            other_kwh=body.other_kwh,
            other_label=body.other_label,
            notes=body.notes,
            updated_by=_actor(claims),
            updated_at=datetime.now(UTC),
        )
    except OperatDeclarationNotFound as exc:
        raise api_error(exc, 404) from exc
    except OperatError as exc:
        raise api_error(exc, 400) from exc
    return OperatDeclarationOut(**declaration)


@router.post(
    "/operat-declarations/{declaration_id}/mark-ready", response_model=OperatDeclarationOut
)
def mark_operat_declaration_ready(
    declaration_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> OperatDeclarationOut:
    try:
        declaration = mark_ready(connection, declaration_id=declaration_id)
    except OperatDeclarationNotFound as exc:
        raise api_error(exc, 404) from exc
    except OperatError as exc:
        raise api_error(exc, 400) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="operat_declaration.marked_ready",
        entity_type="operat_declaration",
        entity_id=str(declaration_id),
        payload={},
    )
    return OperatDeclarationOut(**declaration)


@router.post(
    "/operat-declarations/{declaration_id}/submissions", response_model=OperatDeclarationOut
)
def record_operat_submission(
    declaration_id: uuid.UUID,
    body: OperatSubmissionCreate,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_id)],
    claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> OperatDeclarationOut:
    """Enregistre qu'une personne a transmis la déclaration sur le portail
    OPERAT — aucune transmission automatique (voir app.regulatory.operat)."""
    try:
        declaration = record_manual_submission(
            connection,
            declaration_id=declaration_id,
            submitted_by=_actor(claims),
            submitted_at=datetime.now(UTC),
            submission_reference=body.submission_reference,
        )
    except OperatDeclarationNotFound as exc:
        raise api_error(exc, 404) from exc
    except OperatError as exc:
        raise api_error(exc, 400) from exc
    append_audit_entry(
        connection,
        tenant_id=tenant_id,
        actor=_actor(claims),
        action="operat_declaration.submitted",
        entity_type="operat_declaration",
        entity_id=str(declaration_id),
        payload={"submission_reference": body.submission_reference},
    )
    return OperatDeclarationOut(**declaration)


@router.get("/operat-declarations/{declaration_id}/summary", response_model=OperatSummaryOut)
def read_operat_summary(
    declaration_id: uuid.UUID,
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> OperatSummaryOut:
    """Chiffres à saisir sur le portail OPERAT, dans l'ordre où il les
    demande (voir app.regulatory.operat.export_operat_summary)."""
    declaration = _get_or_404(connection, declaration_id)
    return OperatSummaryOut(**export_operat_summary(declaration))
