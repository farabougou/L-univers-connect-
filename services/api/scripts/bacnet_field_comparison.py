"""Outil de comparaison terrain (ADR 015, section 6) : GTB existante ↔
découverte BACnet ↔ Edge ↔ modèle sémantique ↔ Digital Twin — préparé le
30/09/2026 pour que le premier essai autorisé serve à comparer, mesurer,
corriger et valider, pas à développer sur place.

Utilisation prévue, le jour de l'essai :
1. Relever à la main, depuis la supervision déjà en place chez le client,
   les points visibles pour l'installation concernée (nom, unité) — les
   consigner dans un fichier CSV (colonnes : name, unit, notes ; unit et
   notes facultatifs).
2. Lancer un scan BACnet depuis la console web (fiche équipement,
   « Découverte BACnet »), attendre qu'il passe à « Prêt ».
3. Lancer cet outil pour comparer la liste GTB au scan et obtenir un
   rapport Markdown des correspondances, des écarts et des points encore
   à classer.

Usage :
    python scripts/bacnet_field_comparison.py \
        --api-url https://api.example.com --token <jeton humain> \
        --batch-id <identifiant du lot> --gtb-csv releve_gtb.csv \
        --output rapport_comparaison.md

Ou hors ligne, contre un export déjà récupéré (voir --proposals-json) :
    python scripts/bacnet_field_comparison.py \
        --proposals-json propositions.json --gtb-csv releve_gtb.csv

Toute la logique de rapprochement vit dans app.bacnet_field_comparison
(module pur, UNIT_TESTED) ; ce script ne fait que la collecte (CSV, API ou
fichier local) et l'écriture du rapport."""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import httpx

from app.bacnet_field_comparison import GtbEntry, compare, render_markdown_report


def _load_gtb_csv(path: Path) -> list[GtbEntry]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "name" not in reader.fieldnames:
            raise SystemExit(
                f"{path} : en-tête attendu avec au moins une colonne 'name' "
                "(colonnes facultatives : unit, notes)"
            )
        return [
            GtbEntry(
                name=row["name"].strip(),
                unit=(row.get("unit") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
            )
            for row in reader
            if row.get("name", "").strip()
        ]


def _load_proposals_from_api(*, api_url: str, token: str, batch_id: str) -> list[dict]:
    response = httpx.get(
        f"{api_url}/bacnet-discovery/batches/{batch_id}/proposals",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def _load_proposals_from_file(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--gtb-csv", required=True, type=Path, help="Relevé GTB (colonnes : name, unit, notes)"
    )
    parser.add_argument(
        "--proposals-json",
        type=Path,
        help="Propositions déjà récupérées (GET .../proposals), au lieu d'appeler l'API",
    )
    parser.add_argument("--api-url", help="Base de l'API (avec --batch-id)")
    parser.add_argument(
        "--token",
        default=os.environ.get("PAIOS_ACCESS_TOKEN"),
        help="Jeton humain (par défaut : variable d'environnement PAIOS_ACCESS_TOKEN)",
    )
    parser.add_argument("--batch-id", help="Identifiant du lot de découverte (avec --api-url)")
    parser.add_argument(
        "--title", default="Comparaison terrain", help="Titre du rapport (ex. nom du site)"
    )
    parser.add_argument(
        "--output", type=Path, help="Fichier de sortie (Markdown) ; par défaut, la sortie standard"
    )
    args = parser.parse_args()
    if bool(args.proposals_json) == bool(args.api_url and args.batch_id):
        parser.error(
            "indiquer soit --proposals-json, soit --api-url et --batch-id ensemble, jamais les deux"
        )
    if args.api_url and not args.token:
        parser.error("--token requis avec --api-url (ou la variable PAIOS_ACCESS_TOKEN)")
    return args


def main() -> None:
    args = _parse_args()
    gtb_entries = _load_gtb_csv(args.gtb_csv)
    if args.proposals_json:
        proposals = _load_proposals_from_file(args.proposals_json)
    else:
        proposals = _load_proposals_from_api(
            api_url=args.api_url, token=args.token, batch_id=args.batch_id
        )

    rows, summary = compare(gtb_entries, proposals)
    report = render_markdown_report(rows, summary, title=args.title)

    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Rapport écrit dans {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
