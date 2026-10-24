"""Essai anti-usurpation de l'adresse du client (en-tête `CLIENT_IP_HEADER`).

À lancer APRÈS avoir renseigné `CLIENT_IP_HEADER=X-Real-IP` sur le service API et l'avoir
redéployé (infra/RAILWAY_STAGING.md, « Activation sur Railway »). Il répond à une seule
question : le proxy écrase-t-il l'en-tête envoyé par le client, ou le laisse-t-il passer ?

Principe, en deux phases de 12 envois de `POST /devices/auth` (secret bidon). Cette route est
limitée à 10 par minute et par adresse.
1. Phase témoin : 12 envois avec le MÊME `X-Real-IP`. Elle prouve que la limite est observable :
   le 11e envoi doit répondre 429. Sinon (aucun 429), l'essai ne peut rien conclure :
   `INCONCLUSIVE` (plusieurs instances du service, adresses de connexion qui changent d'une
   requête à l'autre, limite inopérante...). Constaté sur le staging le 22/10/2026.
2. Phase d'usurpation : 12 envois avec un `X-Real-IP` DIFFÉRENT à chaque fois, tout de suite après.
   - Le proxy écrase l'en-tête : les envois partagent l'adresse réelle, dont le quota vient d'être
     épuisé par la phase témoin : tout répond 429. Verdict `NOT_SPOOFABLE`.
   - Le proxy laisse passer l'en-tête : chaque envoi a « sa » adresse, aucun 429. Un client peut
     se fabriquer des quotas à volonté. Verdict `SPOOFABLE` : remettre `CLIENT_IP_HEADER` à
     vide tout de suite.
   - Un mélange de 429 et de réponses normales : `INCONCLUSIVE`.

Ce que l'essai ne peut pas voir : si `CLIENT_IP_HEADER` est vide, le verdict est aussi
`NOT_SPOOFABLE` (tout le monde partage l'adresse du proxy). Le verdict ne vaut donc que si le
réglage est actif : vérifiez-le dans le journal de démarrage (`capacity.checked`,
`client_ip_header`).

L'essai envoie 24 requêtes, toutes refusées (appareil inexistant) : rien n'est créé ni lu.
Aucun secret n'est utilisé ni enregistré. Il s'exécute sur un serveur distant : confirmer avec
`--allow-remote`.

Usage (depuis services/api) :
    PYTHONPATH=. python scripts/spoof_test.py --api-url https://API_STAGING --allow-remote \\
        --json-out ~/preuve-x-real-ip.json
"""

import argparse
import ipaddress
import json
import sys
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

REQUESTS = 12
LIMIT = 10  # POST /devices/auth : 10 par minute et par adresse (app/routers/devices.py)
FIRST_REFUSAL_EXPECTED = LIMIT + 1  # le 11e envoi
SPOOFABLE = "SPOOFABLE"
NOT_SPOOFABLE = "NOT_SPOOFABLE"
INCONCLUSIVE = "INCONCLUSIVE"


def _valid_shape(statuses: list[int | None], phase: str) -> tuple[bool, str]:
    if len(statuses) != REQUESTS:
        return False, f"{phase} : {REQUESTS} envois attendus, {len(statuses)} reçus"
    if any(status is None or status >= 500 for status in statuses):
        return False, f"{phase} : erreur réseau ou erreur serveur pendant l'essai"
    unexpected = sorted({s for s in statuses if s not in (401, 403, 404, 429)})
    if unexpected:
        return False, f"{phase} : réponses inattendues {unexpected}"
    return True, ""


