"""Jeu de données de démonstration du staging (scripts/seed_staging_demo.py), face à une fausse
API en mémoire, sans réseau.

Ce que ces tests prouvent : sans `--yes` rien n'est écrit, aucune suppression n'est jamais émise,
toute valeur est déclarée « simulated » (jamais « measured »), tout nom porte « DÉMO — », le site
archivé n'est archivé qu'après l'alarme et la valeur de son équipement, un second passage ne crée
aucun doublon de structure, et ni le mot de passe ni le jeton n'apparaissent dans la sortie.
"""

import json
import os
import uuid
from urllib.parse import parse_qs

import httpx
import pytest

import scripts.seed_staging_demo as seed

PASSWORD = "mot-de-passe-de-demo-qui-ne-doit-jamais-apparaitre"
TOKEN = "jeton-de-demo-qui-ne-doit-jamais-apparaitre"


class FakeStaging:
    """Assez de Keycloak et d'API pour les routes que l'outil appelle."""

    def __init__(self, *, roles=("admin_tenant",), fail_on: str | None = None):
        self.roles = list(roles)
        self.fail_on = fail_on
        self.sites: list[dict] = []
        self.locations: list[dict] = []
        self.points: list[dict] = []
        self.measurements: list[dict] = []
        self.alarms: list[dict] = []
        self.calls: list[tuple[str, str]] = []

    @property
    def writes(self) -> list[tuple[str, str]]:
        return [
            c for c in self.calls if c[0] != "GET" and not c[1].endswith("/openid-connect/token")
        ]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        self.calls.append((method, path))
        if path.endswith("/openid-connect/token"):
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if form.get("password") != PASSWORD:
                return httpx.Response(401, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": TOKEN})
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401)
        if self.fail_on and f"{method} {path}" == self.fail_on:
            return httpx.Response(409, json={"code": "SITE_NAME_CONFLICT", "detail": "SECRET-BODY"})
        body = json.loads(request.content) if request.content else {}
        params = request.url.params

        if path == "/me":
            return httpx.Response(
                200, json={"roles": self.roles, "tenant_name": "Client de démo", "username": "u"}
            )
        if path == "/sites" and method == "GET":
            return httpx.Response(200, json=self.sites)
        if path == "/sites" and method == "POST":
            site = {"id": str(uuid.uuid4()), "name": body["name"], "archived_at": None}
            self.sites.append(site)
            return httpx.Response(201, json=site)
        if path.startswith("/sites/") and path.endswith("/archive"):
            site_id = path.split("/")[2]
            for site in self.sites:
                if site["id"] == site_id:
                    site["archived_at"] = "2026-10-24T10:00:00+00:00"
            for location in self.locations:
                if location["site_id"] == site_id and not location["archived_at"]:
                    location["archived_at"] = "2026-10-24T10:00:00+00:00"
            return httpx.Response(200, json={"id": site_id})
        if path == "/functional-locations" and method == "GET":
            return httpx.Response(200, json=self.locations)
        if path == "/functional-locations" and method == "POST":
            location = {
                "id": str(uuid.uuid4()),
                "site_id": body["site_id"],
                "code": body["code"],
                "name": body["name"],
                "archived_at": None,
            }
            self.locations.append(location)
            return httpx.Response(201, json=location)
        if path == "/points" and method == "GET":
            wanted = params["functional_location_id"]
            return httpx.Response(
                200, json=[p for p in self.points if p["functional_location_id"] == wanted]
            )
        if path == "/points" and method == "POST":
            point = {"id": str(uuid.uuid4()), **body, "mapping_status": "proposed"}
            self.points.append(point)
            return httpx.Response(201, json=point)
        if path.startswith("/points/") and path.endswith("/validate"):
            point_id = path.split("/")[2]
            point = next(p for p in self.points if p["id"] == point_id)
            point["mapping_status"] = "validated"
            return httpx.Response(200, json=point)
        if path == "/measurements" and method == "POST":
            self.measurements.append(body)
            return httpx.Response(201, json=body)
        if path == "/alarms" and method == "GET":
            return httpx.Response(200, json=self.alarms)
        if path == "/alarms" and method == "POST":
            alarm = {"id": str(uuid.uuid4()), **body}
            self.alarms.append(alarm)
            return httpx.Response(201, json=alarm)
        return httpx.Response(404, json={"code": "ROUTE_INCONNUE"})


