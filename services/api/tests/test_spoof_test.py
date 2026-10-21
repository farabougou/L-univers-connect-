"""Essai anti-usurpation de `CLIENT_IP_HEADER` (scripts/spoof_test.py).

Deux niveaux de preuve :
- le verdict (`judge`) est une fonction pure, testée sur chaque forme de résultat ;
- l'essai complet tourne contre la vraie application et son vrai limiteur, avec un proxy
  qui écrase l'en-tête (cas sain) et sans proxy (cas dangereux : le client choisit son
  adresse). Si l'essai ne distinguait pas ces deux cas, il ne prouverait rien sur Railway.
"""

import json

import httpx
import pytest
from starlette.testclient import TestClient

import scripts.spoof_test as spoof
from app.config import settings
from app.main import app

SHARED_ADDRESS = "203.0.113.9"


def _pose_l_adresse_du_proxy(client: TestClient) -> None:
    """Ce que fait un proxy qui écrase `X-Real-IP` : quelle que soit la valeur envoyée par le
    client, l'application reçoit l'adresse réelle du client."""
    client.event_hooks["request"] = [
        lambda request: request.headers.__setitem__("X-Real-IP", SHARED_ADDRESS)
    ]


# --- Le verdict ----------------------------------------------------------------------------

REFUS_NORMAL = [401] * 10 + [429] * 2


@pytest.mark.parametrize(
    ("statuses", "verdict"),
    [
        (REFUS_NORMAL, spoof.NOT_SPOOFABLE),
        ([401] * 12, spoof.SPOOFABLE),
        ([404] * 12, spoof.SPOOFABLE),
        ([401] * 5 + [429] * 7, spoof.INCONCLUSIVE),  # quota déjà entamé
        ([401] * 11 + [429], spoof.INCONCLUSIVE),  # limite trop tardive : pas la nôtre
        ([401] * 10 + [429, 401], spoof.INCONCLUSIVE),  # limitation irrégulière
        ([401] * 11 + [503], spoof.INCONCLUSIVE),
        ([401] * 11 + [None], spoof.INCONCLUSIVE),
        ([401] * 11, spoof.INCONCLUSIVE),  # nombre d'envois incorrect
        ([200] * 12, spoof.INCONCLUSIVE),  # réponse que ce test ne sait pas interpréter
        ([422] * 12, spoof.INCONCLUSIVE),  # corps refusé avant le limiteur : rien ne prouve
    ],
)
def test_le_verdict_par_forme_de_resultat(statuses, verdict) -> None:
    assert spoof.judge(statuses)[0] == verdict


def test_un_verdict_sain_n_est_jamais_donne_pour_un_resultat_ambigu() -> None:
    for statuses in ([401] * 12, [429] * 12, [None] * 12, [500] * 12):
        assert spoof.judge(statuses)[0] != spoof.NOT_SPOOFABLE


# --- L'essai complet contre la vraie application -------------------------------------------


def test_sans_proxy_l_en_tete_du_client_est_cru_et_l_essai_le_signale(monkeypatch) -> None:
    monkeypatch.setattr(settings, "client_ip_header", "X-Real-IP")

    with TestClient(app) as client:
        statuses = spoof.run_probe(client)

    assert 429 not in statuses
    assert spoof.judge(statuses)[0] == spoof.SPOOFABLE


def test_un_proxy_qui_ecrase_l_en_tete_donne_un_quota_partage(monkeypatch) -> None:
    monkeypatch.setattr(settings, "client_ip_header", "X-Real-IP")

    with TestClient(app) as client:
        _pose_l_adresse_du_proxy(client)
        statuses = spoof.run_probe(client)

    assert statuses[:10] == [401] * 10
    assert statuses[10:] == [429, 429]
    assert spoof.judge(statuses)[0] == spoof.NOT_SPOOFABLE


def test_reglage_vide_l_essai_ne_distingue_rien_et_la_preuve_le_dit(monkeypatch) -> None:
    """Sans `CLIENT_IP_HEADER`, tout le monde partage l'adresse de la connexion : verdict
    sain quel que soit le proxy. C'est pourquoi la preuve porte une réserve explicite."""
    monkeypatch.setattr(settings, "client_ip_header", "")

    with TestClient(app) as client:
        statuses = spoof.run_probe(client)
    proof = spoof.build_proof("https://api.example.invalid", statuses, *spoof.judge(statuses))

    assert proof["verdict"] == spoof.NOT_SPOOFABLE
    assert "CLIENT_IP_HEADER=X-Real-IP était actif" in proof["reserve"]


# --- La commande -----------------------------------------------------------------------------


def _serveur(statuses: list[int]) -> httpx.MockTransport:
    reponses = iter(statuses)
    return httpx.MockTransport(lambda request: httpx.Response(next(reponses)))


def test_la_commande_refuse_une_cible_distante_sans_confirmation(capsys) -> None:
    code = spoof.main(["--api-url", "https://api.example.invalid"])

    assert code == 2
    assert "--allow-remote" in capsys.readouterr().err


def test_la_commande_ecrit_une_preuve_sans_secret_et_sort_en_0(tmp_path, capsys) -> None:
    sortie = tmp_path / "preuve.json"

    code = spoof.main(
        ["--api-url", "https://api.example.invalid", "--allow-remote", "--json-out", str(sortie)],
        transport=_serveur(REFUS_NORMAL),
    )

    assert code == 0
    preuve = json.loads(sortie.read_text(encoding="utf-8"))
    assert preuve["verdict"] == spoof.NOT_SPOOFABLE
    assert preuve["cible"] == "api.example.invalid"
    assert preuve["codes_de_reponse"] == REFUS_NORMAL
    assert "secret-bidon" not in sortie.read_text(encoding="utf-8")
    assert "secret-bidon" not in capsys.readouterr().out


def test_la_commande_sort_en_1_et_ordonne_de_retirer_le_reglage_si_usurpable(capsys) -> None:
    code = spoof.main(
        ["--api-url", "https://api.example.invalid", "--allow-remote"],
        transport=_serveur([401] * 12),
    )

    assert code == 1
    assert "remettre CLIENT_IP_HEADER à vide" in capsys.readouterr().err


def test_la_commande_sort_en_3_si_le_resultat_n_est_pas_concluant() -> None:
    code = spoof.main(
        ["--api-url", "https://api.example.invalid", "--allow-remote"],
        transport=_serveur([401] * 6 + [429] * 6),
    )

    assert code == 3
