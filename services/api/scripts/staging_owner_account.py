"""Compte personnel du propriétaire du staging (Keycloak) : création, vérification, mot de passe
choisi par la personne elle-même.

Pourquoi un outil plus qu'un compte créé à la main : le compte a besoin de plusieurs réglages
(rôle, client, profil complet) et il faut prouver, avant de le remettre, qu'il fonctionne, sans que
le mot de passe ne passe jamais par un message, un fichier ou un journal.

Ce que `create` fait (idempotent) :
- refuse les comptes de démonstration et le compte de test dédié (`demo.admin`,
  `demo.technicien`, `loadtest.staging`) : un compte personnel est distinct d'eux ;
- crée l'utilisateur dans le royaume `paios` avec le seul rôle `admin_tenant` (administrateur du
  client : toutes les routes de l'API l'acceptent, aucun autre rôle n'est nécessaire) et le client
  demandé (`tenant_id`) ;
- lui donne un mot de passe aléatoire de 32 octets, **jamais affiché ni écrit** : il ne sert qu'à
  prouver que la connexion marche, puis il est retiré ;
- vérifie : un jeton est délivré par Keycloak, et l'API (`GET /me`) voit bien le rôle
  `admin_tenant`, l'identifiant et le client ;
- exécute, si demandé après `--`, une commande de contrôle (par exemple une connexion dans un
  navigateur) avec l'identifiant et le mot de passe dans **l'environnement du processus enfant
  seulement**, sans le mot de passe administrateur ; sa sortie est filtrée (le mot de passe y est
  remplacé par « *** ») ;
- retire ensuite le mot de passe et impose son changement (`UPDATE_PASSWORD`), **même si une
  vérification a échoué** : le compte n'est jamais laissé avec un mot de passe que personne ne
  connaît mais que le programme a déjà vu.

Il reste alors à la personne de définir son mot de passe dans la console Keycloak (royaume
`paios`, Utilisateurs, son compte, onglet des identifiants, « temporaire » activé) : Keycloak lui
imposera d'en choisir un nouveau à la première connexion. Si le compte existe déjà, l'outil ne
touche ni à son mot de passe ni à son état ; il vérifie seulement le rôle et le client.

Le mot de passe administrateur de Keycloak vient de la variable d'environnement
`KEYCLOAK_ADMIN_PASSWORD` (ou est demandé sans être affiché) : il ne doit jamais transiter par le
dépôt, un message ou un journal.

Usage (depuis services/api) :
    PYTHONPATH=. python scripts/staging_owner_account.py create \\
        --keycloak-url https://KEYCLOAK_STAGING --api-url https://API_STAGING \\
        --username IDENTIFIANT
    # avec une commande de contrôle (identifiant et mot de passe reçus par l'environnement) :
    PYTHONPATH=. python scripts/staging_owner_account.py create ... \\
        -- node infra/staging-web-login-check.mjs URL_WEB
"""

import argparse
import getpass
import os
import secrets
import subprocess
import sys
import uuid

import httpx

from scripts.staging_account import (
    DEFAULT_TENANT,
    DEFAULT_USERNAME,
    DEMO_USERS,
    StagingAccountError,
    _check,
    _find_user,
    admin_token,
)

ROLE = "admin_tenant"
NOT_PERSONAL = (*DEMO_USERS, DEFAULT_USERNAME)


class OwnerCheckError(Exception):
    """Une vérification a échoué ; le message ne contient jamais de secret."""


def _assign_role(client: httpx.Client, realm: str, user_id: str) -> None:
    role = _check(client.get(f"/admin/realms/{realm}/roles/{ROLE}"), "lecture du rôle").json()
    _check(
        client.post(f"/admin/realms/{realm}/users/{user_id}/role-mappings/realm", json=[role]),
        "attribution du rôle",
    )


