"""Jeu de données de démonstration du staging : fictif, étiqueté, jamais supprimé.

Pourquoi : valider à l'écran, sur le staging lui-même, ce que les tests et les captures locales
ne prouvent pas (tuiles d'alarmes, symboles d'unité, équipement archivé, valeur simulée).
Les données inventées uniquement en local ne sont jamais une validation du staging.

Ce que l'outil crée, avec le compte dont vous fournissez les identifiants (un rôle de gestion du
registre est nécessaire : responsable d'exploitation ou administrateur du client) :

- un site actif « DÉMO — Site de démonstration (données fictives) », avec un équipement
  `DEMO-PAC-01`, deux points validés (température de départ en °C, énergie en kWh), un relevé
  simulé pour chacun et une alarme d'avertissement ouverte ;
- un second site, « DÉMO — Ancien site archivé (données fictives) », avec un équipement
  `DEMO-ARC-01`, un point validé, un relevé simulé et une alarme majeure ouverte, puis le site est
  archivé : l'archivage en cascade archive l'équipement, ce qui valide ce comportement de bout en
  bout. L'alarme ouverte et la valeur de l'équipement archivé restent visibles, nommées « archivé ».

Garanties :
- tout nom commence par « DÉMO — » : personne ne peut prendre ces données pour de vraies ;
- toute valeur est déclarée `simulated` (jamais `measured`) et s'affiche comme valeur simulée ;
- aucune suppression : l'outil ne fait que créer et archiver (règle 3, rien n'est écrasé). Pour
  retirer la démonstration des listes, archivez les deux sites dans la console ;
- idempotent pour la structure (sites, équipements, points, alarmes) : relancer ne crée pas de
  doublon. Chaque exécution ajoute un relevé simulé daté de maintenant, ce qui rafraîchit les
  valeurs affichées « à jour » ;
- sans `--yes`, ne fait que lire et affiche le plan ; aucun jeton ni mot de passe n'est affiché
  ou écrit ; les erreurs citent le code HTTP et le code d'erreur de l'API, jamais un corps entier.

Les identifiants viennent d'un fichier hors du dépôt, aux droits 0600 (même format que celui de
`scripts/staging_account.py`) : KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID,
STAGING_USERNAME, STAGING_PASSWORD.

Usage (depuis services/api) :
    PYTHONPATH=. python scripts/seed_staging_demo.py \\
        --api-url https://API_STAGING --credentials-file ~/.config/paios/staging-seed.env
    PYTHONPATH=. python scripts/seed_staging_demo.py \\
        --api-url https://API_STAGING --credentials-file ... --yes --out demo-staging.json
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from scripts.staging_probe import StagingProbeError, fetch_token, load_credentials

PREFIX = "DÉMO — "
SOURCE = "seed-demo"
TIMEZONE = "Africa/Bamako"
MANAGE_ROLES = ("responsable_exploitation", "admin_tenant")

ACTIVE_SITE = f"{PREFIX}Site de démonstration (données fictives)"
ARCHIVED_SITE = f"{PREFIX}Ancien site archivé (données fictives)"

# (code d'équipement, nom, points) ; chaque point : code, nom, classe, unité UCUM, valeur simulée.
ACTIVE_EQUIPMENT = (
    "DEMO-PAC-01",
    f"{PREFIX}Pompe à chaleur (fictive)",
    (
        (
            "DEMO-PAC-01.TDEP",
            "Température départ eau",
            "supply_water_temperature_sensor",
            "Cel",
            41.2,
        ),
        ("DEMO-PAC-01.ENERGIE", "Énergie active totale", "energy_meter_reading", "kW.h", 1284.6),
    ),
)
ARCHIVED_EQUIPMENT = (
    "DEMO-ARC-01",
    f"{PREFIX}Groupe froid d'un site archivé (fictif)",
    (
        (
            "DEMO-ARC-01.TDEP",
            "Température départ eau",
            "supply_water_temperature_sensor",
            "Cel",
            38.4,
        ),
    ),
)
ACTIVE_ALARM = (
    "warning",
    f"{PREFIX}température de départ élevée (donnée fictive)",
)
ARCHIVED_ALARM = (
    "major",
    f"{PREFIX}perte de communication (donnée fictive)",
)


class SeedError(Exception):
    """Échec attendu : le message ne contient jamais de secret ni de corps de réponse."""


class Api:
    def __init__(self, client: httpx.Client, *, write: bool):
        self.client = client
        self.write = write
        self.plan: list[str] = []

    def get(self, path: str, **params):
        return self._check(self.client.get(path, params=params or None), f"GET {path}").json()

    def post(self, path: str, body: dict, *, describe: str):
        """Écrit seulement avec `--yes` ; sans lui, note l'étape dans le plan."""
        if not self.write:
            self.plan.append(describe)
            return None
        return self._check(self.client.post(path, json=body), f"POST {path}", ok=(200, 201)).json()

    @staticmethod
    def _check(response: httpx.Response, action: str, ok: tuple[int, ...] = (200,)):
        if response.status_code not in ok:
            code = ""
            try:
                code = f", code {response.json().get('code')}"
            except (ValueError, AttributeError):
                pass
            raise SeedError(f"{action} : HTTP {response.status_code}{code}")
        return response


