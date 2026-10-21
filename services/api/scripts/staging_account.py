"""Compte de test dédié du staging (Keycloak) : création, rotation, désactivation des comptes de
démonstration. À lancer par la personne qui détient le mot de passe administrateur de Keycloak.

Pourquoi un outil plutôt qu'une action faite pour vous : ce mot de passe est une variable du
service Keycloak sur Railway, masquée pour les assistants et les outils. Il ne doit pas transiter
par le dépôt, un message, ni un journal. Cet outil le lit dans la variable d'environnement
`KEYCLOAK_ADMIN_PASSWORD` ou le demande sans l'afficher.

Ce que `create` fait (idempotent) :
- crée l'utilisateur `loadtest.staging` dans le royaume `paios` : rôle `technicien` seulement
  (aucun droit d'administration), rattaché au client demandé (`tenant_id`) ;
- lui donne un mot de passe aléatoire de 32 octets, écrit **uniquement** dans un fichier hors du
  dépôt (par défaut `~/.config/paios/staging-loadtest.env`, droits 0600) ; ni ce mot de passe ni
  un jeton ne sont jamais affichés ;
- si le compte existe déjà, ne touche pas à son mot de passe, sauf avec `--rotate`.

`scripts/staging_probe.py` lit ce fichier, obtient un jeton de courte durée et lance la mesure de
charge sans jamais l'imprimer ni l'écrire.

Ce que `disable-demo-users` fait : désactive `demo.technicien` et `demo.admin` du royaume (le mot
de passe documenté dans infra/README.md fonctionne sur le staging, exposé sur Internet). Réversible
(`enabled` repasse à vrai dans la console Keycloak). Demande `--yes`.

Usage (depuis services/api) :
    PYTHONPATH=. python scripts/staging_account.py create \\
        --keycloak-url https://virtuous-communication-staging.up.railway.app
    PYTHONPATH=. python scripts/staging_account.py disable-demo-users --yes \\
        --keycloak-url https://virtuous-communication-staging.up.railway.app
"""

import argparse
import getpass
import os
import secrets
import stat
import sys
import uuid
from pathlib import Path

import httpx

DEFAULT_TENANT = "11111111-1111-1111-1111-111111111111"
DEFAULT_USERNAME = "loadtest.staging"
DEFAULT_CREDENTIALS = Path.home() / ".config" / "paios" / "staging-loadtest.env"
DEMO_USERS = ("demo.technicien", "demo.admin")
ROLE = "technicien"


class StagingAccountError(Exception):
    """Échec attendu (identifiants refusés, royaume absent...) : message sans secret."""


def admin_token(client: httpx.Client, *, user: str, password: str) -> str:
    response = client.post(
        "/realms/master/protocol/openid-connect/token",
        data={
            "client_id": "admin-cli",
            "grant_type": "password",
            "username": user,
            "password": password,
        },
    )
    if response.status_code != 200:
        raise StagingAccountError(
            f"authentification administrateur refusée par Keycloak (HTTP {response.status_code})"
        )
    return response.json()["access_token"]


def _check(response: httpx.Response, action: str) -> httpx.Response:
    if response.status_code >= 400:
        # Jamais le corps de la réponse : il peut citer l'utilisateur ou un identifiant.
        raise StagingAccountError(f"{action} : HTTP {response.status_code}")
    return response


def _find_user(client: httpx.Client, realm: str, username: str) -> dict | None:
    response = _check(
        client.get(f"/admin/realms/{realm}/users", params={"username": username, "exact": "true"}),
        "recherche de l'utilisateur",
    )
    users = [u for u in response.json() if u["username"] == username]
    return users[0] if users else None


