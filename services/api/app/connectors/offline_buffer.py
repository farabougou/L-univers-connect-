"""Tampon hors ligne : une mesure déjà lue n'est jamais perdue si la base est
injoignable (ADR 012 §2.10, DEFER M3-M4 — première brique).

Un fichier local, une ligne JSON par mesure en attente d'un envoi réussi.
Volontairement pas de file d'attente en mémoire : si le démon est redémarré
(ou la machine coupée) pendant une panne réseau, ce qui était en attente
reste sur disque et repart au retour de la connexion.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BufferedReading:
    tenant_id: uuid.UUID
    point_id: uuid.UUID
    value: float
    measured_at: datetime
    origin: str
    source: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "tenant_id": str(self.tenant_id),
                "point_id": str(self.point_id),
                "value": self.value,
                "measured_at": self.measured_at.isoformat(),
                "origin": self.origin,
                "source": self.source,
            }
        )

    @staticmethod
    def from_json(line: str) -> "BufferedReading":
        data = json.loads(line)
        return BufferedReading(
            tenant_id=uuid.UUID(data["tenant_id"]),
            point_id=uuid.UUID(data["point_id"]),
            value=data["value"],
            measured_at=datetime.fromisoformat(data["measured_at"]),
            origin=data["origin"],
            source=data["source"],
        )

    def as_http_item(self) -> dict[str, Any]:
        """Forme JSON attendue par POST /edge/measurements (voir
        app.connectors.edge_client) : un appareil parle par HTTP, jamais en
        objets Python directement à la base."""
        return {
            "point_id": str(self.point_id),
            "value": self.value,
            "measured_at": self.measured_at.isoformat(),
            "origin": self.origin,
        }


class OfflineBuffer:
    """Fichier append-only de mesures en attente d'un envoi réussi."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, reading: BufferedReading) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(reading.to_json() + "\n")

    def pending(self) -> list[BufferedReading]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return [BufferedReading.from_json(line) for line in handle if line.strip()]

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