def _find(rows: list[dict], **wanted) -> dict | None:
    return next((r for r in rows if all(r.get(k) == v for k, v in wanted.items())), None)


def ensure_site(api: Api, name: str, report: dict) -> dict | None:
    site = _find(api.get("/sites", include_archived="true"), name=name)
    if site:
        report["existing"].append(f"site « {name} »")
        return site
    created = api.post(
        "/sites",
        {"name": name, "timezone": TIMEZONE},
        describe=f"créer le site « {name} »",
    )
    if created:
        report["created"].append(f"site « {name} »")
    return created


def ensure_location(api: Api, site: dict | None, code: str, name: str, report: dict) -> dict | None:
    if site is None:  # lecture seule : rien n'existe encore
        api.plan.append(f"créer l'équipement {code}")
        return None
    rows = api.get("/functional-locations", include_archived="true")
    existing = _find(rows, site_id=site["id"], code=code)
    if existing:
        report["existing"].append(f"équipement {code}")
        return existing
    created = api.post(
        "/functional-locations",
        {"site_id": site["id"], "code": code, "name": name, "kind": "equipment"},
        describe=f"créer l'équipement {code}",
    )
    if created:
        report["created"].append(f"équipement {code}")
    return created


def ensure_point(api: Api, location: dict | None, spec: tuple, report: dict) -> dict | None:
    code, name, point_class, unit, _value = spec
    if location is None:
        api.plan.append(f"créer et valider le point {code}")
        return None
    points = api.get("/points", functional_location_id=location["id"])
    point = _find(points, code=code)
    if point is None:
        point = api.post(
            "/points",
            {
                "code": code,
                "name": name,
                "value_type": "number",
                "point_class": point_class,
                "unit": unit,
                "functional_location_id": location["id"],
                "expected_interval_seconds": 900,
            },
            describe=f"créer le point {code}",
        )
        if point:
            report["created"].append(f"point {code}")
    else:
        report["existing"].append(f"point {code}")
    if point and point.get("mapping_status") != "validated":
        point = api.post(
            f"/points/{point['id']}/validate",
            {"reason": "Point de démonstration fictif"},
            describe=f"valider le point {code}",
        )
        if point:
            report["created"].append(f"point {code} validé")
    return point


def post_simulated_value(api: Api, point: dict | None, spec: tuple, report: dict) -> None:
    code, _name, _class, unit, value = spec
    if point is None:
        api.plan.append(f"enregistrer un relevé simulé pour {code}")
        return
    created = api.post(
        "/measurements",
        {
            "point_id": point["id"],
            "value": value,
            "origin": "simulated",
            "source": SOURCE,
            "unit": unit,
            "measured_at": datetime.now(UTC).isoformat(),
        },
        describe=f"enregistrer un relevé simulé pour {code}",
    )
    if created:
        report["created"].append(f"relevé simulé {code} = {value} {unit}")


