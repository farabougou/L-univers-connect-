"""Mesure de charge authentifiée du staging, sans jamais afficher ni enregistrer le jeton.

Pourquoi ce lanceur : `scripts/load_probe.py` sait envoyer un jeton (variable
`LOAD_PROBE_TOKEN`), mais il faut d'abord en obtenir un. Ce lanceur lit les identifiants du
compte dédié (créés par `scripts/staging_account.py`, dans un fichier hors du dépôt aux droits
0600), demande à Keycloak un jeton de courte durée, puis lance `load_probe.py` en lui passant le
jeton **uniquement dans l'environnement du processus enfant** : il ne figure ni dans les
arguments (visibles avec `ps`), ni dans un fichier, ni dans la sortie.

Le fichier d'identifiants est refusé s'il est lisible par un autre compte que le vôtre.

Usage (depuis services/api) ; tout ce qui suit `--` est transmis à `load_probe.py` :
    PYTHONPATH=. python scripts/staging_probe.py \\
        --api-url https://API_STAGING --allow-remote -- \\
        --path "/sync/interventions?limit=50" --levels 1,2,4 --step-seconds 10 --label staging

Le quota de 120 requêtes par minute et par utilisateur s'applique : la montée s'arrête à la
première limitation (429), c'est voulu. Aucune requête n'écrit : GET uniquement.
"""

import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path

import httpx

DEFAULT_CREDENTIALS = Path.home() / ".config" / "paios" / "staging-loadtest.env"
LOAD_PROBE = Path(__file__).resolve().parent / "load_probe.py"
REQUIRED_KEYS = (
    "KEYCLOAK_URL",
    "KEYCLOAK_REALM",
    "KEYCLOAK_CLIENT_ID",
    "STAGING_USERNAME",
    "STAGING_PASSWORD",
)


class StagingProbeError(Exception):
    """Échec attendu ; le message ne contient jamais de secret."""


def load_credentials(path: Path) -> dict[str, str]:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError as exc:
        raise StagingProbeError(
            f"fichier d'identifiants introuvable : {path} (voir scripts/staging_account.py)"
        ) from exc
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise StagingProbeError(
            f"droits trop larges sur {path} : exécutez « chmod 600 {path} » puis recommencez"
        )
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    missing = [key for key in REQUIRED_KEYS if not values.get(key)]
    if missing:
        raise StagingProbeError(f"champs absents du fichier d'identifiants : {', '.join(missing)}")
    return values


def fetch_token(
    credentials: dict[str, str], *, transport: httpx.BaseTransport | None = None
) -> str:
    url = (
        f"{credentials['KEYCLOAK_URL'].rstrip('/')}"
        f"/realms/{credentials['KEYCLOAK_REALM']}/protocol/openid-connect/token"
    )
    try:
        with httpx.Client(timeout=20.0, transport=transport) as client:
            response = client.post(
                url,
                data={
                    "grant_type": "password",
                    "client_id": credentials["KEYCLOAK_CLIENT_ID"],
                    "username": credentials["STAGING_USERNAME"],
                    "password": credentials["STAGING_PASSWORD"],
                },
            )
    except httpx.HTTPError as exc:
        # Le type seul : le message d'une erreur réseau peut citer l'adresse demandée.
        raise StagingProbeError(
            f"Keycloak injoignable ({type(exc).__name__}) : aucune mesure lancée"
        ) from exc
    if response.status_code != 200:
        raise StagingProbeError(
            f"jeton refusé par Keycloak (HTTP {response.status_code}) : compte absent, désactivé "
            "ou mot de passe renouvelé ? Relancez scripts/staging_account.py create"
        )
    token = response.json().get("access_token")
    if not token:
        raise StagingProbeError("réponse de Keycloak sans jeton")
    return token


def build_command(api_url: str, passthrough: list[str], *, allow_remote: bool) -> list[str]:
    command = [sys.executable, str(LOAD_PROBE), "--base-url", api_url]
    if allow_remote:
        command.append("--allow-remote")
    return command + passthrough


def child_environment(token: str) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key != "LOAD_PROBE_TOKEN"}
    environment["LOAD_PROBE_TOKEN"] = token
    environment["PYTHONPATH"] = str(LOAD_PROBE.parent.parent) + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
    )
    return environment


def _parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--credentials-file", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Confirme l'envoi de charge à un serveur distant (obligatoire pour le staging)",
    )
    args, rest = parser.parse_known_args(argv)
    if rest and rest[0] == "--":
        rest = rest[1:]
    return args, rest


def main(argv: list[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    args, passthrough = _parse_args(argv)
    if any(arg.startswith("--base-url") or "LOAD_PROBE_TOKEN" in arg for arg in passthrough):
        print("Refusé : --base-url vient de --api-url ; le jeton ne se passe jamais en argument.")
        return 2
    try:
        token = fetch_token(load_credentials(args.credentials_file), transport=transport)
    except StagingProbeError as exc:
        print(f"Échec : {exc}", file=sys.stderr)
        return 1
    command = build_command(args.api_url, passthrough, allow_remote=args.allow_remote)
    return subprocess.run(command, env=child_environment(token), check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
