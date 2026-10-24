"""Virtual Asset (ADR 017 §2.1, Virtual Commissioning Lab) : peuple le
registre avec un site, un bâtiment et un ou plusieurs équipements virtuels
(un par profil du Virtual Protocol Adapter, `app/connectors/virtual_telemetry.py`),
points déjà validés inclus.

Chaque équipement traverse exactement le même chemin de création que la
saisie manuelle ou l'import IFC (`app.spatial.create_space`,
`app.assets.create_functional_location`, `app.points.create_point`) : jamais
un second modèle de registre pour les actifs virtuels, conforme à la
décision « zéro duplication » de l'ADR 017.

Isolation (ADR 017 §7) : un tenant dédié (« Virtual Commissioning Lab »,
slug `virtual-lab`), toujours distinct du tenant de démonstration
(`scripts/seed_demo_equipment.py`) et de tout tenant client réel.

Idempotent : rejouer ce script sur un site déjà créé (même `--site-name`) ne
duplique ni le site, ni le bâtiment, ni un équipement déjà présent (recherché
par site + code), ni un point déjà présent (recherché par code), ni une règle
FDD déjà active, ni un état souhaité déjà ouvert, ni la relation dependsOn
ci-dessous. Un appareil Edge déjà provisionné n'est en revanche jamais
re-provisionné : son secret n'est pas recalculable (voir
`app.devices.provision_device`) — ce script l'ignore alors et le signale,
sans rien casser.

Câblage complet (02/10/2026, demande explicite de Mohamed : « le simulateur
doit alimenter exactement la même chaîne que les futurs équipements réels »)
— chaque brique ci-dessous est une entrée dans le même moteur que pour un
équipement réel, jamais un second chemin :
- Règles FDD par défaut par profil (`_default_alarm_rules`) : seuil,
  divergence à l'état souhaité, corrélation à deux points
  (`simultaneous_heating_cooling`, le seul type multi-points du moteur) et
  projection de tendance — chacune pensée pour un scénario de panne déjà
  déclenchable (`app.connectors.virtual_telemetry.list_failure_scenarios`).
  `short_cycling` reste hors de ce câblage : aucun mécanisme d'oscillation
  marche/arrêt n'existe encore dans le simulateur (DEFER déjà documenté,
  feature-benchmark-matrix.md, non bloquant).
- Un état souhaité sur le volet d'air neuf de chaque CTA, nécessaire à la
  règle de divergence et au scénario `economiseur_bloque`.
- Un point commandable par pompe (`_ensure_commandable_relay`), strictement
  réservé au device_type `simulated_relay` (CLAUDE.md, exception scopée à la
  règle non négociable 1) : seul point du labo virtuel sur lequel
  `POST /commands` accepte une commande, toujours en Shadow/Dry Run, jamais
  vers un équipement réel.
- Une relation `dependsOn` entre une pompe et le groupe froid qu'elle dessert
  (si les deux sont créés dans le même appel), pour exercer l'analyse
  d'impact (`GET /graph/nodes/{id}/impact`) avec des données réalistes.
Alarmes, chronologie et ordres de travail ne sont volontairement pas
seedés séparément : ce sont des vues pures ou des effets automatiques déjà
câblés (`app.rules._escalate`) qui apparaissent dès qu'un scénario de panne
est joué par `scripts/virtual_commissioning_daemon.py` — jamais une donnée
inventée en plus de la télémétrie.

Script de développement/laboratoire uniquement, à l'image de
`scripts/seed_demo_equipment.py` : pas d'authentification, écrit directement
en base.

Utilisation, depuis services/api, environnement virtuel activé :
    python scripts/seed_virtual_site.py --profile cta --profile groupe_froid
    python scripts/seed_virtual_site.py --site-name "Site virtuel 2" --profile vrv_drv
"""

import argparse
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.assets import create_functional_location
from app.config_versions import activate_version, create_version
from app.connectors.device_mapping import MODBUS_DEVICE_MAPPING
from app.connectors.virtual_telemetry import VirtualPointSpec, list_profiles, profile_points
from app.db import engine
from app.desired_states import declare_desired_state
from app.devices import DeviceConflict, provision_device
from app.graph import create_relation, list_node_relations
from app.points import PointConflict, create_point, decide_point
from app.rules import ALARM_RULE
from app.spatial import create_space
from app.tenancy import set_tenant_context

_PROPOSED_BY = "systeme:virtual-lab"
_APPROVED_BY = "systeme:virtual-lab-approbation"

