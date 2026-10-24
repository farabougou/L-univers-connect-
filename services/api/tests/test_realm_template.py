"""Le modèle de royaume Keycloak (`infra/keycloak/realm-staging.json`) porte le mapper d'audience.

Pourquoi : un compte créé à la main dans la console reçoit le rôle par défaut
`default-roles-<royaume>`, et Keycloak ajoute alors `aud: ["account"]` à son jeton. L'API refuse
un jeton dont l'audience ne contient pas `paios-api` (tests/test_token_verification.py) : sans
mapper, tout compte créé à la main est bloqué en 401 `TOKEN_INVALID` (constaté sur le staging le
24/10/2026). Le mapper ajoute `paios-api` à l'audience du jeton d'accès, avec ou sans rôle par
défaut.
"""

import json
from pathlib import Path

from app.config import settings

REALM_TEMPLATE = Path(__file__).resolve().parents[3] / "infra" / "keycloak" / "realm-staging.json"


def _paios_api_mappers() -> list[dict]:
    realm = json.loads(REALM_TEMPLATE.read_text(encoding="utf-8"))
    (client,) = [c for c in realm["clients"] if c["clientId"] == "paios-api"]
    return client["protocolMappers"]


def test_le_modele_de_royaume_ajoute_l_audience_de_l_api_au_jeton_d_acces() -> None:
    audience_mappers = [
        m for m in _paios_api_mappers() if m["protocolMapper"] == "oidc-audience-mapper"
    ]

    assert len(audience_mappers) == 1
    config = audience_mappers[0]["config"]
    assert config["included.client.audience"] == settings.oidc_audience
    assert config["access.token.claim"] == "true"
    assert config["id.token.claim"] == "false"


def test_le_modele_de_royaume_garde_le_mapper_du_client() -> None:
    names = [m["name"] for m in _paios_api_mappers()]

    assert "tenant_id" in names
