"""Couverture de la limitation de débit par défaut (120 requêtes par minute et par personne).

Constat du 22/10/2026, relevé en mesurant le staging : environ 540 requêtes en moins d'une
minute sur `/sync/interventions` avec le même compte, aucun refus 429. Reproduit ici : seules les
routes définies directement sur l'application (`/me`) ou décorées explicitement
(`/devices/auth`) sont limitées. Les routes des sous-routeurs (`/sites`, `/points`, `/sync/*`...)
ne le sont pas.

Cause : FastAPI 0.141 range les routes d'un sous-routeur dans des objets internes
(`_IncludedRouter`) qui n'ont pas d'attribut `endpoint`. L'intergiciel de `slowapi` ne retrouve
donc pas la fonction de la route (`_find_route_handler` renvoie `None`) et ne contrôle rien,
sans erreur ni journal.

Ces tests documentent l'écart sans casser la CI : le test témoin (`/me`) doit passer, les tests
des sous-routeurs sont attendus en échec (`xfail` strict). Le jour où le mécanisme est corrigé,
le `xfail` strict fait échouer la CI et oblige à retirer la marque. Décision de correction :
Mohamed (politique de quota par route ou globale, voir infra/RAILWAY_STAGING.md).
"""

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.main import app
from tests.jwt_helpers import JWKS, make_token

QUOTA = 120
ATTEMPTS = QUOTA + 10


def _first_refusal(path: str) -> int | None:
    """Rang de la première réponse 429, ou None si les `ATTEMPTS` requêtes ont toutes passé."""
    token = make_token(roles=["technicien", "responsable_exploitation"])
    headers = {"Authorization": f"Bearer {token}"}
    with patch("app.auth.fetch_jwks", return_value=JWKS), TestClient(app) as client:
        for rank in range(1, ATTEMPTS + 1):
            if client.get(path, headers=headers).status_code == 429:
                return rank
    return None


def test_temoin_une_route_definie_sur_l_application_est_limitee() -> None:
    """Sans ce témoin, les tests suivants ne prouveraient rien : il vérifie que la mesure
    sait voir une limitation quand elle existe."""
    assert _first_refusal("/me") == QUOTA + 1


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Écart connu (22/10/2026) : slowapi ne retrouve pas les routes des sous-routeurs avec "
        "FastAPI 0.141 (_IncludedRouter sans attribut endpoint), donc aucun quota par défaut. "
        "En attente de la décision de correction."
    ),
)
@pytest.mark.parametrize("path", ["/sites", "/points", "/sync/interventions?limit=1"])
def test_une_route_de_sous_routeur_est_limitee(path: str) -> None:
    assert _first_refusal(path) == QUOTA + 1
