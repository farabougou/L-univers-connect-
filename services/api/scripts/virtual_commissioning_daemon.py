"""Virtual Protocol Adapter, le démon (ADR 017 §2.2, Virtual Commissioning
Lab) : relève un équipement virtuel à intervalle régulier et envoie ses
mesures générées par `app.connectors.virtual_telemetry`, exactement comme
`scripts/modbus_daemon.py` le fait pour un équipement Modbus réel — même
identité d'appareil (`app.connectors.edge_client.EdgeApiClient`), même
endpoint `POST /edge/measurements`, même tampon hors ligne. Aucun nouvel
endpoint d'ingestion : du point de vue du reste de la plateforme, un
équipement virtuel est indiscernable d'un équipement réel tant qu'on ne
regarde pas `origin`/`source` de ses mesures.

La configuration (identifiant d'appareil, secret, correspondance point ↔
suffixe de code) vient du manifeste écrit par `scripts/seed_virtual_site.py`
— pas de `GET /edge/config` ici : un actif virtuel n'a ni hôte ni port à
découvrir, le profil suffit à savoir quoi générer.

Usage :
    python scripts/virtual_commissioning_daemon.py \
        --api-url http://localhost:8000 --manifest virtual_site_site_virtuel_1.json \
        --equipment CTA-01 [--interval 60] [--buffer fichier]

Scénario de panne déclenchable (ADR 017 §2.2, incrément 2) :
    python scripts/virtual_commissioning_daemon.py ... --failure-scenario vanne_bloquee

Voir `app.connectors.virtual_telemetry.list_failure_scenarios` pour les noms
valides selon le profil de l'équipement — toujours au moins
`perte_communication`, valable sur n'importe quel profil. Le scénario démarre
au lancement du démon (une dérive se mesure depuis cet instant) ; l'arrêter
est un redémarrage sans `--failure-scenario`, jamais un état à annuler en
base — aucune trace d'une panne qui n'a pas eu lieu.

Arrêt propre : Ctrl+C ou SIGTERM. Le tampon, s'il contient des mesures en
attente, reste sur disque et repart au prochain démarrage (même principe que
le démon Modbus).
"""

import argparse
import json
import logging
import signal
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

import httpx

from app.connectors.edge_client import EdgeApiClient
from app.connectors.offline_buffer import BufferedReading, OfflineBuffer
from app.connectors.virtual_telemetry import (
    FailureScenario,
    failure_scenario,
    generate_profile_values,
)
from app.observability import configure_logging

logger = logging.getLogger("paios.virtual_commissioning_daemon")

_stop = False


def _handle_stop(signum: int, frame: FrameType | None) -> None:
    global _stop
    _stop = True


def _load_manifest_equipment(manifest_path: Path, equipment_code: str) -> dict:
    manifest = json.loads(manifest_path.read_text())
    for equipment in manifest["equipment"]:
        if equipment["code"] == equipment_code:
            if not equipment.get("device_secret"):
                raise SystemExit(
                    f"Le manifeste {manifest_path} ne contient pas de secret pour "
                    f"{equipment_code} (déjà consommé lors d'un précédent lancement de "
                    "seed_virtual_site.py — le secret n'est jamais réécrit). "
                    "Relancer avec un nouveau site, ou fournir --secret explicitement."
                )
            return {
                "tenant_id": uuid.UUID(manifest["tenant_id"]),
                "device_id": equipment["device_id"],
                "secret": equipment["device_secret"],
                "profile": equipment["profile"],
                "points": {
                    suffix: uuid.UUID(point_id) for suffix, point_id in equipment["points"].items()
                },
            }
    raise SystemExit(f"Équipement {equipment_code!r} introuvable dans {manifest_path}")


