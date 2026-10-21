"""Lecture directe d'un compteur Eastron SDM120 et contrôles T1 à T4, sans la plateforme
et sans Internet (consolidation V5 du 21/10/2026).

À lancer AVANT de démarrer le démon : cela isole le compteur et la passerelle de tout le
reste. Lecture seule : seul le code de fonction Modbus 04 est utilisé (voir
app/connectors/modbus.py, qui ne contient aucune fonction d'écriture).

Usage (depuis services/api) :
    PYTHONPATH=. python scripts/sdm120_preflight.py --host 192.168.1.200 \\
        --resistive-load --display voltage=231,2 --display current=2,38 \\
        --display active_power=549 --json-out ~/sdm120-lecture-directe.json

Avec le simulateur (répétition à blanc) : --host 127.0.0.1 --port 5020.

Code de sortie : 0 aucun échec (des contrôles peuvent rester non évalués), 1 au moins un
échec, 2 lecture impossible.
"""

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app.connectors.modbus import ModbusReadError, read_modbus_points
from app.connectors.sdm120 import SDM120_POINTS
from app.i18n import load_catalog
from app.sdm120_check import FAIL, READ_KEYS, check_direct_readings, render

UNITS = {point.name: point.unit for point in SDM120_POINTS}


def parse_display(raw: str) -> tuple[str, float]:
    """`voltage=231,2` ou `voltage=231.2` -> ("voltage", 231.2)."""
    name, _, number = raw.strip().partition("=")
    if name not in READ_KEYS:
        raise argparse.ArgumentTypeError(
            f"grandeur inconnue « {name} » (attendu : {', '.join(READ_KEYS)})"
        )
    try:
        return name, float(number.replace(",", "."))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"valeur illisible pour {name} : « {number} »") from exc


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", required=True, help="Adresse de la passerelle (ou du simulateur)")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--reads", type=int, default=3, help="Nombre de lectures (au moins 3)")
    parser.add_argument("--pause", type=float, default=3.0, help="Secondes entre deux lectures")
    parser.add_argument("--nominal-voltage", type=float, default=230.0)
    parser.add_argument(
        "--resistive-load",
        action="store_true",
        help="La charge branchée est résistive (radiateur, bouilloire) : active le contrôle T4",
    )
    parser.add_argument(
        "--display",
        action="append",
        type=parse_display,
        default=None,
        metavar="GRANDEUR=VALEUR",
        help=(
            "Valeur lue sur l'afficheur du compteur, une option par grandeur "
            f"({', '.join(READ_KEYS)}) ; la virgule décimale est acceptée"
        ),
    )
    parser.add_argument("--lang", choices=("fr", "en"), default="fr")
    parser.add_argument("--json-out", type=Path, default=None, help="Fichier de preuve (JSON)")
    args = parser.parse_args(argv)
    args.display = dict(args.display) if args.display else None
    if args.reads < 3:
        parser.error("--reads doit valoir au moins 3 (critère T1)")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    notes = load_catalog(args.lang, "sdm120_check")["notes"]
    print(notes["readonly"])

    reads: list[dict[str, float]] = []
    timestamps: list[str] = []
    for index in range(args.reads):
        if index:
            time.sleep(args.pause)
        try:
            values = read_modbus_points(args.host, args.port, SDM120_POINTS)
        except ModbusReadError as exc:
            print(f"Lecture impossible ({args.host}:{args.port}) : {exc}", file=sys.stderr)
            return 2
        reads.append(values)
        timestamps.append(datetime.now(UTC).isoformat())
        print(
            f"Lecture {index + 1}/{args.reads} : "
            + ", ".join(f"{name} = {values[name]:.6g} {UNITS[name]}" for name in READ_KEYS)
        )

    checks = check_direct_readings(
        reads,
        nominal_voltage=args.nominal_voltage,
        resistive_load=args.resistive_load,
        display=args.display,
    )
    print()
    for check in checks:
        print(render(check, args.lang))

    if args.json_out:
        evidence = {
            "kind": "sdm120_direct",
            "taken_at": timestamps,
            "host": args.host,
            "port": args.port,
            "options": {
                "nominal_voltage": args.nominal_voltage,
                "resistive_load": args.resistive_load,
                "display": args.display,
            },
            "reads": reads,
            "checks": [{"code": c.code, "status": c.status, "params": c.params} for c in checks],
        }
        args.json_out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), "utf-8")
        print(f"\nPreuve enregistrée : {args.json_out}")
    return 1 if any(check.status == FAIL for check in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
