"""Couverture de la limitation de débit par défaut (120 requêtes par minute et par personne).

Constat du 22/10/2026, relevé en mesurant le staging : environ 540 requêtes en moins d'une
minute sur `/sync/interventions` avec le même compte, aucun refus 429. Cause : FastAPI 0.141
range les routes d'un sous-routeur dans des objets internes (`_IncludedRouter`) sans attribut
`endpoint`. L'intergiciel de `slowapi` ne retrouvait donc pas la fonction de la route
(`_find_route_handler` renvoyait `None`) et ne contrôlait rien, sans erreur ni journal : seules
`/me` (définie sur l'application) et les routes décorées étaient limitées.

Correction du 23/10/2026 (`app/rate_limit.py`, `find_route_handler`) : la fonction de la route
est retrouvée par l'aide publique de FastAPI (`iter_route_contexts`). Ces tests gardent le
résultat de deux façons :
- chaque route de l'application est retrouvée par l'intergiciel (aucune ne peut redevenir
  silencieusement exemptée lors d'une mise à jour de FastAPI ou de slowapi) ;
- des routes de plusieurs familles sont réellement refusées à la 121e requête.
"""

from unittest.mock import patch

import pytest
from fastapi.routing import iter_route_contexts
from starlette.testclient import TestClient

from app.main import app
from app.rate_limit import find_route_handler
from tests.jwt_helpers import JWKS, make_token

QUOTA = 120
ATTEMPTS = QUOTA + 10


def _first_refusal(path: str, attempts: int = ATTEMPTS) -> int | None:
    """Rang de la première réponse 429, ou None si les `attempts` requêtes ont toutes passé."""
    token = make_token(roles=["technicien", "responsable_exploitation"])
    headers = {"Authorization": f"Bearer {token}"}
    with patch("app.auth.fetch_jwks", return_value=JWKS), TestClient(app) as client:
        for rank in range(1, attempts + 1):
            if client.get(path, headers=headers).status_code == 429:
                return rank
    return None


def test_temoin_une_route_definie_sur_l_application_est_limitee() -> None:
    """Sans ce témoin, les tests suivants ne prouveraient rien : il vérifie que la mesure
    sait voir une limitation quand elle existe."""
    assert _first_refusal("/me") == QUOTA + 1


@pytest.mark.parametrize("path", ["/sites", "/points"])
def test_une_route_de_sous_routeur_est_limitee(path: str) -> None:
    assert _first_refusal(path) == QUOTA + 1


SYNC_QUOTA = 600


@pytest.mark.parametrize(
    "path", ["/sync/interventions?limit=1", "/sync/functional-locations?limit=1"]
)
def test_le_flux_de_synchronisation_a_son_propre_plafond_plus_large(path: str) -> None:
    """Le mobile pagine en masse au premier parcours et ne gère pas le refus 429 : le quota
    général (120) l'interromprait à 24 000 lignes. Le flux a donc un plafond dédié, qui borne
    toujours l'abus."""
    assert _first_refusal(path, attempts=SYNC_QUOTA + 5) == SYNC_QUOTA + 1


def _scope(path: str, method: str) -> dict:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "root_path": "",
        "headers": [],
        "query_string": b"",
        "app": app,
    }


def test_chaque_route_de_l_application_est_retrouvee_par_l_intergiciel() -> None:
    """Une route non retrouvée est exemptée en silence (c'est le défaut du 22/10/2026) : ce
    parcours de toutes les routes fait échouer la CI si une mise à jour de FastAPI ou de slowapi
    en fait de nouveau disparaître."""
    contexts = [c for c in iter_route_contexts(app.routes) if c.endpoint and c.path_format]
    assert len(contexts) > 100, "le parcours ne voit presque aucune route : l'aide a changé"

    inconnues = []
    for context in contexts:
        # Paramètres de chemin remplacés par une valeur acceptée par n'importe quel convertisseur.
        path = context.path_format
        for name in context.param_convertors:
            path = path.replace("{" + name + "}", "1")
        for method in sorted(context.methods or ()):
            if find_route_handler(app, _scope(path, method)) is not context.endpoint:
                inconnues.append(f"{method} {context.path_format}")

    assert not inconnues, f"routes non retrouvées par la limitation de débit : {inconnues}"


def test_un_chemin_inconnu_n_a_pas_de_route_a_limiter() -> None:
    assert find_route_handler(app, _scope("/cette/route/n/existe/pas", "GET")) is None