def run(
    *,
    api: EdgeApiClient,
    profile: str,
    points: dict[str, uuid.UUID],
    interval_seconds: float,
    buffer: OfflineBuffer,
    source: str = "virtual_commissioning_lab",
    max_cycles: int | None = None,
    scenario: FailureScenario | None = None,
) -> int:
    """Boucle de génération + envoi. `max_cycles` (réservé aux tests) arrête
    après N tours au lieu d'attendre Ctrl+C ; renvoie le nombre de tours
    effectués. Avec `scenario`, il démarre au premier tour de cet appel —
    jamais avant, jamais rétroactif."""
    logger.info(
        f"démon Virtual Commissioning Lab démarré (profil {profile}), toutes les "
        f"{interval_seconds:g}s"
        + (f" — scénario de panne actif : {scenario.name}" if scenario else "")
    )
    scenario_started_at = datetime.now(UTC) if scenario else None

    cycles_done = 0
    while not _stop and (max_cycles is None or cycles_done < max_cycles):
        cycle_started = time.monotonic()
        now = datetime.now(UTC)
        values = generate_profile_values(
            profile, now=now, scenario=scenario, scenario_started_at=scenario_started_at
        )
        new_readings = [
            BufferedReading(
                tenant_id=api.tenant_id,
                point_id=point_id,
                value=float(values[suffix]),
                measured_at=now,
                origin="simulated",
                source=source,
            )
            for suffix, point_id in points.items()
            if suffix in values
        ]
        pending = buffer.pending()
        items = [reading.as_http_item() for reading in pending + new_readings]
        try:
            summary = api.post_measurements(items)
            buffer.clear()
            renvoi = f", {len(pending)} mesure(s) en tampon renvoyée(s)" if pending else ""
            logger.info(f"relève virtuelle effectuée{renvoi} : {summary}")
        except httpx.HTTPError as exc:
            for reading in new_readings:
                buffer.append(reading)
            logger.error(
                f"API injoignable, {len(new_readings)} mesure(s) mise(s) en tampon local "
                f"({len(pending) + len(new_readings)} en attente au total) : {exc}"
            )
        cycles_done += 1

        remaining = interval_seconds - (time.monotonic() - cycle_started)
        more_to_come = not _stop and (max_cycles is None or cycles_done < max_cycles)
        if remaining > 0 and more_to_come:
            time.sleep(remaining)

    logger.info("démon Virtual Commissioning Lab arrêté")
    return cycles_done


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-url", default="http://localhost:8000", help="Base de l'API")
    parser.add_argument(
        "--manifest", required=True, type=Path, help="Manifeste de scripts/seed_virtual_site.py"
    )
    parser.add_argument(
        "--equipment", required=True, help="Code de l'équipement virtuel (ex. CTA-01)"
    )
    parser.add_argument("--interval", type=float, default=60.0, help="Secondes entre deux tours")
    parser.add_argument("--buffer", type=Path, default=None, help="Fichier du tampon hors ligne")
    parser.add_argument(
        "--failure-scenario",
        default=None,
        help=(
            "Nom d'un scénario de panne (voir "
            "app.connectors.virtual_telemetry.list_failure_scenarios) — aucun par défaut, "
            "télémétrie saine"
        ),
    )
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = _parse_args()
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    equipment = _load_manifest_equipment(args.manifest, args.equipment)
    buffer_path = args.buffer or Path(f"virtual_buffer_{args.equipment}.jsonl")
    scenario = (
        failure_scenario(equipment["profile"], args.failure_scenario)
        if args.failure_scenario
        else None
    )

    with EdgeApiClient(
        client=httpx.Client(base_url=args.api_url, timeout=10.0),
        tenant_id=equipment["tenant_id"],
        device_id=equipment["device_id"],
        secret=equipment["secret"],
    ) as api:
        run(
            api=api,
            profile=equipment["profile"],
            points=equipment["points"],
            interval_seconds=args.interval,
            buffer=OfflineBuffer(buffer_path),
            scenario=scenario,
        )


if __name__ == "__main__":
    main()
