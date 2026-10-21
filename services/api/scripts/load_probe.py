"""Test de charge progressif et borné d'une route de l'API (voir app/load_probe.py).

Exemples :
    # En local, route authentifiée (jeton lu dans l'environnement, jamais en argument) :
    LOAD_PROBE_TOKEN=... PYTHONPATH=. python scripts/load_probe.py \
        --base-url http://127.0.0.1:8000 --path "/sync/interventions?limit=100" \
        --levels 1,5,10,20,40,80 --step-seconds 10

    # Sur un hébergement (refusé sans --allow-remote : on n'envoie pas de charge à
    # un serveur distant par accident) :
    PYTHONPATH=. python scripts/load_probe.py --base-url https://api.exemple \
        --path /health --levels 1,5,10 --allow-remote

La montée s'arrête au premier critère franchi (erreurs serveur, refus 503,
limitation 429, latence p99) ou à une borne (requêtes, durée), puis une phase de
reprise vérifie le retour à la normale. Aucune requête n'écrit : GET uniquement.
"""

import argparse
import asyncio
import ipaddress
import json
import os
import sys
import time
from collections import Counter
from urllib.parse import urlparse

import httpx

from app.load_probe import Criteria, ProbeReport, StepResult, run_probe

MAX_CONCURRENCY = 200


def is_local(base_url: str) -> bool:
    host = urlparse(base_url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def parse_levels(raw: str) -> list[int]:
    levels = [int(part) for part in raw.split(",") if part.strip()]
    if not levels or any(level < 1 or level > MAX_CONCURRENCY for level in levels):
        raise argparse.ArgumentTypeError(f"paliers entre 1 et {MAX_CONCURRENCY} clients")
    if levels != sorted(levels):
        raise argparse.ArgumentTypeError("paliers croissants uniquement")
    return levels


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--path", required=True, help="Route GET à mesurer")
    parser.add_argument("--levels", type=parse_levels, default="1,5,10,20,40")
    parser.add_argument("--step-seconds", type=float, default=10.0)
    parser.add_argument("--recovery-seconds", type=float, default=20.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--max-shed-rate", type=float, default=0.05)
    parser.add_argument("--max-limited-rate", type=float, default=0.05)
    parser.add_argument("--max-p99-seconds", type=float, default=5.0)
    parser.add_argument("--max-total-requests", type=int, default=5000)
    parser.add_argument("--max-total-seconds", type=float, default=300.0)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument(
        "--label", default="", help="Nom de la cible dans le rapport (ex. local, staging)"
    )
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()
    if isinstance(args.levels, str):
        args.levels = parse_levels(args.levels)
    if not is_local(args.base_url) and not args.allow_remote:
        parser.error("cible distante : ajouter --allow-remote pour confirmer l'intention")
    return args


def _row(step: StepResult) -> str:
    s = step.statuses
    return (
        f"{step.concurrency:>9} {step.requests:>9} {step.rps:>8.1f} "
        f"{step.p(0.50) * 1000:>7.0f} {step.p(0.95) * 1000:>7.0f} {step.p(0.99) * 1000:>7.0f} "
        f"{s['2xx']:>6} {s['429']:>5} {s['500'] + s['502'] + s['504']:>5} "
        f"{s['503']:>5} {s['reseau']:>6}"
    )


def render(report: ProbeReport, target: str, network_errors: Counter | None = None) -> str:
    lines = [
        f"Cible : {target}",
        f"{'clients':>9} {'requêtes':>9} {'req/s':>8} {'p50 ms':>7} {'p95 ms':>7} {'p99 ms':>7} "
        f"{'2xx':>6} {'429':>5} {'5xx':>5} {'503':>5} {'réseau':>6}",
    ]
    lines += [_row(step) for step in report.steps]
    if report.stopped_because:
        lines.append(f"Arrêt de la montée : {report.stopped_because}")
    if report.reached_limit:
        lines.append(f"Borne atteinte : {report.reached_limit}")
    if report.recovery and report.verdict:
        lines.append("Reprise (1 client) :")
        lines.append(_row(report.recovery))
        answer = "OUI" if report.verdict.ok else "NON"
        lines.append(f"Retour à la normale : {answer} — {report.verdict.reason}")
    if network_errors:
        kinds = ", ".join(f"{kind} ×{count}" for kind, count in network_errors.most_common())
        lines.append(f"Erreurs réseau côté client : {kinds}")
    return "\n".join(lines)


def to_json(report: ProbeReport, target: str, network_errors: Counter | None = None) -> dict:
    def step(result: StepResult) -> dict:
        return {
            "clients": result.concurrency,
            "requetes": result.requests,
            "req_par_s": round(result.rps, 2),
            "p50_ms": round(result.p(0.50) * 1000, 1),
            "p95_ms": round(result.p(0.95) * 1000, 1),
            "p99_ms": round(result.p(0.99) * 1000, 1),
            "statuts": dict(result.statuses),
        }

    return {
        "cible": target,
        "paliers": [step(s) for s in report.steps],
        "arret": report.stopped_because,
        "borne": report.reached_limit,
        "reprise": step(report.recovery) if report.recovery else None,
        "retour_a_la_normale": report.verdict.ok if report.verdict else None,
        "detail_reprise": report.verdict.reason if report.verdict else None,
        "erreurs_reseau": dict(network_errors or {}),
    }


async def _main() -> int:
    args = _parse_args()
    headers = {}
    token = os.environ.get("LOAD_PROBE_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    limits = httpx.Limits(max_connections=max(args.levels) + 5)
    network_errors: Counter = Counter()
    async with httpx.AsyncClient(
        base_url=args.base_url, headers=headers, timeout=30.0, limits=limits
    ) as client:

        async def send() -> tuple[int | None, float]:
            started = time.perf_counter()
            try:
                response = await client.get(args.path)
                await response.aread()
                return response.status_code, time.perf_counter() - started
            except httpx.HTTPError as error:
                network_errors[type(error).__name__] += 1
                return None, time.perf_counter() - started

        report = await run_probe(
            send,
            levels=args.levels,
            step_seconds=args.step_seconds,
            recovery_seconds=args.recovery_seconds,
            criteria=Criteria(
                max_error_rate=args.max_error_rate,
                max_shed_rate=args.max_shed_rate,
                max_limited_rate=args.max_limited_rate,
                max_p99_seconds=args.max_p99_seconds,
                max_total_requests=args.max_total_requests,
                max_total_seconds=args.max_total_seconds,
            ),
        )
    target = f"{args.label or args.base_url} {args.path.split('?')[0]}"
    print(render(report, target, network_errors))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(to_json(report, target, network_errors), handle, ensure_ascii=False, indent=2)
    return 0 if report.verdict and report.verdict.ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