# Point commandable (jamais généré par le Virtual Protocol Adapter : voir
# _ensure_commandable_relay ci-dessous) — mêmes classe et type que la seule
# commande déjà autorisée par la règle non négociable 1 (on_off_command,
# app/point_vocabulary.py).
_RELAY_POINT_SPEC = VirtualPointSpec(
    "commande_marche_forcee", "Commande marche forcée (Shadow/Dry Run)", "on_off_command", "boolean"
)

TENANT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TENANT_NAME = "Virtual Commissioning Lab"
TENANT_SLUG = "virtual-lab"

_CREATED_BY = "seed_virtual_site.py"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _ensure_tenant(connection: Connection) -> None:
    connection.execute(
        text(
            "INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": TENANT_ID, "name": TENANT_NAME, "slug": TENANT_SLUG},
    )


def _ensure_site(connection: Connection, *, name: str) -> uuid.UUID:
    existing = connection.execute(
        text("SELECT id FROM sites WHERE tenant_id = :tenant_id AND name = :name"),
        {"tenant_id": TENANT_ID, "name": name},
    ).scalar()
    if existing:
        return existing
    site_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO sites (id, tenant_id, name, timezone) "
            "VALUES (:id, :tenant_id, :name, 'UTC')"
        ),
        {"id": site_id, "tenant_id": TENANT_ID, "name": name},
    )
    return site_id


def _ensure_building(connection: Connection, *, site_id: uuid.UUID) -> uuid.UUID:
    existing = connection.execute(
        text(
            "SELECT id FROM spaces WHERE site_id = :site_id AND code = 'BAT-VIRTUEL' "
            "AND valid_to IS NULL"
        ),
        {"site_id": site_id},
    ).scalar()
    if existing:
        return existing
    return create_space(
        connection,
        tenant_id=TENANT_ID,
        site_id=site_id,
        parent_id=None,
        space_type="building",
        code="BAT-VIRTUEL",
        name="Bâtiment virtuel",
        valid_from=datetime.now(UTC),
    )


def _ensure_functional_location(
    connection: Connection, *, site_id: uuid.UUID, space_id: uuid.UUID, code: str, name: str
) -> uuid.UUID:
    existing = connection.execute(
        text("SELECT id FROM functional_locations WHERE site_id = :site_id AND code = :code"),
        {"site_id": site_id, "code": code},
    ).scalar()
    if existing:
        return existing
    return create_functional_location(
        connection,
        tenant_id=TENANT_ID,
        site_id=site_id,
        parent_id=None,
        code=code,
        name=name,
        kind="equipment",
        space_id=space_id,
        created_by=_CREATED_BY,
    )


def _ensure_point(
    connection: Connection, *, location_id: uuid.UUID, code: str, spec: Any
) -> uuid.UUID:
    existing = connection.execute(
        text("SELECT id FROM points WHERE code = :code"), {"code": code}
    ).scalar()
    if existing:
        return existing
    try:
        point_id = create_point(
            connection,
            tenant_id=TENANT_ID,
            code=code,
            name=spec.name,
            value_type=spec.value_type,
            created_by=_CREATED_BY,
            point_class=spec.point_class,
            unit=spec.unit,
            functional_location_id=location_id,
        )
    except PointConflict:
        # Course avec un autre processus, ou code déjà pris autrement :
        # la vérité reste la base, jamais une hypothèse.
        return connection.execute(
            text("SELECT id FROM points WHERE code = :code"), {"code": code}
        ).scalar()
    decide_point(connection, point_id=point_id, decision="validated")
    return point_id


def _provision_virtual_device(
    connection: Connection, *, site_id: uuid.UUID, device_id: str
) -> str | None:
    """None si l'appareil existe déjà (secret non récupérable, par
    conception — voir app.devices.provision_device)."""
    existing = connection.execute(
        text("SELECT 1 FROM edge_devices WHERE tenant_id = :tenant_id AND device_id = :device_id"),
        {"tenant_id": TENANT_ID, "device_id": device_id},
    ).scalar()
    if existing:
        return None
    try:
        _, secret = provision_device(
            connection,
            tenant_id=TENANT_ID,
            device_id=device_id,
            created_by=_CREATED_BY,
            site_id=site_id,
        )
    except DeviceConflict:
        return None
    return secret


