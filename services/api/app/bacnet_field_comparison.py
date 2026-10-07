"""Outil de comparaison terrain (ADR 015, section 6 : GTB existante ↔
découverte BACnet ↔ Edge ↔ modèle sémantique ↔ Digital Twin/interface),
préparé le 30/09/2026 pour que le premier essai terrain autorisé serve à
comparer, mesurer, corriger et valider — pas à développer sur place.

Module pur, sans réseau ni base de données (UNIT_TESTED,
`tests/test_bacnet_field_comparison.py`) : compare une liste de points
relevée à la main depuis la supervision existante d'un site avec les
propositions déjà produites par un scan de découverte BACnet
(`app.bacnet_discovery`). Le CLI (`scripts/bacnet_field_comparison.py`)
assure la collecte (fichier CSV rempli sur site, appel à l'API pour les
propositions) ; ce module ne connaît que des structures déjà chargées.

Correspondance stricte, jamais devinée : deux noms sont mis en
correspondance seulement si leurs formes normalisées (minuscules, accents
retirés, ponctuation et espaces ignorés) sont strictement égales — jamais
une correspondance approximative qui masquerait un vrai écart entre ce que
voit la GTB et ce que notre Edge découvre (même principe que le devineur
sémantique : mieux vaut « à revoir » qu'une correspondance inventée)."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

MatchKind = Literal["matched", "gtb_only", "discovery_only"]


@dataclass(frozen=True)
class GtbEntry:
    """Un point tel que relevé à la main depuis la supervision déjà en
    place chez le client, avant tout scan — voir la méthodologie de l'ADR
    015, étape 1."""

    name: str
    unit: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ComparisonRow:
    match_kind: MatchKind
    gtb_name: str | None
    gtb_unit: str | None
    discovered_name: str | None
    object_type: str | None
    object_instance: int | None
    bacnet_units: str | None
    proposed_point_class: str | None
    confidence: float | None
    reason_code: str | None
    status: str | None


@dataclass(frozen=True)
class ComparisonSummary:
    gtb_count: int
    discovered_count: int
    matched_count: int
    gtb_only_count: int
    discovery_only_count: int
    # Points appariés ou découverts en plus, mais sans correspondance
    # sémantique fiable (`proposed_point_class` nul) : à classer par une
    # personne avant d'accepter la proposition.
    needs_review_count: int


def _normalize(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", without_accents.lower())


def compare(
    gtb_entries: list[GtbEntry], proposals: list[dict[str, Any]]
) -> tuple[list[ComparisonRow], ComparisonSummary]:
    """`proposals` : lignes telles que renvoyées par
    `app.bacnet_discovery.list_proposals` (ou l'API, mêmes champs)."""
    gtb_by_key = {_normalize(entry.name): entry for entry in gtb_entries}
    proposals_by_key = {_normalize(str(p["object_name"] or "")): p for p in proposals}

    rows: list[ComparisonRow] = []
    matched_keys: set[str] = set()

    for key, entry in gtb_by_key.items():
        proposal = proposals_by_key.get(key)
        if proposal is None:
            rows.append(
                ComparisonRow(
                    match_kind="gtb_only",
                    gtb_name=entry.name,
                    gtb_unit=entry.unit,
                    discovered_name=None,
                    object_type=None,
                    object_instance=None,
                    bacnet_units=None,
                    proposed_point_class=None,
                    confidence=None,
                    reason_code=None,
                    status=None,
                )
            )
        else:
            matched_keys.add(key)
            rows.append(_matched_row(entry, proposal))

    for key, proposal in proposals_by_key.items():
        if key in matched_keys:
            continue
        rows.append(_discovery_only_row(proposal))

    needs_review = sum(
        1 for row in rows if row.match_kind != "gtb_only" and row.proposed_point_class is None
    )
    summary = ComparisonSummary(
        gtb_count=len(gtb_entries),
        discovered_count=len(proposals),
        matched_count=len(matched_keys),
        gtb_only_count=sum(1 for row in rows if row.match_kind == "gtb_only"),
        discovery_only_count=sum(1 for row in rows if row.match_kind == "discovery_only"),
        needs_review_count=needs_review,
    )
    return rows, summary


def _matched_row(entry: GtbEntry, proposal: dict[str, Any]) -> ComparisonRow:
    return ComparisonRow(
        match_kind="matched",
        gtb_name=entry.name,
        gtb_unit=entry.unit,
        discovered_name=proposal["object_name"],
        object_type=proposal["object_type"],
        object_instance=proposal["object_instance"],
        bacnet_units=proposal["bacnet_units"],
        proposed_point_class=proposal["proposed_point_class"],
        confidence=(
            float(proposal["confidence"]) if proposal.get("confidence") is not None else None
        ),
        reason_code=proposal["reason_code"],
        status=proposal["status"],
    )


def _discovery_only_row(proposal: dict[str, Any]) -> ComparisonRow:
    return ComparisonRow(
        match_kind="discovery_only",
        gtb_name=None,
        gtb_unit=None,
        discovered_name=proposal["object_name"],
        object_type=proposal["object_type"],
        object_instance=proposal["object_instance"],
        bacnet_units=proposal["bacnet_units"],
        proposed_point_class=proposal["proposed_point_class"],
        confidence=(
            float(proposal["confidence"]) if proposal.get("confidence") is not None else None
        ),
        reason_code=proposal["reason_code"],
        status=proposal["status"],
    )


def render_markdown_report(
    rows: list[ComparisonRow], summary: ComparisonSummary, *, title: str = "Comparaison terrain"
) -> str:
    """Rapport lisible par une personne pendant l'essai terrain — jamais un
    format destiné à l'affichage produit (pas de traduction ADR 013 ici :
    document de travail technique, pas une interface)."""
    lines = [
        f"# {title}",
        "",
        f"- Points relevés depuis la GTB existante : {summary.gtb_count}",
        f"- Objets découverts par le scan BACnet : {summary.discovered_count}",
        f"- Correspondances trouvées (nom strictement identique) : {summary.matched_count}",
        f"- Vus par la GTB, non découverts par le scan (à investiguer) : {summary.gtb_only_count}",
        f"- Découverts par le scan, absents de la liste GTB : {summary.discovery_only_count}",
        f"- Sans correspondance sémantique fiable, à classer : {summary.needs_review_count}",
        "",
        "| Statut | Nom GTB | Nom découvert | Objet BACnet | Unité | Classe proposée | "
        "Confiance | Raison | État |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    kind_label = {
        "matched": "Correspond",
        "gtb_only": "GTB seulement",
        "discovery_only": "Découverte seulement",
    }
    for row in rows:
        object_ref = (
            f"{row.object_type} #{row.object_instance}" if row.object_type is not None else "—"
        )
        confidence = f"{row.confidence:.2f}" if row.confidence is not None else "—"
        lines.append(
            "| "
            + " | ".join(
                [
                    kind_label[row.match_kind],
                    row.gtb_name or "—",
                    row.discovered_name or "—",
                    object_ref,
                    row.bacnet_units or row.gtb_unit or "—",
                    row.proposed_point_class or "à revoir",
                    confidence,
                    row.reason_code or "—",
                    row.status or "—",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
