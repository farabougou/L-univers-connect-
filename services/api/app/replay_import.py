"""Replay Mode (ADR 017 §3, Virtual Commissioning Lab) : traduit un export
réel anonymisé de GTB (CSV, format large — une colonne par point, une ligne
par horodatage) vers le même contrat qu'une mesure en direct
(`app.telemetry.record_measurement`, voir `scripts/replay_import.py`) —
jamais un second chemin d'ingestion, jamais une table parallèle.

Anonymisation : responsabilité de la personne qui fournit l'export (CLAUDE.md,
règle non négociable 9 — aucune donnée personnelle réelle). Ce module ajoute
une garde minimale, **jamais une garantie** : refuse un fichier dont l'en-tête
ou un échantillon de valeurs ressemble à une donnée personnelle (nom, e-mail,
téléphone), tant que l'anonymisation n'est pas explicitement confirmée par la
personne qui lance l'import (`--anonymise-confirme` côté script).

Pure logique, sans base ni réseau : un fichier CSV entre, des relevés à
enregistrer sortent — le palier UNIT_TESTED de ce module."""

import csv
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import IO
from zoneinfo import ZoneInfo

_SUSPICIOUS_HEADER_TOKENS = (
    "nom",
    "prenom",
    "prénom",
    "name",
    "email",
    "e-mail",
    "mail",
    "telephone",
    "téléphone",
    "phone",
    "adresse",
    "address",
)
_EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
# Comparé à la cellule ENTIÈRE (`fullmatch`), jamais à une sous-chaîne : un
# horodatage ("2026-10-01 08:00") ou une grande valeur de compteur
# ("1234567.8") contiennent eux aussi des suites de chiffres avec séparateurs
# — seule une cellule qui ne contient RIEN d'autre qu'un numéro de téléphone
# plausible (9 à 15 chiffres, indicatif international optionnel) déclenche
# la garde. Pas de ":" dans les séparateurs tolérés : une heure ne matche
# jamais. Trouvé par un vrai test (`test_ordinary_header_and_values_are_accepted`
# a d'abord échoué à cause d'un `search` trop large sur l'horodatage lui-même).
_PHONE_PATTERN = re.compile(r"(?:\+\d{1,3}[ .-]?)?(?:\d[ .-]?){8,14}\d")


class ReplayImportRefused(Exception):
    """Fichier refusé avant tout enregistrement — jamais un import partiel."""


@dataclass(frozen=True)
class ReplayRow:
    measured_at: datetime
    point_code: str
    value: float


def check_not_obviously_personal_data(header: list[str], sample_rows: list[list[str]]) -> None:
    """Garde minimale (pas une garantie, voir le docstring du module) :
    refuse un en-tête ou un échantillon de valeurs qui ressemble à une
    donnée personnelle."""
    for column in header:
        normalized = column.strip().lower()
        if any(token in normalized for token in _SUSPICIOUS_HEADER_TOKENS):
            raise ReplayImportRefused(
                f"colonne {column!r} ressemble à une donnée personnelle (nom, e-mail, "
                "téléphone...) — l'export doit être anonymisé avant d'être rejoué "
                "(CLAUDE.md, règle non négociable 9)"
            )
    for row in sample_rows:
        for cell in row:
            stripped = cell.strip()
            if _EMAIL_PATTERN.search(stripped) or _PHONE_PATTERN.fullmatch(stripped):
                raise ReplayImportRefused(
                    "une valeur ressemble à un e-mail ou un numéro de téléphone — l'export "
                    "doit être anonymisé avant d'être rejoué (CLAUDE.md, règle non négociable 9)"
                )


def parse_replay_csv(
    file: IO[str],
    *,
    timestamp_column: str,
    timestamp_format: str,
    column_to_point_code: dict[str, str],
    timezone: ZoneInfo | None = None,
    sample_size: int = 50,
) -> list[ReplayRow]:
    """Lit un export au format large et le traduit en relevés individuels
    (une ligne par point par horodatage) — une cellule vide est un capteur
    non mesuré à cet instant, jamais une valeur à zéro inventée.

    `timezone` convertit un horodatage naïf (sans fuseau, le cas courant
    d'un export GTB) vers UTC ; par défaut, un horodatage naïf est traité
    comme déjà en UTC (ADR 012, convention horaire de la plateforme)."""
    reader = csv.DictReader(file)
    if not reader.fieldnames:
        raise ReplayImportRefused("fichier CSV vide ou sans en-tête")
    missing = {timestamp_column, *column_to_point_code} - set(reader.fieldnames)
    if missing:
        raise ReplayImportRefused(f"colonnes absentes du fichier : {', '.join(sorted(missing))}")

    rows = list(reader)
    check_not_obviously_personal_data(
        list(reader.fieldnames), [list(row.values()) for row in rows[:sample_size]]
    )

    replay_rows: list[ReplayRow] = []
    for row in rows:
        raw_timestamp = row[timestamp_column]
        try:
            measured_at = datetime.strptime(raw_timestamp, timestamp_format)
        except ValueError:
            raise ReplayImportRefused(
                f"horodatage {raw_timestamp!r} ne correspond pas au format {timestamp_format!r}"
            ) from None
        measured_at = measured_at.replace(tzinfo=timezone or UTC).astimezone(UTC)

        for column, point_code in column_to_point_code.items():
            raw_value = row[column].strip()
            if raw_value == "":
                continue
            try:
                value = float(raw_value)
            except ValueError:
                raise ReplayImportRefused(
                    f"valeur non numérique {raw_value!r} pour {column!r} à {raw_timestamp!r} "
                    "(Replay Mode ne prend en charge que des points numériques pour l'instant)"
                ) from None
            replay_rows.append(
                ReplayRow(measured_at=measured_at, point_code=point_code, value=value)
            )
    return replay_rows