def _ensure_alarm_rule(
    connection: Connection, *, subject_key: str, content: dict[str, Any]
) -> None:
    """Idempotent : une règle déjà active pour cette clé n'est jamais
    redoublée en rejouant le script. `ALARM_RULE` exige deux personnes
    distinctes (`app/config_versions.py`, `requires_second_person=True`) —
    deux acteurs système distincts, jamais le même, pour rester cohérent
    avec la règle qui s'appliquerait à une vraie proposition humaine."""
    existing = connection.execute(
        text(
            "SELECT 1 FROM config_versions WHERE config_type = :type "
            "AND subject_key = :key AND status = 'active'"
        ),
        {"type": ALARM_RULE, "key": subject_key},
    ).scalar()
    if existing:
        return
    version_id = create_version(
        connection,
        tenant_id=TENANT_ID,
        config_type=ALARM_RULE,
        subject_key=subject_key,
        content=content,
        author=_PROPOSED_BY,
        reason="Virtual Commissioning Lab : règle FDD par défaut du profil",
    )
    activate_version(
        connection, version_id=version_id, activated_by=_APPROVED_BY, activated_at=datetime.now(UTC)
    )


def _default_alarm_rules(profile: str, points: dict[str, str]) -> list[tuple[str, dict[str, Any]]]:
    """[(suffixe de clé, contenu)] pour les règles FDD par défaut de ce
    profil — seulement là où un scénario de panne dédié existe déjà
    (app/connectors/virtual_telemetry.py), jamais une règle sur chaque
    profil « au cas où ». `short_cycling` reste volontairement absent ici :
    aucun scénario d'oscillation marche/arrêt n'existe encore dans le
    simulateur (DEFER déjà documenté, feature-benchmark-matrix.md, non
    bloquant)."""
    if profile == "cta":
        return [
            (
                "correlation",
                {
                    "kind": "simultaneous_heating_cooling",
                    "heating_point_id": points["vanne_chaude"],
                    "cooling_point_id": points["vanne_froide"],
                    "heating_threshold": 20,
                    "cooling_threshold": 20,
                    "severity": "major",
                    "title": "Chauffage et refroidissement actifs en même temps",
                    "recommended_action": "Vérifier les vannes et la régulation de la CTA.",
                    "create_work_order": True,
                },
            ),
            (
                "projection",
                {
                    "kind": "trend_projection",
                    "point_id": points["t_depart"],
                    "operator": ">",
                    "threshold": 28.0,
                    "window_minutes": 60,
                    "horizon_minutes": 180,
                    "severity": "warning",
                    "title": "Dérive du capteur de température de départ",
                    "recommended_action": "Planifier le remplacement du capteur.",
                },
            ),
            (
                "divergence",
                {
                    "kind": "desired_state_divergence",
                    "point_id": points["volet_air_neuf"],
                    "tolerance": 15,
                    "severity": "warning",
                    "title": "Volet d'air neuf : écart à l'état souhaité",
                    "recommended_action": "Vérifier le moteur du volet d'air neuf.",
                },
            ),
        ]
    if profile == "groupe_froid":
        return [
            (
                "seuil",
                {
                    "kind": "threshold",
                    "point_id": points["t_eau_glacee_retour"],
                    "operator": ">",
                    "threshold": 18.0,
                    "severity": "major",
                    "title": "Eau glacée retour anormalement chaude",
                    "recommended_action": "Vérifier la charge et le groupe froid.",
                    "create_work_order": True,
                },
            ),
            (
                "projection",
                {
                    "kind": "trend_projection",
                    "point_id": points["t_eau_glacee_depart"],
                    "operator": ">",
                    "threshold": 11.0,
                    "window_minutes": 60,
                    "horizon_minutes": 180,
                    "severity": "warning",
                    "title": "Dérive de l'échangeur (encrassement progressif)",
                    "recommended_action": "Planifier un nettoyage de l'échangeur.",
                },
            ),
        ]
    if profile == "pompe":
        return [
            (
                "seuil",
                {
                    "kind": "threshold",
                    "point_id": points["pression_refoulement"],
                    "operator": "<",
                    "threshold": 1.0,
                    "severity": "major",
                    "title": "Pression de refoulement anormalement basse",
                    "recommended_action": "Vérifier l'amorçage et le fonctionnement de la pompe.",
                    "create_work_order": True,
                },
            ),
            (
                "projection",
                {
                    "kind": "trend_projection",
                    "point_id": points["puissance_absorbee"],
                    "operator": ">",
                    "threshold": 7.5,
                    "window_minutes": 60,
                    "horizon_minutes": 180,
                    "severity": "warning",
                    "title": "Dérive de la puissance absorbée (usure progressive)",
                    "recommended_action": "Planifier une inspection des roulements.",
                },
            ),
        ]
    return []


