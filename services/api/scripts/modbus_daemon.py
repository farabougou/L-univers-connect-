"""Démon de sondage Modbus : relève un équipement à intervalle régulier
(M3→M4).

L'adresse de l'appareil et l'association point ↔ registre viennent de la
configuration versionnée « modbus_device_mapping » (voir
app/connectors/device_mapping.py), pas d'arguments tapés à la main : cette
configuration se crée et s'active via la console web ou l'API générique
/configs, exactement comme une règle de détection. Le démon relit la
version active à chaque tour : changer l'adresse, ajouter un point ou
retirer la configuration depuis la console prend effet au tour suivant,
sans redémarrage.

Précurseur minimal de l'agent Edge : une seule boucle, pas de gestion de
flotte ni de PKI (DEFER, voir ADR 012 §2.10-2.12). Tous les points d'un même
appareil sont lus en une seule connexion Modbus (voir read_modbus_points),
puis enregistrés ensemble. Deux pannes distinctes, deux réponses
différentes :
- l'appareil est injoignable (Modbus) : rien à faire, on retentera au tour
  suivant, il n'y a pas de valeur à conserver puisqu'aucune n'a été lue ;
- la base est injoignable (réseau du site, coupure) après une lecture
  réussie : chaque valeur lue est mise dans un tampon local (fichier),
  jamais perdue, et repart avec les suivantes dès que la connexion revient.

Usage :
    python scripts/modbus_daemon.py --tenant <tenant_id> --equipment <id> \
        [--interval 60] [--buffer fichier] [--source sdm120]

Arrêt propre : Ctrl+C ou SIGTERM. Le tampon, s'il contient des mesures en
attente, reste sur disque et sera renvoyé au prochain démarrage.
"""

import argparse
import logging
import signal
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

from app.connectors.device_mapping import resolve_active_mapping
from app.connectors.modbus import ModbusReadError, read_modbus_points
from app.connectors.offline_buffer import BufferedReading, OfflineBuffer
from app.db import engine
from app.observability import configure_logging
from app.telemetry import ingest_measurements
from app.tenancy import set_tenant_context

logger = logging.getLogger("paios.modbus_daemon")

_stop = False


def _handle_stop(signum: int, frame: FrameType | None) -> None:
    global _stop
    _stop = True


def _load_mappings(tenant_id: uuid.UUID, equipment_id: uuid.UUID):
    """None si aucune configuration n'est active — jamais une exception pour
    ce cas normal (retirée entre deux tours, pas encore créée)."""
    with engine.begin() as connection:
        set_tenant_context(connection, tenant_id)
        return resolve_active_mapping(connection, equipment_id=equipment_id)


def run(
    *,
    tenant_id: uuid.UUID,
    equipment_id: uuid.UUID,
    interval_seconds: float,
    buffer: OfflineBuffer,
    source: str = "sdm120",
    max_cycles: int | None = None,
) -> int:
    """Boucle de sondage. `max_cycles` (réservé aux tests) arrête après N
    tours au lieu d'attendre Ctrl+C ; renvoie le nombre de tours effectués.

    Refuse de démarrer si aucune configuration n'est active dès le premier
    tour (rien à faire) ; une fois lancé, sa disparition plus tard (retirée
    entre deux tours, base injoignable) n'arrête jamais le démon."""
    if _load_mappings(tenant_id, equipment_id) is None:
        raise SystemExit(
            f"Aucune configuration Modbus active pour l'équipement {equipment_id} "
            "(console web : Connexion Modbus, ou POST /configs puis /activate)."
        )
    logger.info(f"démon Modbus démarré, toutes les {interval_seconds:g}s")

    cycles_done = 0
    while not _stop and (max_cycles is None or cycles_done < max_cycles):
        cycle_started = time.monotonic()
        resolved = None
        try:
            resolved = _load_mappings(tenant_id, equipment_id)
        except Exception as exc:  # noqa: BLE001 — base injoignable : on retente au tour suivant.
            logger.error(
                f"configuration Modbus injoignable, nouvelle tentative au prochain tour : {exc}"
            )
        else:
            if resolved is None:
                logger.error(
                    "aucune configuration Modbus active pour cet équipement, "
                    "nouvelle tentative au prochain tour"
                )

        if resolved is not None:
            host, port, mappings = resolved
            try:
                values = read_modbus_points(host, port, [m.register for m in mappings])
            except ModbusReadError as exc:
                logger.error(f"lecture impossible, nouvelle tentative au prochain tour : {exc}")
            else:
                now = datetime.now(UTC)
                new_readings = [
                    BufferedReading(
                        tenant_id=tenant_id,
                        point_id=mapping.point_id,
                        value=values[mapping.register.name],
                        measured_at=now,
                        origin="measured",
                        source=source,
                    )
                    for mapping in mappings
                ]
                pending = buffer.pending()
                items = [reading.as_item() for reading in pending + new_readings]
                try:
                    with engine.begin() as connection:
                        set_tenant_context(connection, tenant_id)
                        summary = ingest_measurements(
                            connection,
                            tenant_id=tenant_id,
                            items=items,
                            source=source,
                            received_at=now,
                        )
                    buffer.clear()
                    renvoi = f", {len(pending)} mesure(s) en tampon renvoyée(s)" if pending else ""
                    logger.info(f"relève effectuée{renvoi} : {summary}")
                except Exception as exc:  # noqa: BLE001 — coupure BD : les mesures partent au tampon.
                    for reading in new_readings:
                        buffer.append(reading)
                    logger.error(
                        f"base injoignable, {len(new_readings)} mesure(s) mise(s) en tampon local "
                        f"({len(pending) + len(new_readings)} en attente au total) : {exc}"
                    )
        cycles_done += 1

        remaining = interval_seconds - (time.monotonic() - cycle_started)
        more_to_come = not _stop and (max_cycles is None or cycles_done < max_cycles)
        if remaining > 0 and more_to_come:
            time.sleep(remaining)

    logger.info("démon Modbus arrêté")
    return cycles_done


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tenant", required=True, type=uuid.UUID, help="Identifiant du client")
    parser.add_argument(
        "--equipment",
        required=True,
        type=uuid.UUID,
        help="Identifiant de l'équipement (functional_location_id)",
    )
    parser.add_argument("--interval", type=float, default=60.0, help="Secondes entre deux tours")
    parser.add_argument("--buffer", type=Path, default=None, help="Fichier du tampon hors ligne")
    parser.add_argument("--source", default="sdm120")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = _parse_args()
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    buffer_path = args.buffer or Path(f"modbus_buffer_{args.equipment}.jsonl")
    run(
        tenant_id=args.tenant,
        equipment_id=args.equipment,
        interval_seconds=args.interval,
        buffer=OfflineBuffer(buffer_path),
        source=args.source,
    )


if __name__ == "__main__":
    main()
