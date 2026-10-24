"""Test de charge progressif et borné (consolidation V5 du 21/10/2026).

Monte la charge par paliers (nombre de clients simultanés), mesure à chaque palier
le débit, les latences p50/p95/p99 et la répartition des statuts, puis **s'arrête
dès qu'un critère est franchi** : erreurs serveur, délestage (503), limitation
(429), latence p99. Il lance ensuite une phase de reprise à faible charge et
vérifie le **retour à la normale** après saturation.

Pensé pour être exécuté à l'identique en local et sur un hébergement (scripts/
load_probe.py) : les chiffres des deux ne doivent jamais être mélangés, le rapport
indique la cible mesurée. Les bornes (clients, requêtes, durée) existent pour ne
jamais transformer un essai en déni de service.

La logique est ici (testable sans réseau, avec un émetteur factice) ; le réseau
réel est dans scripts/load_probe.py.
"""

import asyncio
import math
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

# Un émetteur renvoie (code HTTP ou None si échec réseau, durée en secondes).
Send = Callable[[], Awaitable[tuple[int | None, float]]]


def percentile(sorted_values: list[float], fraction: float) -> float:
    """Rang le plus proche (méthode « nearest rank ») : le p99 de 100 valeurs est la
    99e, jamais une valeur interpolée qui n'a pas été observée."""
    if not sorted_values:
        return 0.0
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


def classify(status: int | None) -> str:
    if status is None:
        return "reseau"
    if 200 <= status < 300:
        return "2xx"
    if status in (429, 500, 502, 503, 504):
        return str(status)
    if 400 <= status < 500:
        return "4xx"
    return "autre"


@dataclass
class StepResult:
    concurrency: int
    seconds: float
    latencies: list[float] = field(default_factory=list)
    statuses: Counter = field(default_factory=Counter)

    @property
    def requests(self) -> int:
        return sum(self.statuses.values())

    @property
    def rps(self) -> float:
        return self.requests / self.seconds if self.seconds else 0.0

    def count(self, *classes: str) -> int:
        return sum(self.statuses[c] for c in classes)

    def rate(self, *classes: str) -> float:
        return self.count(*classes) / self.requests if self.requests else 0.0

    @property
    def error_rate(self) -> float:
        """Vraies pannes : erreurs serveur (hors délestage 503) et pertes réseau."""
        return self.rate("500", "502", "504", "reseau")

    @property
    def shed_rate(self) -> float:
        return self.rate("503")

    @property
    def limited_rate(self) -> float:
        return self.rate("429")

    def p(self, fraction: float) -> float:
        return percentile(sorted(self.latencies), fraction)


@dataclass(frozen=True)
class Criteria:
    max_error_rate: float = 0.01
    max_shed_rate: float = 0.05
    max_limited_rate: float = 0.05
    max_p99_seconds: float = 5.0
    max_total_requests: int = 5000
    max_total_seconds: float = 300.0
    # Un événement isolé n'arrête pas la montée : 1 erreur sur 80 requêtes fait 1,25 %
    # sans prouver une saturation. Il reste compté et rapporté dans tous les cas.
    min_events: int = 3


def stop_reason(step: StepResult, criteria: Criteria) -> str | None:
    """Pourquoi arrêter la montée après ce palier, ou None pour continuer."""
    failures = step.count("500", "502", "504", "reseau")
    if step.error_rate > criteria.max_error_rate and failures >= criteria.min_events:
        return (
            f"erreurs serveur ou réseau : {step.error_rate:.1%} "
            f"(seuil {criteria.max_error_rate:.1%})"
        )
    if step.limited_rate > criteria.max_limited_rate and step.count("429") >= criteria.min_events:
        return (
            f"limitation de débit 429 : {step.limited_rate:.1%} "
            "(la mesure ne porte plus sur la capacité)"
        )
    if step.shed_rate > criteria.max_shed_rate and step.count("503") >= criteria.min_events:
        return f"saturation atteinte, requêtes refusées 503 : {step.shed_rate:.1%}"
    if step.p(0.99) > criteria.max_p99_seconds:
        return f"latence p99 : {step.p(0.99):.2f} s (seuil {criteria.max_p99_seconds:.2f} s)"
    return None


@dataclass(frozen=True)
class RecoveryVerdict:
    ok: bool
    reason: str


def recovery_verdict(baseline: StepResult, recovery: StepResult) -> RecoveryVerdict:
    """Retour à la normale : aucune erreur ni refus, et un p95 revenu près de celui
    du palier de référence (au plus le double, ou 50 ms de plus s'il est très bas)."""
    if recovery.requests == 0:
        return RecoveryVerdict(False, "aucune requête pendant la reprise")
    bad = recovery.error_rate + recovery.shed_rate + recovery.limited_rate
    if bad > 0:
        return RecoveryVerdict(False, f"{bad:.1%} de requêtes en échec pendant la reprise")
    allowed = max(2 * baseline.p(0.95), baseline.p(0.95) + 0.05)
    if recovery.p(0.95) > allowed:
        return RecoveryVerdict(
            False,
            f"p95 {recovery.p(0.95) * 1000:.0f} ms, au-dessus de {allowed * 1000:.0f} ms attendus",
        )
    return RecoveryVerdict(
        True,
        f"p95 {recovery.p(0.95) * 1000:.0f} ms, sans erreur "
        f"(référence {baseline.p(0.95) * 1000:.0f} ms)",
    )


@dataclass
class ProbeReport:
    steps: list[StepResult]
    stopped_because: str | None
    reached_limit: str | None
    recovery: StepResult | None
    verdict: RecoveryVerdict | None


async def run_step(send: Send, concurrency: int, seconds: float) -> StepResult:
    result = StepResult(concurrency=concurrency, seconds=seconds)
    deadline = time.monotonic() + seconds

    async def worker() -> None:
        while time.monotonic() < deadline:
            status, elapsed = await send()
            result.latencies.append(elapsed)
            result.statuses[classify(status)] += 1

    started = time.monotonic()
    await asyncio.gather(*(worker() for _ in range(concurrency)))
    result.seconds = max(time.monotonic() - started, 1e-9)
    return result


async def run_probe(
    send: Send,
    *,
    levels: list[int],
    step_seconds: float,
    recovery_seconds: float,
    criteria: Criteria = Criteria(),
) -> ProbeReport:
    steps: list[StepResult] = []
    stopped: str | None = None
    limit: str | None = None
    started = time.monotonic()

    for concurrency in levels:
        if sum(step.requests for step in steps) >= criteria.max_total_requests:
            limit = f"plafond de {criteria.max_total_requests} requêtes atteint"
            break
        if time.monotonic() - started >= criteria.max_total_seconds:
            limit = f"plafond de {criteria.max_total_seconds:.0f} s atteint"
            break
        step = await run_step(send, concurrency, step_seconds)
        steps.append(step)
        stopped = stop_reason(step, criteria)
        if stopped:
            break

    recovery = await run_step(send, 1, recovery_seconds) if steps else None
    verdict = recovery_verdict(steps[0], recovery) if steps and recovery else None
    return ProbeReport(steps, stopped, limit, recovery, verdict)