def _ensure_desired_state(
    connection: Connection, *, point_id: uuid.UUID, value: float, reason: str
) -> None:
    """Idempotent : un état souhaité déjà déclaré et toujours ouvert n'est
    jamais redéclaré en rejouant le script."""
    existing = connection.execute(
        text("SELECT 1 FROM desired_states WHERE point_id = :point_id AND valid_to IS NULL"),
        {"point_id": point_id},
    ).scalar()
    if existing:
        return
    declare_desired_state(
        connection,
        tenant_id=TENANT_ID,
        point_id=point_id,
        value=value,
        valid_from=datetime.now(UTC) - timedelta(days=1),
        reason=reason,
        created_by=_CREATED_BY,
    )


def _ensure_commandable_relay(
    connection: Connection, *, location_id: uuid.UUID, point_code_prefix: str
) -> uuid.UUID:
    """Point commandable, strictement réservé au Shadow/Dry Run (ADR 017
    §4, CLAUDE.md règle non négociable 1, exception scopée au seul
    device_type "simulated_relay") : jamais un point du profil simulé
    lui-même, qui reste un capteur jamais pilotable."""
    point_id = _ensure_point(
        connection,
        location_id=location_id,
        code=f"{point_code_prefix}.commande_marche_forcee",
        spec=_RELAY_POINT_SPEC,
    )
    existing = connection.execute(
        text(
            "SELECT 1 FROM config_versions WHERE config_type = :type "
            "AND subject_key = :key AND status = 'active'"
        ),
        {"type": MODBUS_DEVICE_MAPPING, "key": str(location_id)},
    ).scalar()
    if not existing:
        version_id = create_version(
            connection,
            tenant_id=TENANT_ID,
            config_type=MODBUS_DEVICE_MAPPING,
            subject_key=str(location_id),
            content={
                "device_type": "simulated_relay",
                "host": "127.0.0.1",
                "port": 5020,
                "points": [{"point_id": str(point_id), "register_name": "relay_state"}],
            },
            author=_PROPOSED_BY,
            reason="Virtual Commissioning Lab : point commandable Shadow/Dry Run",
        )
        activate_version(
            connection,
            version_id=version_id,
            activated_by=_PROPOSED_BY,
            activated_at=datetime.now(UTC),
        )
    return point_id


def _ensure_depends_on(
    connection: Connection, *, subject_id: uuid.UUID, object_id: uuid.UUID
) -> None:
    """Idempotent : alimente l'analyse d'impact (GET /graph/nodes/{id}/impact,
    app/impact_analysis.py) avec une relation réaliste et stable entre deux
    équipements virtuels, jamais une seconde fois à chaque rejeu du script."""
    for relation in list_node_relations(connection, subject_id):
        if (
            relation["predicate"] == "dependsOn"
            and relation["subject_id"] == subject_id
            and relation["object_id"] == object_id
        ):
            return
    create_relation(
        connection,
        tenant_id=TENANT_ID,
        subject_id=subject_id,
        predicate="dependsOn",
        object_id=object_id,
        created_by=_CREATED_BY,
        valid_from=datetime.now(UTC),
        origin="manual",
    )


