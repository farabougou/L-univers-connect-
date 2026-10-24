"""Vérification, après l'essai, des mesures d'un compteur SDM120 enregistrées par la
plateforme (consolidation V5 du 21/10/2026). Fonctionne hors ligne : elle lit la base
locale (lecture seule, sous la sécurité par client), pas l'API ; aucun jeton à renouveler.

Elle applique les contrôles T5 à T9 de docs/terrain/test-terrain-sdm120.md : unités des
points, mesures manquantes, doubles mesures, indicateurs de qualité, énergie, et les
épreuves de panne que vous déclarez avec --outage.

Heures : toujours avec fuseau (« 2026-10-21T09:10:00Z »). Notez-les pendant l'essai avec
`date -u +%Y-%m-%dT%H:%M:%SZ`.

Usage (depuis services/api) :
    PYTHONPATH=. python scripts/sdm120_verify.py \\
        --tenant <TENANT_ID> --power-point <ID_POINT_PUISSANCE> --energy-point <ID_POINT_ENERGIE> \\
        --start 2026-10-21T09:00:00Z --end 2026-10-21T09:45:00Z --interval 60 \\
        --outage api=2026-10-21T09:10:00Z,2026-10-21T09:15:00Z \\
        --outage gateway=2026-10-21T09:20:00Z,2026-10-21T09:25:00Z \\
        --outage daemon=2026-10-21T09:30:00Z,2026-10-21T09:32:00Z \\
        --direct-json ~/sdm120-lecture-directe.json --json-out ~/sdm120-rapport.json

Code de sortie : 0 PASS, 1 FAIL, 2 point introuvable pour ce client, 3 INCOMPLETE (au moins
un contrôle requis non évalué).
Le verdict ne remplace jamais la fiche de résultats signée : voir la section « Non couvert ».
"""

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db import engine
from app.i18n import load_catalog
from app.sdm120_check import (
    Check,
    Sample,
    Window,
    check_point_definitions,
    check_series,
    find_gaps,
    render,
    verdict,
)
from app.tenancy import set_tenant_context

EXIT_CODES = {"PASS": 0, "FAIL": 1, "INCOMPLETE": 3}


def parse_instant(raw: str) -> datetime:
    """Heure ISO 8601 avec fuseau obligatoire : une heure sans fuseau est ambiguë."""
    try:
        moment = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"heure illisible : « {raw} »") from exc
    if moment.tzinfo is None:
        raise argparse.ArgumentTypeError(
            f"heure sans fuseau : « {raw} » (ajouter Z pour UTC, ou un décalage comme +00:00)"
        )
    return moment.astimezone(UTC)


def parse_outage(raw: str) -> Window:
    """`api=DEBUT,FIN` (types : api, gateway, daemon)."""
    kind, _, span = raw.partition("=")
    start, _, end = span.partition(",")
    if not (kind and start and end):
        raise argparse.ArgumentTypeError(f"coupure mal écrite : « {raw} » (type=début,fin)")
    try:
        return Window(kind.strip(), parse_instant(start), parse_instant(end))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def fetch_series(
    tenant_id: uuid.UUID, point_id: uuid.UUID, start: datetime, end: datetime
) -> list[Sample]:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        rows = connection.execute(
            text(
                "SELECT measured_at, value, quality_flags FROM measurements "
                "WHERE point_id = :point_id AND measured_at >= :start AND measured_at <= :end "
                "ORDER BY measured_at"
            ),
            {"point_id": point_id, "start": start, "end": end},
        ).all()
    return [
        Sample(row.measured_at, float(row.value), tuple(row.quality_flags or ())) for row in rows
    ]


def fetch_point(tenant_id: uuid.UUID, point_id: uuid.UUID) -> dict[str, Any] | None:
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        row = connection.execute(
            text("SELECT point_class, unit FROM points WHERE id = :point_id"),
            {"point_id": point_id},
        ).first()
    return None if row is None else {"point_class": row.point_class, "unit": row.unit}


