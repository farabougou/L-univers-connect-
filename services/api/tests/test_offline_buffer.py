import uuid
from datetime import UTC, datetime

from app.connectors.offline_buffer import BufferedReading, OfflineBuffer


def _reading(**overrides) -> BufferedReading:
    defaults = dict(
        tenant_id=uuid.uuid4(),
        point_id=uuid.uuid4(),
        value=42.5,
        measured_at=datetime(2026, 9, 24, 8, 0, tzinfo=UTC),
        origin="measured",
        source="sdm120",
    )
    return BufferedReading(**{**defaults, **overrides})


def test_vide_au_depart(tmp_path):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    assert buffer.pending() == []


def test_append_puis_pending_retrouve_exactement_la_meme_mesure(tmp_path):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    reading = _reading()
    buffer.append(reading)

    assert buffer.pending() == [reading]


def test_plusieurs_ajouts_gardent_l_ordre(tmp_path):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    first = _reading(value=1.0)
    second = _reading(value=2.0)
    buffer.append(first)
    buffer.append(second)

    assert buffer.pending() == [first, second]


def test_clear_vide_le_tampon(tmp_path):
    buffer = OfflineBuffer(tmp_path / "buffer.jsonl")
    buffer.append(_reading())
    buffer.clear()

    assert buffer.pending() == []


def test_clear_sans_fichier_ne_leve_rien(tmp_path):
    OfflineBuffer(tmp_path / "jamais-cree.jsonl").clear()