def write_credentials(path: Path, values: dict[str, str]) -> None:
    """Fichier hors du dépôt, droits 0600 dès la création (jamais lisible par un autre compte,
    même un instant)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except PermissionError:
        pass
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")
    path.chmod(0o600)


def create_account(
    client: httpx.Client,
    *,
    realm: str,
    username: str,
    tenant_id: str,
    credentials_file: Path,
    keycloak_url: str,
    rotate: bool,
) -> str:
    """Renvoie « created », « rotated » ou « unchanged »."""
    uuid.UUID(tenant_id)  # refuse un identifiant de client mal écrit avant tout appel
    existing = _find_user(client, realm, username)
    password = secrets.token_urlsafe(32)

    if existing is None:
        _check(
            client.post(
                f"/admin/realms/{realm}/users",
                json={
                    "username": username,
                    "enabled": True,
                    "emailVerified": True,
                    # Le profil utilisateur de Keycloak exige ces champs ; sans eux, la
                    # connexion répond « compte incomplet ».
                    "email": f"{username}@example.invalid",
                    "firstName": "Test",
                    "lastName": "Charge",
                    "attributes": {"tenant_id": [tenant_id]},
                    "credentials": [{"type": "password", "value": password, "temporary": False}],
                },
            ),
            "création de l'utilisateur",
        )
        user = _find_user(client, realm, username)
        outcome = "created"
    else:
        user, outcome = existing, "unchanged"
        attributes = {**(user.get("attributes") or {}), "tenant_id": [tenant_id]}
        _check(
            client.put(
                f"/admin/realms/{realm}/users/{user['id']}", json={**user, "attributes": attributes}
            ),
            "mise à jour de l'utilisateur",
        )
        if rotate:
            _check(
                client.put(
                    f"/admin/realms/{realm}/users/{user['id']}/reset-password",
                    json={"type": "password", "value": password, "temporary": False},
                ),
                "changement du mot de passe",
            )
            outcome = "rotated"

    role = _check(client.get(f"/admin/realms/{realm}/roles/{ROLE}"), "lecture du rôle").json()
    _check(
        client.post(f"/admin/realms/{realm}/users/{user['id']}/role-mappings/realm", json=[role]),
        "attribution du rôle",
    )
    if outcome in ("created", "rotated"):
        write_credentials(
            credentials_file,
            {
                "KEYCLOAK_URL": keycloak_url.rstrip("/"),
                "KEYCLOAK_REALM": realm,
                "KEYCLOAK_CLIENT_ID": "paios-api",
                "STAGING_USERNAME": username,
                "STAGING_PASSWORD": password,
            },
        )
    return outcome


def disable_demo_users(client: httpx.Client, *, realm: str) -> list[str]:
    disabled = []
    for username in DEMO_USERS:
        user = _find_user(client, realm, username)
        if user is None or not user.get("enabled", True):
            continue
        _check(
            client.put(
                f"/admin/realms/{realm}/users/{user['id']}", json={**user, "enabled": False}
            ),
            f"désactivation de {username}",
        )
        disabled.append(username)
    return disabled


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("create", "disable-demo-users"))
    parser.add_argument("--keycloak-url", required=True)
    parser.add_argument("--realm", default="paios")
    parser.add_argument("--admin-user", default=os.environ.get("KEYCLOAK_ADMIN_USER", "admin"))
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT)
    parser.add_argument("--credentials-file", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--rotate", action="store_true", help="Nouveau mot de passe aléatoire")
    parser.add_argument("--yes", action="store_true", help="Confirme disable-demo-users")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "disable-demo-users" and not args.yes:
        print(
            "Refusé : ajoutez --yes pour désactiver les comptes de démonstration.", file=sys.stderr
        )
        return 2
    password = os.environ.get("KEYCLOAK_ADMIN_PASSWORD") or getpass.getpass(
        "Mot de passe administrateur Keycloak (non affiché) : "
    )
    try:
        with httpx.Client(
            base_url=args.keycloak_url.rstrip("/"), timeout=20.0, transport=transport
        ) as client:
            token = admin_token(client, user=args.admin_user, password=password)
            client.headers["Authorization"] = f"Bearer {token}"
            if args.command == "create":
                outcome = create_account(
                    client,
                    realm=args.realm,
                    username=args.username,
                    tenant_id=args.tenant_id,
                    credentials_file=args.credentials_file,
                    keycloak_url=args.keycloak_url,
                    rotate=args.rotate,
                )
                if outcome == "unchanged":
                    print(
                        f"Le compte {args.username} existe déjà : mot de passe inchangé "
                        "(--rotate pour le renouveler)."
                    )
                else:
                    print(
                        f"Compte {args.username} {'créé' if outcome == 'created' else 'renouvelé'}."
                    )
                    print(f"Identifiants enregistrés (droits 0600) : {args.credentials_file}")
            else:
                disabled = disable_demo_users(client, realm=args.realm)
                print(
                    "Comptes de démonstration désactivés : "
                    + (", ".join(disabled) or "aucun (déjà désactivés)")
                )
    except (StagingAccountError, httpx.HTTPError, ValueError) as exc:
        print(f"Échec : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