@pytest.fixture
def credentials(tmp_path):
    path = tmp_path / "identifiants.env"
    path.write_text(
        "KEYCLOAK_URL=https://keycloak.test\nKEYCLOAK_REALM=paios\nKEYCLOAK_CLIENT_ID=paios-api\n"
        f"STAGING_USERNAME=demo.admin\nSTAGING_PASSWORD={PASSWORD}\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)
    return path


def _run(fake, credentials, *extra, capsys=None):
    argv = ["--api-url", "https://api.test", "--credentials-file", str(credentials), *extra]
    return seed.main(argv, transport=httpx.MockTransport(fake))


def test_sans_yes_rien_n_est_ecrit_et_le_plan_est_affiche(credentials, capsys) -> None:
    fake = FakeStaging()

    assert _run(fake, credentials) == 0

    assert fake.writes == []
    out = capsys.readouterr().out
    assert "Lecture seule" in out
    assert "créer le site" in out
    assert fake.sites == [] and fake.measurements == [] and fake.alarms == []


def test_avec_yes_cree_toute_la_demonstration(credentials) -> None:
    fake = FakeStaging()

    assert _run(fake, credentials, "--yes") == 0

    assert sorted(s["name"] for s in fake.sites) == sorted([seed.ACTIVE_SITE, seed.ARCHIVED_SITE])
    assert sorted(location["code"] for location in fake.locations) == [
        "DEMO-ARC-01",
        "DEMO-PAC-01",
    ]
    assert len(fake.points) == 3
    assert all(p["mapping_status"] == "validated" for p in fake.points)
    assert {p["unit"] for p in fake.points} == {"Cel", "kW.h"}
    assert sorted((a["severity"]) for a in fake.alarms) == ["major", "warning"]


def test_tout_nom_est_etiquete_demo(credentials) -> None:
    fake = FakeStaging()
    _run(fake, credentials, "--yes")

    names = [s["name"] for s in fake.sites] + [location["name"] for location in fake.locations]
    names += [a["message"] for a in fake.alarms]
    assert names and all(name.startswith(seed.PREFIX) for name in names)


def test_toute_valeur_est_simulee_jamais_mesuree(credentials) -> None:
    fake = FakeStaging()
    _run(fake, credentials, "--yes")

    assert len(fake.measurements) == 3
    assert {m["origin"] for m in fake.measurements} == {"simulated"}
    assert {m["source"] for m in fake.measurements} == {seed.SOURCE}
    # L'unité est déclarée en code UCUM : l'API la refuse si elle diffère de celle du point.
    assert {m["unit"] for m in fake.measurements} == {"Cel", "kW.h"}


def test_le_site_archive_ne_l_est_qu_apres_l_alarme_et_la_valeur_de_son_equipement(
    credentials,
) -> None:
    fake = FakeStaging()
    _run(fake, credentials, "--yes")

    steps = [f"{m} {p}" for m, p in fake.calls]
    archive = next(i for i, step in enumerate(steps) if step.endswith("/archive"))
    last_alarm = max(i for i, step in enumerate(steps) if step == "POST /alarms")
    last_measure = max(i for i, step in enumerate(steps) if step == "POST /measurements")
    assert archive > last_alarm and archive > last_measure
    archived = next(s for s in fake.sites if s["name"] == seed.ARCHIVED_SITE)
    assert archived["archived_at"] is not None
    # La cascade a archivé l'équipement, qui garde son alarme ouverte.
    arc = next(loc for loc in fake.locations if loc["code"] == "DEMO-ARC-01")
    assert arc["archived_at"] is not None
    assert any(a["functional_location_id"] == arc["id"] for a in fake.alarms)


def test_un_second_passage_ne_cree_aucun_doublon_de_structure(credentials) -> None:
    fake = FakeStaging()
    _run(fake, credentials, "--yes")
    structure = (len(fake.sites), len(fake.locations), len(fake.points), len(fake.alarms))
    archives = [c for c in fake.calls if c[1].endswith("/archive")]

    assert _run(fake, credentials, "--yes") == 0

    assert (len(fake.sites), len(fake.locations), len(fake.points), len(fake.alarms)) == structure
    assert [c for c in fake.calls if c[1].endswith("/archive")] == archives  # pas de 2e archivage
    # Le site actif reçoit un nouveau relevé simulé (rafraîchissement) ; l'archivé n'est pas touché.
    assert len(fake.measurements) == 3 + 2


def test_aucune_suppression_n_est_jamais_emise(credentials) -> None:
    fake = FakeStaging()
    _run(fake, credentials, "--yes")
    _run(fake, credentials, "--yes")

    assert {method for method, _ in fake.calls} <= {"GET", "POST"}


def test_ni_mot_de_passe_ni_jeton_dans_la_sortie_ni_dans_le_resume(
    credentials, capsys, tmp_path
) -> None:
    fake = FakeStaging()
    out_file = tmp_path / "resume.json"

    assert _run(fake, credentials, "--yes", "--out", str(out_file)) == 0

    printed = capsys.readouterr()
    for secret in (PASSWORD, TOKEN):
        assert secret not in printed.out + printed.err
        assert secret not in out_file.read_text(encoding="utf-8")
    summary = json.loads(out_file.read_text(encoding="utf-8"))
    assert summary["target"]["tenant_name"] == "Client de démo"
    assert summary["archived"]


def test_un_compte_sans_droit_de_gestion_est_refuse_avant_toute_ecriture(
    credentials, capsys
) -> None:
    fake = FakeStaging(roles=("technicien",))

    assert _run(fake, credentials, "--yes") == 1

    assert fake.writes == []
    assert "ne peut pas gérer le registre" in capsys.readouterr().err


def test_une_erreur_de_l_api_cite_le_code_http_et_le_code_jamais_le_corps(
    credentials, capsys
) -> None:
    fake = FakeStaging(fail_on="POST /sites")

    assert _run(fake, credentials, "--yes") == 1

    err = capsys.readouterr().err
    assert "HTTP 409" in err and "SITE_NAME_CONFLICT" in err
    assert "SECRET-BODY" not in err


def test_un_fichier_d_identifiants_trop_ouvert_est_refuse(credentials, capsys) -> None:
    os.chmod(credentials, 0o644)
    fake = FakeStaging()

    assert _run(fake, credentials, "--yes") == 1

    assert fake.calls == []  # aucun appel réseau, pas même le jeton
    assert "droits trop larges" in capsys.readouterr().err


def test_un_mot_de_passe_refuse_par_keycloak_arrete_sans_le_citer(tmp_path, capsys) -> None:
    path = tmp_path / "mauvais.env"
    path.write_text(
        "KEYCLOAK_URL=https://keycloak.test\nKEYCLOAK_REALM=paios\nKEYCLOAK_CLIENT_ID=paios-api\n"
        "STAGING_USERNAME=demo.admin\nSTAGING_PASSWORD=autre-mot-de-passe-confidentiel\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)
    fake = FakeStaging()

    assert _run(fake, path, "--yes") == 1

    printed = capsys.readouterr()
    assert "autre-mot-de-passe-confidentiel" not in printed.out + printed.err
    assert fake.writes == []