def judge(control: list[int | None], varied: list[int | None]) -> tuple[str, str]:
    """Verdict et raison, d'après les codes de réponse des deux phases, dans l'ordre d'envoi
    (None : échec réseau). Fonction pure : c'est elle que les tests exercent."""
    for statuses, phase in ((control, "phase témoin"), (varied, "phase d'usurpation")):
        ok, reason = _valid_shape(statuses, phase)
        if not ok:
            return INCONCLUSIVE, reason

    refused = [index + 1 for index, status in enumerate(control) if status == 429]
    if not refused:
        return INCONCLUSIVE, (
            f"phase témoin : aucun 429 en {REQUESTS} envois depuis la même adresse, la limite de "
            f"{LIMIT} par minute n'est pas observable (plusieurs instances, adresse de connexion "
            "variable ou limite inopérante) : l'essai ne peut rien conclure"
        )
    first = refused[0]
    if first != FIRST_REFUSAL_EXPECTED or refused != list(range(first, REQUESTS + 1)):
        return INCONCLUSIVE, (
            f"phase témoin : limitation aux envois {refused} (attendue à partir du "
            f"{FIRST_REFUSAL_EXPECTED}e, sans interruption) : quota déjà entamé ou irrégulier, "
            "attendre une minute"
        )

    limited = sum(1 for status in varied if status == 429)
    if limited == REQUESTS:
        return NOT_SPOOFABLE, (
            f"les {REQUESTS} envois aux en-têtes différents partagent le quota épuisé par la phase "
            "témoin : l'en-tête du client est écrasé ou ignoré"
        )
    if limited == 0:
        return SPOOFABLE, (
            f"aucune limitation sur {REQUESTS} envois aux en-têtes différents, alors que la phase "
            "témoin a prouvé que la limite fonctionne : le proxy laisse passer l'en-tête du client"
        )
    return INCONCLUSIVE, (
        f"phase d'usurpation : {limited} refus sur {REQUESTS}, ni tous ni aucun (fenêtre de "
        "temps, instances multiples ?)"
    )


def _is_local(api_url: str) -> bool:
    host = urlparse(api_url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _fake_address(index: int) -> str:
    # Plage 198.18.0.0/15 : réservée aux bancs d'essai (RFC 2544), jamais une vraie adresse.
    return str(ipaddress.ip_address("198.18.0.0") + index + 1)


def _post(client: httpx.Client, address: str) -> int | None:
    body = {
        "tenant_id": str(uuid.UUID(int=0)),
        "device_id": "essai-anti-usurpation",
        "secret": "secret-bidon-refuse",
    }
    try:
        return client.post("/devices/auth", json=body, headers={"X-Real-IP": address}).status_code
    except httpx.HTTPError:
        return None


def run_probe(client: httpx.Client) -> tuple[list[int | None], list[int | None]]:
    """Phase témoin (même adresse) puis phase d'usurpation (adresses différentes)."""
    control = [_post(client, _fake_address(0)) for _ in range(REQUESTS)]
    varied = [_post(client, _fake_address(index + 1)) for index in range(REQUESTS)]
    return control, varied


def build_proof(
    api_url: str,
    control: list[int | None],
    varied: list[int | None],
    verdict: str,
    reason: str,
) -> dict:
    return {
        "essai": "anti-usurpation X-Real-IP",
        "heure_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "cible": urlparse(api_url).hostname,
        "envois_par_phase": REQUESTS,
        "limite_par_minute": LIMIT,
        "codes_phase_temoin": control,
        "codes_phase_usurpation": varied,
        "verdict": verdict,
        "raison": reason,
        "reserve": (
            "Valable seulement si CLIENT_IP_HEADER=X-Real-IP était actif sur le service au "
            "moment de l'essai (journal de démarrage, ligne capacity.checked)."
        ),
    }


def main(argv: list[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args(argv)
    if not _is_local(args.api_url) and not args.allow_remote:
        print("Refusé : cible distante, ajoutez --allow-remote pour confirmer.", file=sys.stderr)
        return 2

    with httpx.Client(base_url=args.api_url, timeout=15.0, transport=transport) as client:
        control, varied = run_probe(client)
    verdict, reason = judge(control, varied)
    proof = build_proof(args.api_url, control, varied, verdict, reason)
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(proof, handle, ensure_ascii=False, indent=2)
    if verdict == SPOOFABLE:
        print(
            "\nACTION IMMÉDIATE : remettre CLIENT_IP_HEADER à vide sur le service API.",
            file=sys.stderr,
        )
    return {NOT_SPOOFABLE: 0, SPOOFABLE: 1, INCONCLUSIVE: 3}[verdict]


if __name__ == "__main__":
    sys.exit(main())