def seed(*, site_name: str, profiles: list[str]) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "tenant_id": str(TENANT_ID),
        "site_name": site_name,
        "equipment": [],
    }
    with engine.begin() as connection:
        _ensure_tenant(connection)
        set_tenant_context(connection, TENANT_ID)
        site_id = _ensure_site(connection, name=site_name)
        building_id = _ensure_building(connection, site_id=site_id)
        manifest["site_id"] = str(site_id)
        # Le tenant « Virtual Commissioning Lab » héberge plusieurs sites
        # virtuels (ADR 017 §7) : le code d'un équipement ("CTA-01") n'est
        # unique que DANS son site, exactement comme un vrai code terrain.
        # Les identifiants qui doivent rester uniques pour tout le tenant
        # (code de point, identifiant d'appareil Edge) intègrent donc le
        # site — sans quoi un deuxième site réutilisant "CTA-01" écraserait
        # silencieusement l'appareil et les points du premier (défaut
        # observé et corrigé pendant la mise au point de ce script).
        site_slug = _slugify(site_name)

        profile_counts: dict[str, int] = {}
        # Premier équipement de chaque profil rencontré dans cet appel : sert
        # uniquement à poser UNE relation dependsOn réaliste et stable, pour
        # alimenter l'analyse d'impact avec des données virtuelles (voir
        # _ensure_depends_on) — jamais un graphe de dépendances complet.
        first_location_by_profile: dict[str, uuid.UUID] = {}
        for profile in profiles:
            # Numérotation par profil (CTA-01, CTA-02, GROUPE_FROID-01…),
            # jamais un compteur global qui numéroterait le premier
            # équipement d'un nouveau profil "-02" simplement parce qu'un
            # autre profil le précède dans la liste.
            profile_counts[profile] = profile_counts.get(profile, 0) + 1
            index = profile_counts[profile]
            code = f"{profile.upper()}-{index:02d}"
            location_id = _ensure_functional_location(
                connection,
                site_id=site_id,
                space_id=building_id,
                code=code,
                name=f"{profile.replace('_', ' ').title()} virtuel {index:02d}",
            )
            points: dict[str, str] = {}
            for spec in profile_points(profile):
                point_code = f"{site_slug}.{code}.{spec.code_suffix}"
                point_id = _ensure_point(
                    connection, location_id=location_id, code=point_code, spec=spec
                )
                points[spec.code_suffix] = str(point_id)

            first_location_by_profile.setdefault(profile, location_id)

            # Règles FDD par défaut (02/10/2026, demande explicite de
            # Mohamed : « règles FDD multi-points », « alarmes, timeline,
            # maintenance ») — déclenchent de vraies alarmes et, pour celles
            # qui le demandent (create_work_order), de vrais ordres de
            # travail dès qu'un scénario de panne correspondant est joué par
            # le démon ; la chronologie les montre sans rien seeder de plus
            # (vue pure sur des données réelles).
            for suffix, content in _default_alarm_rules(profile, points):
                _ensure_alarm_rule(connection, subject_key=f"{code}-{suffix}", content=content)

            if profile == "cta":
                # Nécessaire pour que desired_state_divergence (ci-dessus)
                # ait un état souhaité à comparer, et pour que le scénario
                # de panne economiseur_bloque (déjà existant) produise un
                # vrai constat dès le premier relevé du démon.
                _ensure_desired_state(
                    connection,
                    point_id=uuid.UUID(points["volet_air_neuf"]),
                    value=50.0,
                    reason="Modulation libre-refroidissement attendue (Virtual Commissioning Lab)",
                )
            if profile == "pompe":
                # Seul point commandable du labo virtuel (02/10/2026, demande
                # explicite de Mohamed : « commandes uniquement en DRY_RUN /
                # SHADOW ») — jamais un point du profil simulé lui-même.
                relay_point_id = _ensure_commandable_relay(
                    connection, location_id=location_id, point_code_prefix=f"{site_slug}.{code}"
                )
                points["commande_marche_forcee"] = str(relay_point_id)

            device_id = f"virtual-{site_slug}-{code.lower()}"
            secret = _provision_virtual_device(connection, site_id=site_id, device_id=device_id)

            manifest["equipment"].append(
                {
                    "code": code,
                    "profile": profile,
                    "functional_location_id": str(location_id),
                    "device_id": device_id,
                    "device_secret": secret,  # None si déjà provisionné auparavant
                    "points": points,
                }
            )

        # Relation réaliste (une pompe de circulation dépend du groupe froid
        # qu'elle dessert) — seulement si les deux existent dans cet appel,
        # jamais devinée pour des équipements sans rapport.
        if "pompe" in first_location_by_profile and "groupe_froid" in first_location_by_profile:
            _ensure_depends_on(
                connection,
                subject_id=first_location_by_profile["pompe"],
                object_id=first_location_by_profile["groupe_froid"],
            )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site-name", default="Site virtuel 1")
    parser.add_argument(
        "--profile",
        action="append",
        dest="profiles",
        choices=list_profiles(),
        help="Répétable. Par défaut : les sept profils.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Fichier de sortie (par défaut : virtual_site_<site>.json)",
    )
    args = parser.parse_args()
    args.profiles = args.profiles or list_profiles()
    return args


def main() -> None:
    args = _parse_args()
    manifest = seed(site_name=args.site_name, profiles=args.profiles)

    manifest_path = args.manifest or Path(
        f"virtual_site_{args.site_name.lower().replace(' ', '_')}.json"
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    freshly_provisioned = [e for e in manifest["equipment"] if e["device_secret"]]
    already_there = [e for e in manifest["equipment"] if not e["device_secret"]]
    print(f"Site virtuel « {args.site_name} » prêt : {len(manifest['equipment'])} équipement(s).")
    if freshly_provisioned:
        print(
            f"{len(freshly_provisioned)} appareil(s) virtuel(s) nouvellement provisionné(s) "
            f"— secret écrit UNE SEULE FOIS dans {manifest_path} (à conserver)."
        )
    if already_there:
        codes = ", ".join(e["code"] for e in already_there)
        print(f"Déjà provisionné auparavant (secret non réécrit) : {codes}")
    print(f"Manifeste : {manifest_path}")


if __name__ == "__main__":
    main()