def _create_user(client: httpx.Client, args: argparse.Namespace, password: str) -> dict:
    _check(
        client.post(
            f"/admin/realms/{args.realm}/users",
            json={
                "username": args.username,
                "enabled": True,
                "emailVerified": True,
                # Le profil utilisateur de Keycloak exige ces champs ; sans eux, la connexion
                # répond « compte incomplet ». L'adresse par défaut n'existe pas : à remplacer
                # dans la console par la vraie si l'on veut recevoir des messages de Keycloak.
                "email": args.email or f"{args.username}@example.invalid",
                "firstName": args.first_name,
                "lastName": args.last_name,
                "attributes": {"tenant_id": [args.tenant_id]},
                "credentials": [{"type": "password", "value": password, "temporary": False}],
            },
        ),
        "création de l'utilisateur",
    )
    user = _find_user(client, args.realm, args.username)
    if user is None:
        raise StagingAccountError("l'utilisateur créé est introuvable")
    return user


def verify_login(
    args: argparse.Namespace, password: str, *, transport: httpx.BaseTransport | None
) -> None:
    """Jeton délivré par Keycloak, puis accepté par l'API avec le bon rôle, le bon identifiant et
    le bon client. Rien de ce qui est lu ici (jeton, mot de passe) n'est affiché."""
    token_url = f"{args.keycloak_url.rstrip('/')}/realms/{args.realm}/protocol/openid-connect/token"
    with httpx.Client(timeout=20.0, transport=transport) as client:
        response = client.post(
            token_url,
            data={
                "grant_type": "password",
                "client_id": "paios-api",
                "username": args.username,
                "password": password,
            },
        )
        if response.status_code != 200 or not response.json().get("access_token"):
            raise OwnerCheckError(
                f"connexion refusée par Keycloak (HTTP {response.status_code}) : "
                "aucun jeton délivré"
            )
        print("  jeton délivré : oui")
        me = client.get(
            f"{args.api_url.rstrip('/')}/me",
            headers={"Authorization": f"Bearer {response.json()['access_token']}"},
        )
    if me.status_code != 200:
        raise OwnerCheckError(f"l'API refuse le jeton (HTTP {me.status_code})")
    body = me.json()
    if body.get("username") != args.username:
        raise OwnerCheckError("l'API ne reconnaît pas l'identifiant du compte")
    if ROLE not in body.get("roles", []):
        raise OwnerCheckError(f"l'API ne voit pas le rôle {ROLE} pour ce compte")
    if body.get("tenant_id") != args.tenant_id:
        raise OwnerCheckError("l'API voit ce compte dans un autre client que celui demandé")
    print(f"  API : accès administrateur confirmé (rôle {ROLE}, client {args.tenant_id})")


def run_control_command(command: list[str], username: str, password: str) -> None:
    """L'identifiant et le mot de passe passent par l'environnement du processus enfant, jamais
    par ses arguments (visibles avec `ps`), et sans le mot de passe administrateur."""
    env = {k: v for k, v in os.environ.items() if k != "KEYCLOAK_ADMIN_PASSWORD"}
    env["STAGING_OWNER_USERNAME"] = username
    env["STAGING_OWNER_PASSWORD"] = password
    done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=300)
    for stream, target in ((done.stdout, sys.stdout), (done.stderr, sys.stderr)):
        if stream:
            print(stream.replace(password, "***"), end="", file=target)
    if done.returncode != 0:
        raise OwnerCheckError(f"commande de contrôle en échec (code {done.returncode})")


def retire_password_and_require_change(client: httpx.Client, realm: str, user: dict) -> None:
    """Le compte ne garde aucun mot de passe actif, et Keycloak imposera d'en choisir un."""
    _check(
        client.put(
            f"/admin/realms/{realm}/users/{user['id']}",
            json={**user, "requiredActions": ["UPDATE_PASSWORD"]},
        ),
        "changement de mot de passe obligatoire",
    )
    credentials = _check(
        client.get(f"/admin/realms/{realm}/users/{user['id']}/credentials"),
        "lecture des identifiants",
    ).json()
    for credential in credentials:
        if credential.get("type") == "password":
            _check(
                client.delete(
                    f"/admin/realms/{realm}/users/{user['id']}/credentials/{credential['id']}"
                ),
                "retrait du mot de passe",
            )


