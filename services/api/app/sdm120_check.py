"""Vérification des relevés d'un compteur Eastron SDM120 (préparation du test terrain,
consolidation V5 du 21/10/2026).

Fonctions pures, sans réseau ni base : elles reçoivent des valeurs et rendent des
constats `Check(code, status, params)`. Les codes sont stables ; la phrase est produite
à l'affichage par scripts/sdm120_*.py depuis `shared/i18n/*/sdm120_check.json`
(ADR 013). La même règle sert à la répétition avec le simulateur et au test sur le vrai
compteur : seul le résultat change.

Ce que ces vérifications établissent : unités et ordres de grandeur, cohérence interne
des mesures, complétude, absence de double relève, comportement après coupure de l'API,
coupure de la passerelle et redémarrage du démon.

Ce qu'elles n'établissent pas seules : que l'afficheur du compteur concorde (saisie
humaine), que le câblage est conforme, que la donnée est affichée « périmée » dans la
console pendant la coupure (à regarder à l'écran, voir le guide terrain).

Un critère qui n'a pas pu être évalué reste `NOT_EVALUATED` : il n'est jamais compté
comme réussi (`verdict`).
"""

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.i18n import load_catalog

PASS = "PASS"
FAIL = "FAIL"
NOT_EVALUATED = "NOT_EVALUATED"

WINDOW_KINDS = ("api", "gateway", "daemon")

READ_KEYS = ("voltage", "current", "active_power", "frequency", "total_active_energy")

# Résolution d'affichage supposée du SDM120, à confirmer sur la notice de l'exemplaire
# utilisé : l'écart toléré est le plus grand de 1 % et de cette résolution.
DISPLAY_RESOLUTION = {
    "voltage": 0.1,
    "current": 0.01,
    "active_power": 1.0,
    "frequency": 0.1,
    "total_active_energy": 0.01,
}

# Puissance et courant maximaux plausibles pour un SDM120 en raccordement direct.
MAX_CURRENT_A = 100.0
MAX_POWER_W = 23_000.0

# Seuils du guide terrain (docs/terrain/test-terrain-sdm120.md, section 8).
VOLTAGE_TOLERANCE = 0.10
FREQUENCY_TOLERANCE_HZ = 1.0
DISPLAY_TOLERANCE = 0.01
POWER_VS_VI_TOLERANCE = 0.05
ENERGY_VS_POWER_TOLERANCE = 0.10
# En dessous, l'énergie est de l'ordre de la résolution du compteur (un pas de 0,01 kW.h
# fausserait de 10 % une comparaison à 0,1) : on ne conclut pas.
MIN_COMPARABLE_ENERGY_KWH = 0.1

# Un facteur proche de 1000 entre l'énergie mesurée et celle déduite de la puissance
# trahit une confusion d'unité (W / kW, ou Wh / kWh).
UNIT_FACTOR_BAND = (0.8, 1.25)

# Contrôles dont le succès conditionne le verdict global (T1 à T9 du guide, plus le
# redémarrage du démon et l'absence de double mesure).
DIRECT_CODES = (
    "DIRECT_READS_COMPLETE",
    "DIRECT_VALUES_PLAUSIBLE",
    "POWER_UNIT_COHERENT",
    "DISPLAY_CONCORDANCE",
    "POWER_EQUALS_V_TIMES_I",
)
SERIES_CODES = (
    "POINT_UNITS_MATCH_METER",
    "NO_MISSING_SAMPLES",
    "NO_DOUBLE_SAMPLING",
    "INTERVAL_RESPECTED",
    "QUALITY_FLAGS_CLEAN",
    "ENERGY_NEVER_DECREASES",
    "ENERGY_MATCHES_POWER",
    "NO_LOSS_DURING_API_OUTAGE",
    "GATEWAY_OUTAGE_HANDLED",
    "RESTART_RESUMED",
)
REQUIRED_FOR_PASS = DIRECT_CODES + SERIES_CODES


