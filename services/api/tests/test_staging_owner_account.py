"""Compte personnel du propriétaire du staging (scripts/staging_owner_account.py), face à une
fausse Keycloak et une fausse API en mémoire, sans réseau.

Ce que ces tests prouvent : le compte reçoit le seul rôle `admin_tenant` et le bon client ; un
mot de passe aléatoire sert à vérifier la connexion (jeton délivré, accès à l'API) puis est retiré,
le changement de mot de passe est imposé, même si la vérification échoue ; ni le mot de passe
administrateur, ni le mot de passe du compte, ni un jeton n'apparaissent dans la sortie ; un
second passage ne touche à rien ; les comptes de démonstration et le compte de test dédié ne
peuvent pas être pris pour compte personnel ; aucune suppression d'utilisateur n'est jamais émise.
"""

import json
import sys
from urllib.parse import parse_qs

import httpx
import pytest

import scripts.staging_owner_account as owner

ADMIN_PASSWORD = "mot-de-passe-admin-de-test-1234567890"
ADMIN_TOKEN = "jeton-admin-de-test"
TENANT = "11111111-1111-1111-1111-111111111111"
KEYCLOAK = "https://keycloak.test"
API = "https://api.test"
USERNAME = "mohamed"


class FakeStaging:
    """Assez de Keycloak (royaume master et paios) et d'API pour ce que l'outil appelle."""

    def __init__(self, *, api_roles=None, issue_token=True, with_user: str | None = None):
        self.users: dict[str, dict] = {}
        self.credentials: dict[str, list[dict]] = {}
        self.roles_given: dict[str, list[str]] = {}
        self.tokens: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []
        self.api_roles = api_roles
        self.issue_token = issue_token
        self.demo = {
            "demo.admin": {"id": "id-demo-admin", "username": "demo.admin", "enabled": False}
        }
        if with_user:
            self._add_user(with_user, {"tenant_id": [TENANT]}, password="ancien-mot-de-passe")

    def _add_user(self, username, attributes, *, password=None, **extra):
        user = {
            "id": f"id-{username}",
            "username": username,
            "enabled": True,
            "attributes": attributes,
            "requiredActions": [],
            **extra,
        }
        self.users[username] = user
        self.credentials[user["id"]] = (
            [{"id": f"cred-{username}", "type": "password", "value": password}] if password else []
        )
        return user

    def password_of(self, username):
        creds = self.credentials.get(f"id-{username}", [])
        return creds[0]["value"] if creds else None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        method, path, host = request.method, request.url.path, request.url.host
        self.calls.append((method, path))
        if host == "api.test":
            return self._api(request)
        if path == "/realms/master/protocol/openid-connect/token":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if form.get("password") != ADMIN_PASSWORD:
                return httpx.Response(401, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": ADMIN_TOKEN})
        if path == "/realms/paios/protocol/openid-connect/token":
            return self._user_token(request)
        if request.headers.get("Authorization") != f"Bearer {ADMIN_TOKEN}":
            return httpx.Response(401)
        return self._admin(request)

    def _user_token(self, request):
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        user = self.users.get(form.get("username", ""))
        ok = (
            user
            and self.issue_token
            and user["enabled"]
            and not user["requiredActions"]
            and self.password_of(user["username"]) == form.get("password")
        )
        if not ok:
            return httpx.Response(400, json={"error": "invalid_grant"})
        token = f"jeton-utilisateur-{user['username']}-qui-ne-doit-jamais-apparaitre"
        self.tokens[token] = user["username"]
        return httpx.Response(200, json={"access_token": token})

    def _api(self, request):
        user = self.tokens.get(request.headers.get("Authorization", "").removeprefix("Bearer "))
        if request.url.path != "/me" or user is None:
            return httpx.Response(401, json={"code": "TOKEN_INVALID"})
        roles = (
            self.api_roles if self.api_roles is not None else self.roles_given.get(f"id-{user}", [])
        )
        return httpx.Response(200, json={"username": user, "roles": roles, "tenant_id": TENANT})

    def _admin(self, request):
        method, path = request.method, request.url.path
        if path == "/admin/realms/paios/users" and method == "GET":
            wanted = request.url.params["username"]
            found = [u for u in {**self.users, **self.demo}.values() if u["username"] == wanted]
            return httpx.Response(200, json=found)
        if path == "/admin/realms/paios/users" and method == "POST":
            body = json.loads(request.content)
            user = self._add_user(
                body["username"],
                body["attributes"],
                password=body["credentials"][0]["value"] if body.get("credentials") else None,
                email=body.get("email"),
                firstName=body.get("firstName"),
                lastName=body.get("lastName"),
                emailVerified=body.get("emailVerified"),
            )
            user["enabled"] = body["enabled"]
            return httpx.Response(201)
        if path == "/admin/realms/paios/roles/admin_tenant":
            return httpx.Response(200, json={"id": "role-admin", "name": "admin_tenant"})
        parts = path.split("/")  # ['', 'admin', 'realms', 'paios', 'users', <id>, ...]
        if len(parts) >= 6 and parts[4] == "users":
            user = next((u for u in self.users.values() if u["id"] == parts[5]), None)
            if user is None:
                return httpx.Response(404)
            if len(parts) == 6 and method == "PUT":
                user.update(json.loads(request.content))
                return httpx.Response(204)
            if parts[6:7] == ["role-mappings"]:
                self.roles_given.setdefault(user["id"], []).extend(
                    r["name"] for r in json.loads(request.content)
                )
                return httpx.Response(204)
            if parts[6:7] == ["credentials"] and len(parts) == 7 and method == "GET":
                return httpx.Response(
                    200,
                    json=[{"id": c["id"], "type": c["type"]} for c in self.credentials[user["id"]]],
                )
            if parts[6:7] == ["credentials"] and len(parts) == 8 and method == "DELETE":
                self.credentials[user["id"]] = [
                    c for c in self.credentials[user["id"]] if c["id"] != parts[7]
                ]
                return httpx.Response(204)
        return httpx.Response(404)


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", ADMIN_PASSWORD)


def _run(fake, *extra, username=USERNAME, tenant=TENANT):
    argv = [
        "create",
        "--keycloak-url",
        KEYCLOAK,
        "--api-url",
        API,
        "--username",
        username,
        "--tenant-id",
        tenant,
        *extra,
    ]
    return owner.main(argv, transport=httpx.MockTransport(fake))


def _no_secret_in(captured, fake):
    text = captured.out + captured.err
    assert ADMIN_PASSWORD not in text and ADMIN_TOKEN not in text
    assert "jeton-utilisateur" not in text
    for credentials in fake.credentials.values():
        for credential in credentials:
            assert credential.get("value") not in text


def test_cree_le_compte_avec_le_seul_role_admin_tenant_et_le_bon_client(admin_env, capsys):
    fake = FakeStaging()

    assert _run(fake) == 0

    user = fake.users[USERNAME]
    assert fake.roles_given[user["id"]] == ["admin_tenant"]
    assert user["attributes"]["tenant_id"] == [TENANT]
    assert user["enabled"] is True


def test_verifie_la_connexion_le_jeton_et_l_acces_a_l_api(admin_env, capsys):
    fake = FakeStaging()

    assert _run(fake) == 0

    out = capsys.readouterr().out
    assert "jeton délivré : oui" in out
    assert "API : accès administrateur confirmé" in out
    assert ("GET", "/me") in fake.calls
    _no_secret_in(capsys.readouterr(), fake)


def test_retire_le_mot_de_passe_et_impose_le_changement(admin_env, capsys):
    fake = FakeStaging()

    assert _run(fake) == 0

    user = fake.users[USERNAME]
    assert fake.credentials[user["id"]] == []  # plus aucun mot de passe actif
    assert user["requiredActions"] == ["UPDATE_PASSWORD"]
    out = capsys.readouterr().out
    assert "aucun mot de passe actif" in out


def test_ni_mot_de_passe_ni_jeton_dans_la_sortie(admin_env, capsys):
    fake = FakeStaging()
    created = {}
    original = fake._add_user

    def spy(username, attributes, **kwargs):
        user = original(username, attributes, **kwargs)
        if kwargs.get("password"):
            created["password"] = kwargs["password"]
        return user

    fake._add_user = spy

    assert _run(fake) == 0

    captured = capsys.readouterr()
    assert created["password"] and len(created["password"]) >= 32
    assert created["password"] not in captured.out + captured.err
    _no_secret_in(captured, fake)


def test_si_la_verification_echoue_le_mot_de_passe_est_quand_meme_retire(admin_env, capsys):
    fake = FakeStaging(issue_token=False)

    assert _run(fake) == 1

    user = fake.users[USERNAME]
    assert fake.credentials[user["id"]] == []
    assert user["requiredActions"] == ["UPDATE_PASSWORD"]
    assert "jeton" in capsys.readouterr().err


def test_une_api_qui_ne_voit_pas_le_role_administrateur_fait_echouer(admin_env, capsys):
    fake = FakeStaging(api_roles=["technicien"])

    assert _run(fake) == 1

    user = fake.users[USERNAME]
    assert fake.credentials[user["id"]] == []
    assert "admin_tenant" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["demo.admin", "demo.technicien", "loadtest.staging"])
