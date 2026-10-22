"""Essai anti-usurpation de `CLIENT_IP_HEADER` (scripts/spoof_test.py).

Deux niveaux de preuve :
- le verdict (`judge`) est une fonction pure, testée sur chaque forme de résultat ;
- l'essai complet tourne contre la vraie application et son vrai limiteur, avec un proxy
  qui écrase l'en-tête (cas sain) et sans proxy (cas dangereux : le client choisit son
  adresse). Si l'essai ne distinguait pas ces deux cas, il ne prouverait rien sur Railway.

Première utilisation réelle (staging, 22/10/2026) : la limite de 10 par minute n'était pas
observable (60 envois depuis la même adresse, aucun 429). L'ancienne version concluait alors
« usurpable » à tort. La phase témoin existe pour que ce cas donne « non concluant ».
"""

import json

import httpx
import pytest
from starlette.testclient import TestClient

import scripts.spoof_test as spoof
from app.config import settings
from app.main import app

SHARED_ADDRESS = "203.0.113.9"

# Une phase témoin saine : 10 refus d'identité (401) puis le quota atteint (429).
TEMOIN = [401] * 10 + [429] * 2
TOUT_REFUSE = [429] * 12
TOUT_PASSE = [401] * 12


def _pose_l_adresse_du_proxy(client: TestClient) -> None:
    """Ce que fait un proxy qui écrase `X-Real-IP` : quelle que soit la valeur envoyée par le
    client, l'application reçoit l'adresse réelle du client."""
    client.event_hooks["request"] = [
        lambda request: request.headers.__setitem__("X-Real-IP", SHARED_ADDRESS)
    ]


# --- Le verdict ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("control", "varied", "verdict"),
    [
        (TEMOIN, TOUT_REFUSE, spoof.NOT_SPOOFABLE),
        (TEMOIN, TOUT_PASSE, spoof.SPOOFABLE),
        ([401] * 10 + [429, 429], [404] * 12, spoof.SPOOFABLE),
        # Cas relevé sur le staging : la limite n'est pas observable, rien ne se conclut.
        (TOUT_PASSE, TOUT_PASSE, spoof.INCONCLUSIVE),
        (TOUT_PASSE, TOUT_REFUSE, spoof.INCONCLUSIVE),
        ([401] * 5 + [429] * 7, TOUT_REFUSE, spoof.INCONCLUSIVE),  # quota déjà entamé
        ([401] * 11 + [429], TOUT_REFUSE, spoof.INCONCLUSIVE),  # limite trop tardive
        ([401] * 10 + [429, 401], TOUT_REFUSE, spoof.INCONCLUSIVE),  # limitation irrégulière
        (TEMOIN, [401] * 6 + [429] * 6, spoof.INCONCLUSIVE),  # ni tous ni aucun
        (TEMOIN + [429], TOUT_REFUSE, spoof.INCONCLUSIVE),  # nombre d'envois incorrect
        ([401] * 11 + [None], TOUT_PASSE, spoof.INCONCLUSIVE),
        (TEMOIN, [401] * 11 + [503], spoof.INCONCLUSIVE),
        (TEMOIN, [200] * 12, spoof.INCONCLUSIVE),  # réponse que l'essai ne sait pas lire
        (TEMOIN, [422] * 12, spoof.INCONCLUSIVE),  # corps refusé avant le limiteur
    ],
)
def test_le_verdict_par_forme_de_resultat(control, varied, verdict) -> None:
    assert spoof.judge(control, varied)[0] == verdict


def test_sans_phase_temoin_valide_aucun_verdict_ferme_n_est_donne() -> None:
    """Ni « sain » ni « usurpable » ne doivent sortir quand le témoin est invalide : c'est la
    leçon du staging, où l'ancienne version a conclu à tort."""
    invalides = ([401] * 12, [429] * 12, [None] * 12, [500] * 12, [401] * 5 + [429] * 7)
    for control in invalides:
        for varied in (TOUT_PASSE, TOUT_REFUSE):
            verdict = spoof.judge(control, varied)[0]
            assert verdict == spoof.INCONCLUSIVE, (control, varied)


# --- L'essai complet contre la vraie application -------------------------------------------


def test_sans_proxy_l_en_tete_du_client_est_cru_et_l_essai_le_signale(monkeypatch) -> None:
    monkeypatch.setattr(settings, "client_ip_header", "X-Real-IP")

    with TestClient(app) as client:
        control, varied = spoof.run_probe(client)

    assert control[:10] == [401] * 10
    assert control[10:] == [429, 429]
    assert 429 not in varied
    assert spoof.judge(control, varied)[0] == spoof.SPOOFABLE


def test_un_proxy_qui_ecrase_l_en_tete_donne_un_quota_partage(monkeypatch) -> None:
    monkeypatch.setattr(settings, "client_ip_header", "X-Real-IP")

    with TestClient(app) as client:
        _pose_l_adresse_du_proxy(client)
        control, varied = spoof.run_probe(client)

    assert control[10:] == [429, 429]
    assert varied == TOUT_REFUSE
    assert spoof.judge(control, varied)[0] == spoof.NOT_SPOOFABLE


def test_reglage_vide_l_essai_ne_distingue_rien_et_la_preuve_le_dit(monkeypatch) -> None:
    """Sans `CLIENT_IP_HEADER`, tout le monde partage l'adresse de la connexion : verdict
    sain quel que soit le proxy. C'est pourquoi la preuve porte une réserve explicite."""
    monkeypatch.setattr(settings, "client_ip_header", "")

    with TestClient(app) as client:
        control, varied = spoof.run_probe(client)
    proof = spoof.build_proof(
        "https://api.example.invalid", control, varied, *spoof.judge(control, varied)
    )

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
        transport=_serveur(TEMOIN + TOUT_REFUSE),
    )

    assert code == 0
    preuve = json.loads(sortie.read_text(encoding="utf-8"))
    assert preuve["verdict"] == spoof.NOT_SPOOFABLE
    assert preuve["cible"] == "api.example.invalid"
    assert preuve["codes_phase_temoin"] == TEMOIN
    assert preuve["codes_phase_usurpation"] == TOUT_REFUSE
    assert "secret-bidon" not in sortie.read_text(encoding="utf-8")
    assert "secret-bidon" not in capsys.readouterr().out


def test_la_commande_sort_en_1_et_ordonne_de_retirer_le_reglage_si_usurpable(capsys) -> None:
    code = spoof.main(
        ["--api-url", "https://api.example.invalid", "--allow-remote"],
        transport=_serveur(TEMOIN + TOUT_PASSE),
    )

    assert code == 1
    assert "remettre CLIENT_IP_HEADER à vide" in capsys.readouterr().err


def test_la_commande_sort_en_3_si_la_limite_n_est_pas_observable(capsys) -> None:
    """Le cas du staging le 22/10/2026 : 24 envois, aucun refus. Surtout pas de panique
    « usurpable » : le verdict est non concluant et ne demande aucune action immédiate."""
    code = spoof.main(
        ["--api-url", "https://api.example.invalid", "--allow-remote"],
        transport=_serveur(TOUT_PASSE + TOUT_PASSE),
    )

    assert code == 3
    assert "ACTION IMMÉDIATE" not in capsys.readouterr().err