def load_direct_checks(path: Path) -> list[Check]:
    evidence = json.loads(path.read_text("utf-8"))
    if evidence.get("kind") != "sdm120_direct":
        raise ValueError(f"{path} n'est pas un fichier de preuve de sdm120_preflight.py")
    return [Check(c["code"], c["status"], c["params"]) for c in evidence["checks"]]


def build_checks(
    *,
    tenant_id: uuid.UUID,
    power_point: uuid.UUID,
    energy_point: uuid.UUID,
    start: datetime,
    end: datetime,
    interval: float,
    windows: list[Window],
    direct: list[Check],
) -> tuple[list[Check], list[Sample]]:
    """Lit la base et assemble tous les contrôles. Lève LookupError si un point est introuvable
    pour ce client (mauvais identifiant, ou point d'un autre client : jamais visible)."""
    power_def = fetch_point(tenant_id, power_point)
    energy_def = fetch_point(tenant_id, energy_point)
    if power_def is None or energy_def is None:
        raise LookupError("point introuvable pour ce client")
    power = fetch_series(tenant_id, power_point, start, end)
    energy = fetch_series(tenant_id, energy_point, start, end)
    checks = [
        *direct,
        check_point_definitions(power=power_def, energy=energy_def),
        *check_series(
            power=power,
            energy=energy,
            interval_seconds=interval,
            start=start,
            end=end,
            windows=windows,
        ),
    ]
    return checks, power


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tenant", required=True, type=uuid.UUID)
    parser.add_argument("--power-point", required=True, type=uuid.UUID)
    parser.add_argument("--energy-point", required=True, type=uuid.UUID)
    parser.add_argument("--start", required=True, type=parse_instant)
    parser.add_argument("--end", required=True, type=parse_instant)
    parser.add_argument("--interval", type=float, default=60.0, help="Intervalle de relève, en s")
    parser.add_argument(
        "--outage",
        action="append",
        type=parse_outage,
        default=[],
        help="Coupure provoquée : api|gateway|daemon=début,fin (répétable)",
    )
    parser.add_argument(
        "--direct-json", type=Path, default=None, help="Preuve de sdm120_preflight.py"
    )
    parser.add_argument("--lang", choices=("fr", "en"), default="fr")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.end <= args.start:
        parser.error("--end doit suivre --start")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    notes = load_catalog(args.lang, "sdm120_check")["notes"]
    direct = load_direct_checks(args.direct_json) if args.direct_json else []
    try:
        checks, power = build_checks(
            tenant_id=args.tenant,
            power_point=args.power_point,
            energy_point=args.energy_point,
            start=args.start,
            end=args.end,
            interval=args.interval,
            windows=args.outage,
            direct=direct,
        )
    except LookupError as exc:
        print(f"{exc}", file=sys.stderr)
        return 2

    for check in checks:
        print(render(check, args.lang))
    print(f"\n{notes['gaps']} :")
    gaps = find_gaps(power, args.interval)
    for begin, finish, missing in gaps:
        print(f"  {begin.isoformat()} -> {finish.isoformat()} ({missing})")
    if not gaps:
        print(f"  {notes['no_gap']}")

    result = verdict(checks)
    print(f"\n{notes['verdict']} : {load_catalog(args.lang, 'sdm120_check')['statuses'][result]}")
    print(notes["not_covered"])

    if args.json_out:
        report = {
            "kind": "sdm120_verification",
            "verdict": result,
            "period": [args.start.isoformat(), args.end.isoformat()],
            "interval_seconds": args.interval,
            "outages": [
                {"kind": w.kind, "start": w.start.isoformat(), "end": w.end.isoformat()}
                for w in args.outage
            ],
            "checks": [{"code": c.code, "status": c.status, "params": c.params} for c in checks],
            "gaps": [[b.isoformat(), f.isoformat(), m] for b, f, m in gaps],
        }
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), "utf-8"
        )
        print(f"Rapport enregistré : {args.json_out}")
    return EXIT_CODES[result]


if __name__ == "__main__":
    sys.exit(main())