def test_refuse_un_compte_de_demonstration_ou_de_test_comme_compte_personnel(
    admin_env, capsys, name
):
    fake = FakeStaging()

    assert _run(fake, username=name) == 1

    assert fake.users == {}
    assert not [c for c in fake.calls if c[0] in ("POST", "PUT", "DELETE")]
    assert "compte personnel" in capsys.readouterr().err


def test_un_second_passage_ne_touche_a_rien(admin_env, capsys):
    fake = FakeStaging()
    _run(fake)
    capsys.readouterr()

    def writes():
        # La demande de jeton administrateur se refait à chaque exécution : pas une écriture.
        return [
            c
            for c in fake.calls
            if c[0] in ("POST", "DELETE") and not c[1].endswith("/openid-connect/token")
        ]

    writes_before = writes()
    state_before = json.dumps(fake.users[USERNAME], sort_keys=True)

    assert _run(fake) == 0

    new_writes = writes()[len(writes_before) :]
    # Seule l'attribution du rôle peut être rejouée (sans effet) : jamais de création,
    # de suppression de mot de passe ni de nouvelle connexion de vérification.
    assert all(path.endswith("/role-mappings/realm") for _, path in new_writes), new_writes
    assert json.dumps(fake.users[USERNAME], sort_keys=True) == state_before
    assert "existe déjà" in capsys.readouterr().out


