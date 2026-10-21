"""Tampon hors ligne : une mesure déjà lue n'est jamais perdue si la base est
injoignable (ADR 012 §2.10, DEFER M3-M4 — première brique).

Un fichier local, une ligne JSON par mesure en attente d'un envoi réussi.
Volontairement pas de file d'attente en mémoire : si le démon est redémarré
(ou la machine coupée) pendant une panne réseau, ce qui était en attente
reste sur disque et repart au retour de la connexion.
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("paios.offline_buffer")


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

    @property
    def corrupt_path(self) -> Path:
        return self.path.with_name(self.path.name + ".corrupt")

    def pending(self) -> list[BufferedReading]:
        """Mesures en attente. Une ligne illisible (écriture interrompue par une coupure de
        courant : ligne coupée, octets nuls ou invalides) ne doit jamais empêcher le
        démon de repartir, sinon il tomberait à chaque tour sans jamais se rétablir.
        Elle est écartée de la liste, copiée telle quelle dans `<tampon>.corrupt` (rien
        n'est effacé) et signalée dans le journal."""
        if not self.path.exists():
            return []
        readings: list[BufferedReading] = []
        unreadable: list[str] = []
        with self.path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    readings.append(BufferedReading.from_json(line))
                except (ValueError, KeyError, TypeError):
                    unreadable.append(line if line.endswith("\n") else line + "\n")
        if unreadable:
            with self.corrupt_path.open("a", encoding="utf-8") as sidecar:
                sidecar.writelines(unreadable)
            # Réécrit le tampon sans ces lignes : elles ne sont ni renvoyées ni recopiées
            # à chaque tour.
            temporary = self.path.with_name(self.path.name + ".tmp")
            temporary.write_text("".join(r.to_json() + "\n" for r in readings), encoding="utf-8")
            os.replace(temporary, self.path)
            logger.error(
                f"{len(unreadable)} ligne(s) illisible(s) du tampon mise(s) de côté dans "
                f"{self.corrupt_path.name}",
                extra={
                    "event": "offline_buffer.corrupt_lines",
                    "detail": {"count": len(unreadable)},
                },
            )
        return readings

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
