"""Tests du Replay Mode (ADR 017 §3) — palier UNIT_TESTED : aucune base,
seulement la traduction CSV → relevés et la garde anti-donnée-personnelle.
Le palier INTEGRATION_TESTED (relevés rejoués qui déclenchent une vraie
règle FDD) vit dans tests/test_replay_import_integration.py."""

import io
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.replay_import import (
    ReplayImportRefused,
    ReplayRow,
    check_not_obviously_personal_data,
    parse_replay_csv,
)


def _csv(text: str) -> io.StringIO:
    return io.StringIO(text.strip() + "\n")


def test_parses_a_wide_export_into_individual_readings() -> None:
    file = _csv(
        """
Horodatage,T_Depart,Vanne_Chaude
2026-10-01 08:00,18.2,0
2026-10-01 08:05,18.4,5
"""
    )
    rows = parse_replay_csv(
        file,
        timestamp_column="Horodatage",
        timestamp_format="%Y-%m-%d %H:%M",
        column_to_point_code={"T_Depart": "CTA-01.t_depart", "Vanne_Chaude": "CTA-01.vanne_chaude"},
    )
    assert rows == [
        ReplayRow(datetime(2026, 10, 1, 8, 0, tzinfo=UTC), "CTA-01.t_depart", 18.2),
        ReplayRow(datetime(2026, 10, 1, 8, 0, tzinfo=UTC), "CTA-01.vanne_chaude", 0.0),
        ReplayRow(datetime(2026, 10, 1, 8, 5, tzinfo=UTC), "CTA-01.t_depart", 18.4),
        ReplayRow(datetime(2026, 10, 1, 8, 5, tzinfo=UTC), "CTA-01.vanne_chaude", 5.0),
    ]


def test_empty_cell_is_skipped_not_treated_as_zero() -> None:
    file = _csv(
        """
Horodatage,T_Depart
2026-10-01 08:00,
"""
    )
    rows = parse_replay_csv(
        file,
        timestamp_column="Horodatage",
        timestamp_format="%Y-%m-%d %H:%M",
        column_to_point_code={"T_Depart": "CTA-01.t_depart"},
    )
    assert rows == []


def test_naive_timestamp_with_timezone_is_converted_to_utc() -> None:
    file = _csv(
        """
Horodatage,T_Depart
2026-10-01 08:00,18.2
"""
    )
    rows = parse_replay_csv(
        file,
        timestamp_column="Horodatage",
        timestamp_format="%Y-%m-%d %H:%M",
        column_to_point_code={"T_Depart": "CTA-01.t_depart"},
        timezone=ZoneInfo("Europe/Paris"),
    )
    # 08:00 heure de Paris (UTC+2 en octobre, heure d'été) = 06:00 UTC.
    assert rows[0].measured_at == datetime(2026, 10, 1, 6, 0, tzinfo=UTC)


def test_missing_column_is_refused() -> None:
    file = _csv("Horodatage,T_Depart\n2026-10-01 08:00,18.2\n")
    with pytest.raises(ReplayImportRefused, match="colonnes absentes"):
        parse_replay_csv(
            file,
            timestamp_column="Horodatage",
            timestamp_format="%Y-%m-%d %H:%M",
            column_to_point_code={"Vanne_Chaude": "CTA-01.vanne_chaude"},
        )


def test_malformed_timestamp_is_refused() -> None:
    file = _csv("Horodatage,T_Depart\nn-importe-quoi,18.2\n")
    with pytest.raises(ReplayImportRefused, match="horodatage"):
        parse_replay_csv(
            file,
            timestamp_column="Horodatage",
            timestamp_format="%Y-%m-%d %H:%M",
            column_to_point_code={"T_Depart": "CTA-01.t_depart"},
        )


def test_non_numeric_value_is_refused() -> None:
    file = _csv("Horodatage,T_Depart\n2026-10-01 08:00,hors-service\n")
    with pytest.raises(ReplayImportRefused, match="non numérique"):
        parse_replay_csv(
            file,
            timestamp_column="Horodatage",
            timestamp_format="%Y-%m-%d %H:%M",
            column_to_point_code={"T_Depart": "CTA-01.t_depart"},
        )


def test_empty_file_is_refused() -> None:
    with pytest.raises(ReplayImportRefused, match="vide"):
        parse_replay_csv(
            io.StringIO(""),
            timestamp_column="Horodatage",
            timestamp_format="%Y-%m-%d %H:%M",
            column_to_point_code={"T_Depart": "CTA-01.t_depart"},
        )


# --- Garde anti-donnée-personnelle (CLAUDE.md, règle non négociable 9) ---


def test_suspicious_header_is_refused() -> None:
    with pytest.raises(ReplayImportRefused, match="donnée personnelle"):
        check_not_obviously_personal_data(["Horodatage", "Nom technicien"], [])


@pytest.mark.parametrize(
    "value",
    ["jean.dupont@example.com", "+33 6 12 34 56 78", "0612345678"],
)
def test_suspicious_value_is_refused(value: str) -> None:
    with pytest.raises(ReplayImportRefused, match="donnée personnelle|e-mail|téléphone"):
        check_not_obviously_personal_data(["Horodatage", "Commentaire"], [["2026-10-01", value]])


def test_ordinary_header_and_values_are_accepted() -> None:
    check_not_obviously_personal_data(
        ["Horodatage", "T_Depart", "Vanne_Chaude"],
        [["2026-10-01 08:00", "18.2", "0"]],
    )


def test_header_check_is_applied_even_when_the_file_has_no_rows() -> None:
    file = _csv("Horodatage,Nom technicien\n")
    with pytest.raises(ReplayImportRefused, match="donnée personnelle"):
        parse_replay_csv(
            file,
            timestamp_column="Horodatage",
            timestamp_format="%Y-%m-%d %H:%M",
            column_to_point_code={},
        )
