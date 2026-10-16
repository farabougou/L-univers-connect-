"""Catalogue des connecteurs (V4, ADR 012 §2.12) : voir
app/connectors/catalog.py pour le détail du contrat et des niveaux de
certification. Gestion d'équipement, même tiers de rôle que GET /devices.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.engine import Connection

from app.auth import require_any_role
from app.connectors.catalog import list_connectors
from app.deps import get_tenant_connection

router = APIRouter()

_MANAGE_ROLES = ("responsable_exploitation", "admin_tenant")


class ConnectorOut(BaseModel):
    protocol: str
    display_name: str
    schema_version: str
    capabilities: list[Literal["read", "discover", "subscribe"]]
    write_enabled: Literal[False]
    certification_level: Literal["experimental", "verified", "certified"]
    certification_basis: str
    module: str
    daemon_script: str
    device_mapping_config_type: str
    active_equipment_count: int


@router.get("/connectors", response_model=list[ConnectorOut])
def list_connectors_route(
    connection: Annotated[Connection, Depends(get_tenant_connection)],
    _claims: Annotated[dict, Depends(require_any_role(*_MANAGE_ROLES))],
) -> list[ConnectorOut]:
    return [ConnectorOut(**entry) for entry in list_connectors(connection)]
