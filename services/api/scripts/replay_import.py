"""Replay Mode (ADR 017 §3, Virtual Commissioning Lab) : rejoue un export réel
anonymisé de GTB (CSV, format large) à travers le même chemin qu'une mesure
en direct (`app.telemetry.record_measurement`) — jamais un second chemin
d'ingestion, jamais une table parallèle. La traduction CSV → relevés est pure
(`app.replay_import`, testée séparément) ; ce script ne fait que la
résolution des points déjà enregistrés et l'écriture en base.

Les points visés par `--column` doivent déjà exister dans le registre (créés
à la main, par import IFC, ou par `scripts/seed_virtual_site.py` pour une
démonstration) : Replay Mode n'invente jamais un point, il nourrit ceux qui
existent déjà. Horodatage conservé tel quel (`measured_at`), import journalisé
comme reçu maintenant (`received_at`) — un relevé rejoué des mois après coup
reçoit honnêtement le drapeau d'arrivée tardive déjà existant
(`app.telemetry.LATE_ARRIVAL`), jamais maquillé en relevé récent.

**Conséquence volontaire, trouvée en vérifiant ce script contre une vraie
base** : un export vieux de plusieurs mois fait chuter le score de confiance
du point (`app.trust`, pénalité « relevés douteux ») sous le seuil requis par
les règles FDD (`MIN_TRUST_FOR_RULES`) — l'historique s'enregistre
correctement, mais la détection ne s'applique qu'une fois la confiance
rétablie (relevés assez récents ou assez nombreux). Ce n'est pas une
limite de Replay Mode à contourner : c'est la même protection qui empêche
déjà une règle de se fier à un capteur réel arrivé en retard. Pour valider
une règle FDD sur un export rejoué, choisir une fenêtre assez récente
(quelques heures, pas plusieurs mois) ou s'attendre à ce que la détection
n'apparaisse qu'après plusieurs relevés.

Anonymisation : responsabilité de la personne qui lance l'import (CLAUDE.md,
règle non négociable 9). La garde automatique (`app.replay_import`) n'est
qu'un filet de sécurité, jamais une garantie — elle ne dispense personne de
vérifier l'export avant de le fournir.

Usage :
    python scripts/replay_import.py --tenant <uuid> --csv export.csv \
        --timestamp-column "Horodatage" --timestamp-format "%Y-%m-%d %H:%M" \
        --column "T_Depart=CTA-01.t_depart" \
        --column "Vanne_Chaude=CTA-01.vanne_chaude" \
        [--timezone Europe/Paris] [--dry-run]

`--dry-run` traduit et valide le fichier sans rien écrire en base — pour
vérifier le mapping de colonnes avant un import réel.
"""

import argparse
import uuid
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.db import engine
from app.points import get_point
from app.replay_import import ReplayImportRefused, parse_replay_csv
from app.telemetry import MeasurementConflict, MeasurementRejected, record_measurement
from app.tenancy import set_tenant_context


def _resolve_point_id(connection, code: str) -> uuid.UUID:
    point_id = connection.execute(
        text("SELECT id FROM points WHERE code = :code"), {"code": code}
    ).scalar()
    if point_id is None:
        raise SystemExit(
            f"Point introuvable : {code!r}. Replay Mode n'invente jamais un point — "
            "le créer d'abord (console web, API, ou scripts/seed_virtual_site.py)."
        )
    return point_id


def _parse_column_mapping(pairs: list[str]) -> dict[str, str]:
    mapping = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--column attend COLONNE_CSV=CODE_POINT, reçu : {pair!r}")
        column, point_code = pair.split("=", 1)
        mapping[column] = point_code
    return mapping


def run(
    *,
    tenant_id: uuid.UUID,
    csv_path: Path,
    timestamp_column: str,
    timestamp_format: str,
    column_to_point_code: dict[str, str],
    timezone: ZoneInfo | None,
    source: str,
    dry_run: bool,
) -> dict[str, int]:
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        rows = parse_replay_csv(
            file,
            timestamp_column=timestamp_column,
            timestamp_format=timestamp_format,
            column_to_point_code=column_to_point_code,
            timezone=timezone,
        )

    summary = {"inserted": 0, "duplicate": 0, "rejected": 0}
    if dry_run:
        print(f"[dry-run] {len(rows)} relevé(s) traduit(s), rien écrit en base.")
        return summary

    received_at = datetime.now(UTC)
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        point_cache: dict[str, dict] = {}
        for row in rows:
            if row.point_code not in point_cache:
                point_id = _resolve_point_id(connection, row.point_code)
                point_cache[row.point_code] = get_point(connection, point_id)
            point = point_cache[row.point_code]
            try:
                status = record_measurement(
                    connection,
                    tenant_id=tenant_id,
                    point=point,
                    value=row.value,
                    measured_at=row.measured_at,
                    origin="measured",
                    source=source,
                    received_at=received_at,
                )
                summary[status] += 1
            except (MeasurementRejected, MeasurementConflict) as exc:
                summary["rejected"] += 1
                print(f"relevé rejeté ({row.point_code}, {row.measured_at.isoformat()}) : {exc}")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tenant", required=True, type=uuid.UUID, help="Identifiant du client")
    parser.add_argument("--csv", required=True, type=Path, help="Export GTB déjà anonymisé")
    parser.add_argument("--timestamp-column", required=True)
    parser.add_argument(
        "--timestamp-format", required=True, help="Format strptime (ex. %%Y-%%m-%%d %%H:%%M)"
    )
    parser.add_argument(
        "--column",
        action="append",
        dest="columns",
        required=True,
        metavar="COLONNE_CSV=CODE_POINT",
        help="Répétable, une fois par point à importer",
    )
    parser.add_argument(
        "--timezone",
        type=ZoneInfo,
        default=None,
        help="Fuseau d'un horodatage naïf (ex. Europe/Paris) — UTC par défaut",
    )
    parser.add_argument("--source", default="replay_import")
    parser.add_argument(
        "--dry-run", action="store_true", help="Valide et traduit sans rien écrire en base"
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        summary = run(
            tenant_id=args.tenant,
            csv_path=args.csv,
            timestamp_column=args.timestamp_column,
            timestamp_format=args.timestamp_format,
            column_to_point_code=_parse_column_mapping(args.columns),
            timezone=args.timezone,
            source=f"{args.source}:{args.csv.name}",
            dry_run=args.dry_run,
        )
    except ReplayImportRefused as exc:
        raise SystemExit(f"Import refusé : {exc}") from exc

    if not args.dry_run:
        print(
            f"Import terminé : {summary['inserted']} inséré(s), "
            f"{summary['duplicate']} déjà présent(s), {summary['rejected']} rejeté(s)."
        )


if __name__ == "__main__":
    main()