def test_un_compte_existant_garde_son_mot_de_passe(admin_env, capsys):
    fake = FakeStaging(with_user=USERNAME)

    assert _run(fake) == 0

    assert fake.password_of(USERNAME) == "ancien-mot-de-passe"
    assert fake.users[USERNAME]["requiredActions"] == []


def test_un_client_mal_ecrit_est_refuse_avant_tout_appel(admin_env, capsys):
    fake = FakeStaging()

    assert _run(fake, tenant="pas-un-identifiant") == 1

    assert fake.calls == []


def test_un_mauvais_mot_de_passe_administrateur_echoue_sans_le_citer(monkeypatch, capsys):
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "autre-mot-de-passe-confidentiel")
    fake = FakeStaging()

    assert _run(fake) == 1

    captured = capsys.readouterr()
    assert "autre-mot-de-passe-confidentiel" not in captured.out + captured.err
    assert fake.users == {}


def test_n_emet_jamais_de_suppression_d_utilisateur_ni_ne_touche_aux_comptes_de_demo(
    admin_env, capsys
):
    fake = FakeStaging()
    _run(fake)

    for method, path in fake.calls:
        assert not (method == "DELETE" and "/credentials/" not in path)
        assert "id-demo-admin" not in path
    assert fake.demo["demo.admin"]["enabled"] is False


def test_la_commande_de_controle_recoit_le_mot_de_passe_par_l_environnement_seulement(
    admin_env, capsys, tmp_path
):
    fake = FakeStaging()
    probe = tmp_path / "sonde.py"
    probe.write_text(
        "import os, sys\n"
        "print('identifiant reçu :', os.environ['STAGING_OWNER_USERNAME'])\n"
        "print('mot de passe présent :', bool(os.environ.get('STAGING_OWNER_PASSWORD')))\n"
        "absent = 'KEYCLOAK_ADMIN_PASSWORD' not in os.environ\n"
        "print('mot de passe administrateur absent :', absent)\n"
        "print('retour du mot de passe :', os.environ['STAGING_OWNER_PASSWORD'])\n",
        encoding="utf-8",
    )

    code = _run(fake, "--", sys.executable, str(probe))

    out = capsys.readouterr()
    assert code == 0
    assert "mot de passe présent : True" in out.out
    assert "mot de passe administrateur absent : True" in out.out
    # Même si la commande de contrôle affichait le mot de passe, l'outil le masque.
    assert "retour du mot de passe : ***" in out.out
    user = fake.users[USERNAME]
    assert fake.credentials[user["id"]] == []  # retiré après la commande, pas avant


def test_le_mot_de_passe_existe_encore_pendant_la_commande_de_controle(
    admin_env, capsys, tmp_path, monkeypatch
):
    """La commande de contrôle (par exemple une connexion dans un navigateur) doit pouvoir se
    connecter : le mot de passe n'est retiré qu'après elle."""
    fake = FakeStaging()
    seen = {}
    real_run = owner.subprocess.run

    def spy(cmd, **kwargs):
        seen["credentials_during"] = list(fake.credentials[f"id-{USERNAME}"])
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(owner.subprocess, "run", spy)

    assert _run(fake, "--", sys.executable, "-c", "print('ok')") == 0

    assert len(seen["credentials_during"]) == 1


def test_une_commande_de_controle_en_echec_fait_echouer_et_retire_quand_meme_le_mot_de_passe(
    admin_env, capsys
):
    fake = FakeStaging()

    assert _run(fake, "--", sys.executable, "-c", "import sys; sys.exit(3)") == 1

    user = fake.users[USERNAME]
    assert fake.credentials[user["id"]] == []
    assert user["requiredActions"] == ["UPDATE_PASSWORD"]
    assert "commande de contrôle" in capsys.readouterr().err
