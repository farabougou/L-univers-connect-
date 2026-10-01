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
par site + code), ni un point déjà présent (recherché par code). Un appareil
Edge déjà provisionné n'est en revanche jamais re-provisionné : son secret
n'est pas recalculable (voir `app.devices.provision_device`) — ce script
l'ignore alors et le signale, sans rien casser.

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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.assets import create_functional_location
from app.connectors.virtual_telemetry import list_profiles, profile_points
from app.db import engine
from app.devices import DeviceConflict, provision_device
from app.points import PointConflict, create_point, decide_point
from app.spatial import create_space
from app.tenancy import set_tenant_context

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
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site-name", default="Site virtuel 1")
    parser.add_argument(
        "--profile",
        action="append",
        dest="profiles",
        choices=list_profiles(),
        help="Répétable. Par défaut : les six profils.",
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
