"""Essai anti-usurpation de l'adresse du client (en-tête `CLIENT_IP_HEADER`).

À lancer APRÈS avoir renseigné `CLIENT_IP_HEADER=X-Real-IP` sur le service API et l'avoir
redéployé (infra/RAILWAY_STAGING.md, « Activation sur Railway »). Il répond à une seule
question : le proxy écrase-t-il l'en-tête envoyé par le client, ou le laisse-t-il passer ?

Principe : 12 envois de `POST /devices/auth` avec un secret bidon, chacun avec un `X-Real-IP`
différent. La route est limitée à 10 par minute et par adresse.
- Le proxy écrase l'en-tête : les 12 envois partagent la même adresse, le 11e répond 429.
  Verdict `NOT_SPOOFABLE`.
- Le proxy laisse passer l'en-tête : chaque envoi a « sa » adresse, aucun 429. Un client peut
  se fabriquer des quotas à volonté. Verdict `SPOOFABLE` : remettre `CLIENT_IP_HEADER` à vide
  tout de suite.
- Tout autre résultat (429 trop tôt : quota déjà entamé ; erreurs serveur ; réseau) :
  `INCONCLUSIVE`. Attendre une minute et recommencer.

Ce que l'essai ne peut pas voir : si `CLIENT_IP_HEADER` est vide, le verdict est aussi
`NOT_SPOOFABLE` (tout le monde partage l'adresse du proxy). Le verdict ne vaut donc que si le
réglage est actif : vérifiez-le dans le journal de démarrage (`capacity.checked`,
`client_ip_header`).

L'essai envoie 12 requêtes, toutes refusées (appareil inexistant) : rien n'est créé ni lu.
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


def judge(statuses: list[int | None]) -> tuple[str, str]:
    """Verdict et raison, d'après les codes de réponse dans l'ordre d'envoi (None : échec
    réseau). Fonction pure : c'est elle que les tests exercent."""
    if len(statuses) != REQUESTS:
        return INCONCLUSIVE, f"{REQUESTS} envois attendus, {len(statuses)} reçus"
    if any(status is None or status >= 500 for status in statuses):
        return INCONCLUSIVE, "erreur réseau ou erreur serveur pendant l'essai"
    unexpected = [s for s in statuses if s not in (401, 403, 404, 429)]
    if unexpected:
        return INCONCLUSIVE, f"réponses inattendues : {sorted(set(unexpected))}"
    refused = [index + 1 for index, status in enumerate(statuses) if status == 429]
    if not refused:
        return SPOOFABLE, (
            f"aucune limitation en {REQUESTS} envois : le proxy laisse passer l'en-tête du client"
        )
    first = refused[0]
    if first < FIRST_REFUSAL_EXPECTED:
        return INCONCLUSIVE, (
            f"limitation dès l'envoi {first} (attendue au {FIRST_REFUSAL_EXPECTED}e) : le quota "
            "était déjà entamé, attendre une minute"
        )
    if first > FIRST_REFUSAL_EXPECTED:
        return INCONCLUSIVE, (
            f"limitation à l'envoi {first} seulement (attendue au {FIRST_REFUSAL_EXPECTED}e) : "
            "ce n'est pas la limite de 10 par minute d'une adresse unique"
        )
    if refused != list(range(first, REQUESTS + 1)):
        return INCONCLUSIVE, f"limitation irrégulière aux envois {refused}"
    return NOT_SPOOFABLE, (
        f"limitation à partir de l'envoi {first} : les {REQUESTS} envois partagent une adresse "
        "malgré des en-têtes différents"
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


def run_probe(client: httpx.Client) -> list[int | None]:
    statuses: list[int | None] = []
    body = {
        "tenant_id": str(uuid.UUID(int=0)),
        "device_id": "essai-anti-usurpation",
        "secret": "secret-bidon-refuse",
    }
    for index in range(REQUESTS):
        try:
            response = client.post(
                "/devices/auth", json=body, headers={"X-Real-IP": _fake_address(index)}
            )
            statuses.append(response.status_code)
        except httpx.HTTPError:
            statuses.append(None)
    return statuses


def build_proof(api_url: str, statuses: list[int | None], verdict: str, reason: str) -> dict:
    return {
        "essai": "anti-usurpation X-Real-IP",
        "heure_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "cible": urlparse(api_url).hostname,
        "envois": REQUESTS,
        "limite_par_minute": LIMIT,
        "codes_de_reponse": statuses,
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
        statuses = run_probe(client)
    verdict, reason = judge(statuses)
    proof = build_proof(args.api_url, statuses, verdict, reason)
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