def create_owner(
    client: httpx.Client,
    args: argparse.Namespace,
    control: list[str],
    *,
    transport: httpx.BaseTransport | None,
) -> None:
    existing = _find_user(client, args.realm, args.username)
    if existing is not None:
        attributes = {**(existing.get("attributes") or {}), "tenant_id": [args.tenant_id]}
        if attributes != (existing.get("attributes") or {}):
            _check(
                client.put(
                    f"/admin/realms/{args.realm}/users/{existing['id']}",
                    json={**existing, "attributes": attributes},
                ),
                "mise à jour du client",
            )
        _assign_role(client, args.realm, existing["id"])
        print(
            f"Le compte {args.username} existe déjà : mot de passe et état inchangés "
            f"(rôle {ROLE} et client vérifiés)."
        )
        return

    password = secrets.token_urlsafe(32)
    user = _create_user(client, args, password)
    print(f"Compte {args.username} créé (rôle {ROLE}, client {args.tenant_id}). Vérification :")
    try:
        _assign_role(client, args.realm, user["id"])
        verify_login(args, password, transport=transport)
        if control:
            run_control_command(control, args.username, password)
            print("  commande de contrôle : réussie")
    finally:
        retire_password_and_require_change(client, args.realm, user)
    print(
        "Le compte n'a plus aucun mot de passe actif. À faire par vous, dans la console Keycloak "
        f"(royaume {args.realm}, Utilisateurs, {args.username}, onglet des identifiants) : définir "
        "votre mot de passe en laissant « temporaire » activé. Keycloak vous imposera d'en "
        "choisir un nouveau à la première connexion."
    )


def _split_control(argv: list[str]) -> tuple[list[str], list[str]]:
    if "--" in argv:
        index = argv.index("--")
        return argv[:index], argv[index + 1 :]
    return argv, []


def _parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    own, control = _split_control(list(sys.argv[1:] if argv is None else argv))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("create",))
    parser.add_argument("--keycloak-url", required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--realm", default="paios")
    parser.add_argument("--admin-user", default=os.environ.get("KEYCLOAK_ADMIN_USER", "admin"))
    parser.add_argument("--username", required=True, help="Votre identifiant habituel")
    parser.add_argument("--first-name", default="Administrateur")
    parser.add_argument("--last-name", default="Enoryx")
    parser.add_argument("--email", default=None, help="Adresse réelle (sinon une adresse factice)")
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT)
    return parser.parse_args(own), control


def main(argv: list[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    args, control = _parse_args(argv)
    if args.username in NOT_PERSONAL:
        print(
            f"Refusé : {args.username} est un compte de démonstration ou de test, pas un compte "
            "personnel. Choisissez votre propre identifiant.",
            file=sys.stderr,
        )
        return 1
    try:
        uuid.UUID(args.tenant_id)  # refuse un identifiant de client mal écrit avant tout appel
    except ValueError:
        print("Échec : identifiant de client invalide.", file=sys.stderr)
        return 1
    password = os.environ.get("KEYCLOAK_ADMIN_PASSWORD") or getpass.getpass(
        "Mot de passe administrateur Keycloak (non affiché) : "
    )
    try:
        with httpx.Client(
            base_url=args.keycloak_url.rstrip("/"), timeout=20.0, transport=transport
        ) as client:
            token = admin_token(client, user=args.admin_user, password=password)
            client.headers["Authorization"] = f"Bearer {token}"
            create_owner(client, args, control, transport=transport)
    except (StagingAccountError, OwnerCheckError, httpx.HTTPError, ValueError) as exc:
        print(f"Échec : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