@dataclass(frozen=True)
class Check:
    code: str
    status: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Sample:
    at: datetime
    value: float
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Window:
    """Intervalle pendant lequel l'opérateur a provoqué une coupure."""

    kind: str
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.kind not in WINDOW_KINDS:
            raise ValueError(f"type de coupure inconnu : {self.kind}")
        if self.end <= self.start:
            raise ValueError("la fin d'une coupure doit suivre son début")


def _check(code: str, ok: bool | None, **params: Any) -> Check:
    if ok is None and not params.get("reason"):
        raise ValueError(f"{code} : un contrôle non évalué doit dire pourquoi (reason)")
    status = NOT_EVALUATED if ok is None else PASS if ok else FAIL
    return Check(code, status, params)


def _finite(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


# --- Lecture directe (avant tout enregistrement) --------------------------------


def check_direct_readings(
    reads: Sequence[dict[str, float]],
    *,
    nominal_voltage: float = 230.0,
    nominal_frequency: float = 50.0,
    resistive_load: bool = False,
    display: dict[str, float] | None = None,
) -> list[Check]:
    """Contrôles T1 à T4 sur au moins trois lectures directes du compteur."""
    complete = [read for read in reads if all(_finite(read.get(key)) for key in READ_KEYS)]
    incomplete = len(reads) - len(complete)
    checks = [
        _check(
            "DIRECT_READS_COMPLETE",
            len(complete) >= 3 and incomplete == 0,
            count=len(reads),
            incomplete=incomplete,
            required=3,
        )
    ]
    if not complete:
        return checks + [_check(code, None, reason="READS_INCOMPLETE") for code in DIRECT_CODES[1:]]

    violations: set[str] = set()
    for read in complete:
        if abs(read["voltage"] - nominal_voltage) > VOLTAGE_TOLERANCE * nominal_voltage:
            violations.add("voltage")
        if abs(read["frequency"] - nominal_frequency) > FREQUENCY_TOLERANCE_HZ:
            violations.add("frequency")
        if not 0 <= read["current"] <= MAX_CURRENT_A:
            violations.add("current")
        if not 0 <= read["active_power"] <= MAX_POWER_W:
            violations.add("active_power")
    energies = [read["total_active_energy"] for read in complete]
    if min(energies) < 0 or any(b < a for a, b in zip(energies, energies[1:], strict=False)):
        violations.add("total_active_energy")
    checks.append(
        _check(
            "DIRECT_VALUES_PLAUSIBLE",
            not violations,
            violations=sorted(violations),
            nominal_voltage=nominal_voltage,
        )
    )

    loaded = [read for read in complete if read["voltage"] * read["current"] >= 20.0]
    ratios = [read["active_power"] / (read["voltage"] * read["current"]) for read in loaded]
    # La puissance active ne dépasse jamais la puissance apparente (V x I), et un facteur de
    # puissance sous 0,02 est irréaliste : en dehors, l'unité de la puissance est suspecte.
    checks.append(
        _check(
            "POWER_UNIT_COHERENT",
            None if not loaded else all(0.02 <= ratio <= 1.05 for ratio in ratios),
            ratio_min=round(min(ratios), 4) if ratios else None,
            ratio_max=round(max(ratios), 4) if ratios else None,
            reason=None if loaded else "NO_LOAD",
        )
    )

    if display is None:
        checks.append(_check("DISPLAY_CONCORDANCE", None, reason="DISPLAY_NOT_PROVIDED"))
    else:
        deviations: dict[str, float] = {}
        for key, shown in display.items():
            measured = statistics.median(read[key] for read in complete)
            allowed = max(DISPLAY_TOLERANCE * abs(shown), DISPLAY_RESOLUTION.get(key, 0.0))
            if abs(measured - shown) > allowed:
                deviations[key] = round(measured - shown, 4)
        checks.append(
            _check(
                "DISPLAY_CONCORDANCE",
                not deviations,
                deviations=deviations,
                compared=sorted(display),
            )
        )

    if not resistive_load:
        checks.append(_check("POWER_EQUALS_V_TIMES_I", None, reason="LOAD_NOT_DECLARED_RESISTIVE"))
    else:
        strong = [read for read in complete if read["voltage"] * read["current"] >= 100.0]
        if not strong:
            checks.append(_check("POWER_EQUALS_V_TIMES_I", None, reason="NO_LOAD"))
        else:
            worst = max(
                abs(read["active_power"] - read["voltage"] * read["current"])
                / (read["voltage"] * read["current"])
                for read in strong
            )
            checks.append(
                _check(
                    "POWER_EQUALS_V_TIMES_I",
                    worst <= POWER_VS_VI_TOLERANCE,
                    worst_deviation=round(worst, 4),
                    tolerance=POWER_VS_VI_TOLERANCE,
                )
            )
    return checks


# --- Définition des points dans la plateforme -----------------------------------

# Ce que le compteur délivre : puissance en W, énergie en kW.h. Le vocabulaire des points
# accepte aussi `kW` pour une puissance, et rien ne compare l'unité du point à celle du
# registre : un point déclaré en kW afficherait des watts comme des kilowatts (facteur 1000).
EXPECTED_POINT_DEFINITIONS = {
    "power": ("electric_power_sensor", "W"),
    "energy": ("energy_meter_reading", "kW.h"),
}


def check_point_definitions(*, power: dict[str, Any], energy: dict[str, Any]) -> Check:
    """`power` et `energy` : `point_class` et `unit` des deux points tels que la
    plateforme les a enregistrés."""
    mismatches = []
    for name, point in (("power", power), ("energy", energy)):
        expected_class, expected_unit = EXPECTED_POINT_DEFINITIONS[name]
        if point.get("point_class") != expected_class:
            mismatches.append(f"{name}.point_class")
        if point.get("unit") != expected_unit:
            mismatches.append(f"{name}.unit")
    return _check(
        "POINT_UNITS_MATCH_METER",
        not mismatches,
        power_class=power.get("point_class"),
        power_unit=power.get("unit"),
        energy_class=energy.get("point_class"),
        energy_unit=energy.get("unit"),
        mismatches=mismatches,
    )


# --- Série enregistrée par la plateforme -----------------------------------------


@dataclass(frozen=True)
class _Gap:
    start: datetime
    end: datetime
    missing: int


def _covered_seconds(start: datetime, end: datetime, windows: Sequence[Window]) -> float:
    """Durée de [start, end] couverte par des coupures sans relève attendue (union)."""
    spans = sorted(
        (max(w.start, start), min(w.end, end))
        for w in windows
        if w.kind in ("gateway", "daemon") and w.end > start and w.start < end
    )
    total, cursor = 0.0, None
    for left, right in spans:
        if cursor is None or left > cursor:
            total += (right - left).total_seconds()
            cursor = right
        elif right > cursor:
            total += (right - cursor).total_seconds()
            cursor = right
    return total


def _gaps(
    samples: Sequence[Sample],
    start: datetime,
    end: datetime,
    interval: float,
    windows: Sequence[Window],
) -> list[_Gap]:
    """Relevés manquants non expliqués par une coupure sans relève (passerelle, démon).

    Aux deux bouts de l'essai, l'opérateur note l'heure à la main : une relève peut
    légitimement arriver jusqu'à un intervalle après le début, ou avant la fin."""
    stamps = [sample.at for sample in samples]
    edges = [start, *stamps, end]
    gaps: list[_Gap] = []
    for index, (left, right) in enumerate(zip(edges, edges[1:], strict=False)):
        length = (right - left).total_seconds()
        if index == 0 or index == len(edges) - 2:
            length -= interval
        covered = _covered_seconds(left, right, windows)
        if covered > 0:
            # la dernière mesure peut précéder la coupure d'un intervalle, et la reprise
            # suivre sa fin de deux intervalles (le temps que la passerelle redémarre)
            missing = int((length - covered) / interval + 0.5) - 3
        else:
            missing = int(length / interval + 0.5) - 1
        if missing > 0:
            gaps.append(_Gap(left, right, missing))
    return gaps


def _overlaps(gap: _Gap, window: Window) -> bool:
    return gap.start < window.end and gap.end > window.start


def _gap_params(gaps: Sequence[_Gap]) -> list[dict[str, Any]]:
    return [
        {"from": gap.start.isoformat(), "to": gap.end.isoformat(), "missing": gap.missing}
        for gap in gaps[:5]
    ]


def check_series(
    *,
    power: Sequence[Sample],
    energy: Sequence[Sample],
    interval_seconds: float,
    start: datetime,
    end: datetime,
    windows: Sequence[Window] = (),
) -> list[Check]:
    """Contrôles T5 à T9 sur les mesures de puissance (W) et d'énergie (kW.h) enregistrées."""
    power = sorted(power, key=lambda s: s.at)
    energy = sorted(energy, key=lambda s: s.at)
    if not power or not energy:
        return [_check("NO_SAMPLES", False, power=len(power), energy=len(energy))] + [
            _check(code, None, reason="TOO_FEW_SAMPLES") for code in SERIES_CODES
        ]

    api_windows = [w for w in windows if w.kind == "api"]
    checks: list[Check] = []

    # T5 : complétude hors coupure de l'API (qui a son propre critère, T8)
    gaps = {"power": _gaps(power, start, end, interval_seconds, windows)}
    gaps["energy"] = _gaps(energy, start, end, interval_seconds, windows)
    other = {
        name: [g for g in found if not any(_overlaps(g, w) for w in api_windows)]
        for name, found in gaps.items()
    }
    other_missing = {name: sum(g.missing for g in found) for name, found in other.items()}
    checks.append(
        _check(
            "NO_MISSING_SAMPLES",
            not any(other_missing.values()),
            missing_power=other_missing["power"],
            missing_energy=other_missing["energy"],
            gaps=_gap_params(other["power"] + other["energy"]),
        )
    )

    # Double relève : deux mesures à moins d'un demi-intervalle, ou même série relevée deux fois
    too_close = sum(
        1
        for series in (power, energy)
        for a, b in zip(series, series[1:], strict=False)
        if (b.at - a.at).total_seconds() < interval_seconds / 2
    )
    checks.append(_check("NO_DOUBLE_SAMPLING", too_close == 0, count=too_close))

    spacings = [(b.at - a.at).total_seconds() for a, b in zip(power, power[1:], strict=False)]
    # Médiane de tous les écarts : les trous dus aux coupures sont minoritaires, alors qu'un
    # intervalle réglé autrement que prévu décale la médiane elle-même.
    median = statistics.median(spacings) if spacings else None
    checks.append(
        _check(
            "INTERVAL_RESPECTED",
            None if median is None else abs(median - interval_seconds) <= 0.2 * interval_seconds,
            median_seconds=None if median is None else round(median, 2),
            expected_seconds=interval_seconds,
            reason="TOO_FEW_SAMPLES" if median is None else None,
        )
    )

    # T6 : qualité. `late_arrival` est normal pour une relève rejouée après une coupure de l'API.
    allowed_late = [
        (w.start - timedelta(seconds=interval_seconds), w.end + timedelta(seconds=interval_seconds))
        for w in api_windows
    ]
    unexpected: dict[str, int] = {}
    for series in (power, energy):
        for sample in series:
            for flag in sample.flags:
                if flag == "late_arrival" and any(a <= sample.at <= b for a, b in allowed_late):
                    continue
                unexpected[flag] = unexpected.get(flag, 0) + 1
    checks.append(_check("QUALITY_FLAGS_CLEAN", not unexpected, unexpected=unexpected))

    # T7 : l'énergie ne décroît jamais, et correspond à la puissance x durée
    decreases = sum(1 for a, b in zip(energy, energy[1:], strict=False) if b.value < a.value - 1e-9)
    checks.append(_check("ENERGY_NEVER_DECREASES", decreases == 0, decreases=decreases))
    checks.append(_energy_vs_power(power, energy))

    checks.append(_api_outage(api_windows, power, energy, gaps, interval_seconds))
    checks.append(_gateway_outage(windows, power, interval_seconds))
    checks.append(_daemon_restart(windows, power, energy, interval_seconds))
    return checks


def _energy_vs_power(power: Sequence[Sample], energy: Sequence[Sample]) -> Check:
    if len(power) < 2 or len(energy) < 2:
        return _check("ENERGY_MATCHES_POWER", None, reason="TOO_FEW_SAMPLES")
    joules = sum(
        (b.at - a.at).total_seconds() * (a.value + b.value) / 2
        for a, b in zip(power, power[1:], strict=False)
    )
    expected_kwh = joules / 3_600_000
    measured_kwh = energy[-1].value - energy[0].value
    # Les deux séries ne couvrent pas exactement la même durée : l'attendu est ramené
    # à celle de l'énergie.
    span_power = (power[-1].at - power[0].at).total_seconds()
    span_energy = (energy[-1].at - energy[0].at).total_seconds()
    if span_power > 0:
        expected_kwh *= span_energy / span_power
    params = {
        "measured_kwh": round(measured_kwh, 4),
        "expected_kwh": round(expected_kwh, 4),
    }
    if max(expected_kwh, measured_kwh) < MIN_COMPARABLE_ENERGY_KWH:
        return _check("ENERGY_MATCHES_POWER", None, reason="ENERGY_TOO_SMALL", **params)
    if measured_kwh <= 0:
        return _check("ENERGY_MATCHES_POWER", False, reason="ENERGY_FROZEN", **params)
    if expected_kwh <= 1e-9:
        return _check("ENERGY_MATCHES_POWER", False, reason="OUT_OF_TOLERANCE", **params)
    ratio = measured_kwh / expected_kwh
    params["ratio"] = round(ratio, 4)
    for factor in (1000.0, 1 / 1000.0):
        if UNIT_FACTOR_BAND[0] <= ratio / factor <= UNIT_FACTOR_BAND[1]:
            return _check("ENERGY_MATCHES_POWER", False, reason="UNIT_FACTOR_SUSPECTED", **params)
    ok = abs(ratio - 1.0) <= ENERGY_VS_POWER_TOLERANCE
    return _check("ENERGY_MATCHES_POWER", ok, reason=None if ok else "OUT_OF_TOLERANCE", **params)


def _api_outage(
    api_windows: Sequence[Window],
    power: Sequence[Sample],
    energy: Sequence[Sample],
    gaps: dict[str, list[_Gap]],
    interval: float,
) -> Check:
    if not api_windows:
        return _check("NO_LOSS_DURING_API_OUTAGE", None, reason="NO_OUTAGE_DECLARED")
    lost = sum(
        g.missing
        for found in gaps.values()
        for g in found
        if any(_overlaps(g, w) for w in api_windows)
    )
    replayed = sum(1 for s in power if any(w.start <= s.at <= w.end for w in api_windows))
    expected = sum(int((w.end - w.start).total_seconds() / interval) for w in api_windows)
    # Sans aucune mesure datée dans la coupure, rien n'a été relevé pendant qu'elle durait
    # (cas d'un démon qui, faute d'API, ne lit plus le compteur) : perte, même si l'écart
    # était trop court pour être détecté comme trou.
    never_read = expected >= 2 and replayed == 0
    return _check(
        "NO_LOSS_DURING_API_OUTAGE",
        lost == 0 and not never_read,
        lost=lost if lost else (expected if never_read else 0),
        replayed=replayed,
        expected=expected,
    )


def _gateway_outage(windows: Sequence[Window], power: Sequence[Sample], interval: float) -> Check:
    gateway = [w for w in windows if w.kind == "gateway"]
    if not gateway:
        return _check("GATEWAY_OUTAGE_HANDLED", None, reason="NO_OUTAGE_DECLARED")
    margin = timedelta(seconds=interval)
    invented = 0
    not_resumed = 0
    for w in gateway:
        # Les heures sont notées à la main : on ne juge « inventée » qu'une mesure située à
        # plus d'un intervalle des deux bornes (la relève en cours à la coupure peut finir
        # un peu après, et la reprise peut précéder l'heure de fin notée).
        invented += sum(1 for s in power if w.start + margin < s.at < w.end - margin)
        if not any(w.end - margin <= s.at <= w.end + 2 * margin for s in power):
            not_resumed += 1
    return _check(
        "GATEWAY_OUTAGE_HANDLED",
        invented == 0 and not_resumed == 0,
        invented=invented,
        not_resumed=not_resumed,
    )


def _daemon_restart(
    windows: Sequence[Window],
    power: Sequence[Sample],
    energy: Sequence[Sample],
    interval: float,
) -> Check:
    stops = [w for w in windows if w.kind == "daemon"]
    if not stops:
        return _check("RESTART_RESUMED", None, reason="NO_RESTART_DECLARED")
    margin = timedelta(seconds=interval)
    not_resumed = sum(
        1 for w in stops if not any(w.end - margin <= s.at <= w.end + 2 * margin for s in power)
    )
    # Un redémarrage ne doit ni relire l'historique (doublon) ni remettre l'énergie à zéro
    energy_dropped = sum(
        1
        for a, b in zip(energy, energy[1:], strict=False)
        if b.value < a.value - 1e-9
        and any(w.start <= a.at <= w.end + timedelta(seconds=interval) for w in stops)
    )
    return _check(
        "RESTART_RESUMED",
        not_resumed == 0 and energy_dropped == 0,
        not_resumed=not_resumed,
        energy_dropped=energy_dropped,
    )


def find_gaps(
    samples: Sequence[Sample], interval_seconds: float, *, min_intervals: float = 2.0
) -> list[tuple[datetime, datetime, int]]:
    """Trous de la série (début, fin, mesures manquantes), pour aider à les rapprocher des
    heures de coupure notées par l'opérateur. Informatif : ne juge rien."""
    ordered = sorted(samples, key=lambda s: s.at)
    found = []
    for a, b in zip(ordered, ordered[1:], strict=False):
        length = (b.at - a.at).total_seconds()
        if length >= min_intervals * interval_seconds:
            found.append((a.at, b.at, int(length / interval_seconds + 0.5) - 1))
    return found


def verdict(checks: Sequence[Check]) -> str:
    """FAIL dès qu'un contrôle échoue ; PASS seulement si tous les contrôles requis ont
    été évalués et réussis ; sinon INCOMPLETE (jamais « réussi » par défaut)."""
    if any(check.status == FAIL for check in checks):
        return FAIL
    status_by_code = {check.code: check.status for check in checks}
    if all(status_by_code.get(code) == PASS for code in REQUIRED_FOR_PASS):
        return PASS
    return "INCOMPLETE"


# --- Affichage -------------------------------------------------------------------


def _display_value(value: Any, locale: str) -> str:
    if isinstance(value, dict):
        return (
            ", ".join(f"{key} : {_display_value(item, locale)}" for key, item in value.items())
            or "—"
        )
    if isinstance(value, list | tuple):
        return ", ".join(_display_value(item, locale) for item in value) or "—"
    if value is None:
        return "—"
    text = str(value)
    return text.replace(".", ",") if locale == "fr" and isinstance(value, float) else text


def render(check: Check, locale: str = "fr") -> str:
    """Phrase du contrôle dans la langue demandée, depuis `sdm120_check.json` : le contrôle
    ne transporte que son code et ses paramètres (ADR 013)."""
    catalog = load_catalog(locale, "sdm120_check")
    params = {key: _display_value(value, locale) for key, value in check.params.items()}
    lines = [f"[{catalog['statuses'][check.status]}] {catalog['checks'][check.code]}"]
    reason = check.params.get("reason")
    if reason:
        lines.append(f"    {catalog['reasons'][reason]}")
    if check.status != NOT_EVALUATED:
        lines.append(f"    {catalog['details'][check.code].format_map(params)}")
    return "\n".join(lines)
