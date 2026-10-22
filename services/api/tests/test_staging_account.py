"""Compte de test du staging (scripts/staging_account.py) et lanceur de mesure authentifiée
(scripts/staging_probe.py) : face à un faux Keycloak, sans réseau.

Ce que ces tests prouvent : le mot de passe du compte et le jeton ne sont jamais affichés,
le fichier d'identifiants est créé en 0600, le compte n'a que le rôle « technicien », le jeton
passe au processus enfant par l'environnement (jamais par les arguments), et un fichier trop
ouvert est refusé.
"""

import json
import stat
import subprocess
from urllib.parse import parse_qs

import httpx
import pytest

import scripts.staging_account as account
import scripts.staging_probe as probe

ADMIN_PASSWORD = "mot-de-passe-admin-de-test-1234567890"
ADMIN_TOKEN = "jeton-admin-de-test"
USER_TOKEN = "jeton-technicien-de-test-qui-ne-doit-jamais-apparaitre"
TENANT = "11111111-1111-1111-1111-111111111111"


class FakeKeycloak:
    """Assez de Keycloak pour les routes que l'outil appelle, avec un journal des appels."""

    def __init__(self, *, admin_password: str = ADMIN_PASSWORD, with_demo_users: bool = False):
        self.admin_password = admin_password
        self.users: dict[str, dict] = {}
        self.passwords: dict[str, str] = {}
        self.roles_given: dict[str, list[str]] = {}
        self.calls: list[tuple[str, str]] = []
        if with_demo_users:
            for name in account.DEMO_USERS:
                self.users[name] = {"id": f"id-{name}", "username": name, "enabled": True}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        self.calls.append((method, path))
        if path == "/realms/master/protocol/openid-connect/token":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if form.get("password") != self.admin_password:
                return httpx.Response(401, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": ADMIN_TOKEN})
        if request.headers.get("Authorization") != f"Bearer {ADMIN_TOKEN}":
            return httpx.Response(401)
        if path == "/admin/realms/paios/users" and method == "GET":
            wanted = request.url.params["username"]
            return httpx.Response(
                200, json=[u for u in self.users.values() if u["username"] == wanted]
            )
        if path == "/admin/realms/paios/users" and method == "POST":
            body = json.loads(request.content)
            user = {
                "id": f"id-{body['username']}",
                "username": body["username"],
                "enabled": body["enabled"],
                "attributes": body["attributes"],
            }
            self.users[body["username"]] = user
            self.passwords[user["id"]] = body["credentials"][0]["value"]
            return httpx.Response(201)
        if path == "/admin/realms/paios/roles/technicien":
            return httpx.Response(200, json={"id": "role-tech", "name": "technicien"})
        parts = path.split("/")  # ['', 'admin', 'realms', 'paios', 'users', <id>, <action>...]
        if len(parts) >= 6 and parts[4] == "users":
            user = next((u for u in self.users.values() if u["id"] == parts[5]), None)
            if user is None:
                return httpx.Response(404)
            if len(parts) == 6 and method == "PUT":
                user.update(json.loads(request.content))
                return httpx.Response(204)
            if parts[6:7] == ["reset-password"]:
                self.passwords[user["id"]] = json.loads(request.content)["value"]
                return httpx.Response(204)
            if parts[6:7] == ["role-mappings"]:
                self.roles_given.setdefault(user["id"], []).extend(
                    r["name"] for r in json.loads(request.content)
                )
                return httpx.Response(204)
        return httpx.Response(404)


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", ADMIN_PASSWORD)


def _run(fake, tmp_path, *extra, command="create"):
    credentials = tmp_path / "config" / "staging-loadtest.env"
    argv = [
        command,
        "--keycloak-url",
        "https://keycloak.example.invalid",
        "--credentials-file",
        str(credentials),
        *extra,
    ]
    code = account.main(argv, transport=httpx.MockTransport(fake))
    return code, credentials


def test_create_writes_credentials_0600_and_prints_no_secret(admin_env, tmp_path, capsys):
    fake = FakeKeycloak()
    code, credentials = _run(fake, tmp_path)
    out = capsys.readouterr()

    assert code == 0
    mode = stat.S_IMODE(credentials.stat().st_mode)
    assert mode == 0o600
    assert stat.S_IMODE(credentials.parent.stat().st_mode) == 0o700
    stored = dict(line.split("=", 1) for line in credentials.read_text().splitlines())
    password = stored["STAGING_PASSWORD"]
    assert len(password) >= 32
    assert fake.passwords["id-loadtest.staging"] == password
    for text in (out.out, out.err):
        assert password not in text
        assert ADMIN_PASSWORD not in text
        assert ADMIN_TOKEN not in text


def test_account_only_gets_the_technician_role_and_the_tenant(admin_env, tmp_path):
    fake = FakeKeycloak()
    _run(fake, tmp_path, "--tenant-id", TENANT)

    assert fake.roles_given["id-loadtest.staging"] == ["technicien"]
    assert fake.users["loadtest.staging"]["attributes"]["tenant_id"] == [TENANT]


def test_create_is_idempotent_and_keeps_the_password(admin_env, tmp_path, capsys):
    fake = FakeKeycloak()
    _run(fake, tmp_path)
    first = fake.passwords["id-loadtest.staging"]
    capsys.readouterr()

    code, credentials = _run(fake, tmp_path)

    assert code == 0
    assert fake.passwords["id-loadtest.staging"] == first
    assert "existe déjà" in capsys.readouterr().out
    assert (
        dict(line.split("=", 1) for line in credentials.read_text().splitlines())[
            "STAGING_PASSWORD"
        ]
        == first
    )


def test_rotate_replaces_the_password_in_keycloak_and_in_the_file(admin_env, tmp_path):
    fake = FakeKeycloak()
    _run(fake, tmp_path)
    first = fake.passwords["id-loadtest.staging"]

    code, credentials = _run(fake, tmp_path, "--rotate")

    assert code == 0
    second = fake.passwords["id-loadtest.staging"]
    assert second != first
    assert (
        dict(line.split("=", 1) for line in credentials.read_text().splitlines())[
            "STAGING_PASSWORD"
        ]
        == second
    )
    assert stat.S_IMODE(credentials.stat().st_mode) == 0o600


def test_wrong_admin_password_fails_without_echoing_it(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "mauvais-mot-de-passe-admin")
    fake = FakeKeycloak()
    code, credentials = _run(fake, tmp_path)
    out = capsys.readouterr()

    assert code == 1
    assert "HTTP 401" in out.err
    assert "mauvais-mot-de-passe-admin" not in out.out + out.err
    assert not credentials.exists()


def test_invalid_tenant_is_refused_before_any_account_is_created(admin_env, tmp_path, capsys):
    fake = FakeKeycloak()
    code, credentials = _run(fake, tmp_path, "--tenant-id", "pas-un-uuid")

    assert code == 1
    assert fake.users == {}
    assert not credentials.exists()
    assert "Échec" in capsys.readouterr().err


def test_disable_demo_users_requires_confirmation(admin_env, tmp_path):
    fake = FakeKeycloak(with_demo_users=True)
    code, _ = _run(fake, tmp_path, command="disable-demo-users")

    assert code == 2
    assert fake.calls == []
    assert all(u["enabled"] for u in fake.users.values())


def test_disable_demo_users_disables_only_the_demo_accounts(admin_env, tmp_path, capsys):
    fake = FakeKeycloak(with_demo_users=True)
    _run(fake, tmp_path)  # crée le compte de test
    code, _ = _run(fake, tmp_path, "--yes", command="disable-demo-users")

    assert code == 0
    assert not fake.users["demo.technicien"]["enabled"]
    assert not fake.users["demo.admin"]["enabled"]
    assert fake.users["loadtest.staging"]["enabled"]
    assert "demo.technicien" in capsys.readouterr().out


# --- staging_probe ----------------------------------------------------------------------------


def _write_credentials(path, mode=0o600, **overrides):
    values = {
        "KEYCLOAK_URL": "https://keycloak.example.invalid",
        "KEYCLOAK_REALM": "paios",
        "KEYCLOAK_CLIENT_ID": "paios-api",
        "STAGING_USERNAME": "loadtest.staging",
        "STAGING_PASSWORD": "mot-de-passe-du-compte-de-test-0123456789",
        **overrides,
    }
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    path.chmod(mode)
    return values


def _token_transport(status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        assert request.url.path == "/realms/paios/protocol/openid-connect/token"
        assert form["grant_type"] == "password"
        assert form["client_id"] == "paios-api"
        if status != 200:
            return httpx.Response(status, json={"error": "invalid_grant"})
        return httpx.Response(200, json={"access_token": USER_TOKEN})

    return httpx.MockTransport(handler)


def test_probe_refuses_a_credentials_file_readable_by_others(tmp_path):
    path = tmp_path / "creds.env"
    _write_credentials(path, mode=0o644)

    with pytest.raises(probe.StagingProbeError, match="droits trop larges"):
        probe.load_credentials(path)


def test_probe_refuses_a_missing_or_incomplete_credentials_file(tmp_path):
    with pytest.raises(probe.StagingProbeError, match="introuvable"):
        probe.load_credentials(tmp_path / "absent.env")
    path = tmp_path / "creds.env"
    _write_credentials(path, STAGING_PASSWORD="")
    with pytest.raises(probe.StagingProbeError, match="STAGING_PASSWORD"):
        probe.load_credentials(path)


def test_probe_passes_the_token_through_the_child_environment_only(tmp_path, monkeypatch, capsys):
    path = tmp_path / "creds.env"
    values = _write_credentials(path)
    captured = {}

    def fake_run(command, env, check):
        captured["command"], captured["env"] = command, env
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    code = probe.main(
        [
            "--api-url",
            "https://api.example.invalid",
            "--credentials-file",
            str(path),
            "--allow-remote",
            "--",
            "--path",
            "/sync/interventions?limit=50",
            "--levels",
            "1,2",
        ],
        transport=_token_transport(),
    )
    out = capsys.readouterr()

    assert code == 0
    assert captured["env"]["LOAD_PROBE_TOKEN"] == USER_TOKEN
    command_line = " ".join(captured["command"])
    assert USER_TOKEN not in command_line
    assert values["STAGING_PASSWORD"] not in command_line
    assert "--allow-remote" in captured["command"]
    assert captured["command"][captured["command"].index("--base-url") + 1] == (
        "https://api.example.invalid"
    )
    assert captured["command"][-4:] == ["--path", "/sync/interventions?limit=50", "--levels", "1,2"]
    for text in (out.out, out.err):
        assert USER_TOKEN not in text
        assert values["STAGING_PASSWORD"] not in text


def test_probe_without_allow_remote_leaves_the_remote_refusal_to_load_probe(tmp_path, monkeypatch):
    path = tmp_path / "creds.env"
    _write_credentials(path)
    seen = {}
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda command, env, check: (
            seen.update(command=command) or subprocess.CompletedProcess(command, 2)
        ),
    )

    code = probe.main(
        [
            "--api-url",
            "https://api.example.invalid",
            "--credentials-file",
            str(path),
            "--",
            "--path",
            "/health",
        ],
        transport=_token_transport(),
    )

    assert "--allow-remote" not in seen["command"]
    assert code == 2


def test_probe_never_accepts_the_token_or_the_url_as_an_argument(tmp_path, capsys):
    path = tmp_path / "creds.env"
    _write_credentials(path)

    for forbidden in (
        ["--base-url", "https://autre"],
        ["--base-url=https://autre"],
        ["LOAD_PROBE_TOKEN=x"],
    ):
        code = probe.main(
            [
                "--api-url",
                "https://api.example.invalid",
                "--credentials-file",
                str(path),
                "--",
                *forbidden,
            ]
        )
        assert code == 2
    assert "Refusé" in capsys.readouterr().out


def test_probe_stops_cleanly_when_keycloak_refuses_the_token(tmp_path, monkeypatch, capsys):
    path = tmp_path / "creds.env"
    values = _write_credentials(path)
    monkeypatch.setattr(
        probe.subprocess, "run", lambda *a, **k: pytest.fail("aucune mesure sans jeton valide")
    )

    code = probe.main(
        [
            "--api-url",
            "https://api.example.invalid",
            "--credentials-file",
            str(path),
            "--",
            "--path",
            "/health",
        ],
        transport=_token_transport(status=401),
    )
    err = capsys.readouterr().err

    assert code == 1
    assert "HTTP 401" in err
    assert values["STAGING_PASSWORD"] not in err


def test_child_environment_replaces_any_inherited_token(monkeypatch):
    monkeypatch.setenv("LOAD_PROBE_TOKEN", "ancien-jeton")

    environment = probe.child_environment("nouveau-jeton")

    assert environment["LOAD_PROBE_TOKEN"] == "nouveau-jeton"


def test_une_option_inconnue_avant_le_separateur_est_refusee(tmp_path, capsys):
    """`--json-out` appartient à load_probe : placé avant `--`, il doit être refusé net, pas
    transmis de travers (le `--` restait alors dans les arguments et la mesure échouait de
    façon obscure)."""
    path = tmp_path / "creds.env"
    _write_credentials(path)

    with pytest.raises(SystemExit) as refus:
        probe.main(
            [
                "--api-url",
                "https://api.example.invalid",
                "--credentials-file",
                str(path),
                "--json-out",
                "rapport.json",
                "--",
                "--path",
                "/health",
            ]
        )

    assert refus.value.code == 2
    assert "--json-out" in capsys.readouterr().err


def test_tout_ce_qui_suit_le_separateur_est_transmis_tel_quel_sans_le_separateur() -> None:
    args, passthrough = probe._parse_args(
        ["--api-url", "https://a.example.invalid", "--", "--path", "/x", "--json-out", "r.json"]
    )

    assert args.api_url == "https://a.example.invalid"
    assert passthrough == ["--path", "/x", "--json-out", "r.json"]