def ensure_alarm(api: Api, location: dict | None, spec: tuple, report: dict) -> None:
    severity, message = spec
    if location is None:
        api.plan.append(f"lever l'alarme « {message} »")
        return
    open_alarms = api.get("/alarms", condition_state="active")
    if _find(open_alarms, functional_location_id=location["id"], message=message):
        report["existing"].append(f"alarme « {message} »")
        return
    created = api.post(
        "/alarms",
        {"severity": severity, "message": message, "functional_location_id": location["id"]},
        describe=f"lever l'alarme « {message} »",
    )
    if created:
        report["created"].append(f"alarme « {message} »")


def seed_equipment(api: Api, site: dict | None, equipment: tuple, alarm: tuple, report: dict):
    code, name, point_specs = equipment
    location = ensure_location(api, site, code, name, report)
    for spec in point_specs:
        point = ensure_point(api, location, spec, report)
        post_simulated_value(api, point, spec, report)
    ensure_alarm(api, location, alarm, report)
    return location


def check_target(api: Api) -> dict:
    me = api.get("/me")
    roles = set(me.get("roles", []))
    if not roles & set(MANAGE_ROLES):
        raise SeedError(
            "ce compte ne peut pas gérer le registre (rôle responsable d'exploitation ou "
            "administrateur du client requis)"
        )
    return me


def run(api: Api) -> dict:
    report: dict = {"created": [], "existing": [], "archived": []}
    me = check_target(api)
    report["target"] = {"tenant_name": me.get("tenant_name"), "username": me.get("username")}

    active_site = ensure_site(api, ACTIVE_SITE, report)
    seed_equipment(api, active_site, ACTIVE_EQUIPMENT, ACTIVE_ALARM, report)

    archived_site = ensure_site(api, ARCHIVED_SITE, report)
    if archived_site and archived_site.get("archived_at"):
        # État final déjà atteint : rien à créer ni à archiver de nouveau.
        report["existing"].append("site archivé déjà archivé (rien à refaire)")
        return report
    seed_equipment(api, archived_site, ARCHIVED_EQUIPMENT, ARCHIVED_ALARM, report)
    if archived_site is None:
        api.plan.append(f"archiver le site « {ARCHIVED_SITE} » (ses équipements suivent)")
        return report
    archived = api.post(
        f"/sites/{archived_site['id']}/archive",
        {},
        describe=f"archiver le site « {ARCHIVED_SITE} »",
    )
    if archived:
        report["archived"].append(f"site « {ARCHIVED_SITE} » (et ses équipements, en cascade)")
    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--yes", action="store_true", help="Écrire (sinon : plan en lecture seule)")
    parser.add_argument("--out", type=Path, help="Résumé JSON (sans secret) à écrire")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    args = _parse_args(argv)
    try:
        credentials = load_credentials(args.credentials_file.expanduser())
        token = fetch_token(credentials, transport=transport)
        with httpx.Client(
            base_url=args.api_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
            transport=transport,
        ) as client:
            api = Api(client, write=args.yes)
            report = run(api)
    except (StagingProbeError, SeedError) as exc:
        print(f"Arrêt : {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        # Le type seul : le message d'une erreur réseau peut citer l'adresse demandée.
        print(f"Arrêt : API injoignable ({type(exc).__name__})", file=sys.stderr)
        return 1

    target = report["target"]
    print(f"Cible : client « {target['tenant_name']} », compte {target['username']}")
    if not args.yes:
        print("Lecture seule (ajoutez --yes pour écrire). Étapes qui seraient faites :")
        for step in api.plan:
            print(f"  - {step}")
        if not api.plan:
            print("  (rien : la démonstration existe déjà)")
        return 0
    for title, key in (("Créé", "created"), ("Déjà présent", "existing"), ("Archivé", "archived")):
        for item in report[key]:
            print(f"{title} : {item}")
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
