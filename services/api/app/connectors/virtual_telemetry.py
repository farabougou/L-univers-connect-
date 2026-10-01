"""Virtual Protocol Adapter : génère une télémétrie dynamique réaliste pour
un équipement virtuel, sans aucun protocole réseau réel (ADR 017 §2.2,
Virtual Commissioning Lab).

Même principe que les connecteurs réels (`app/connectors/modbus.py`,
`app/connectors/bacnet.py`) : une fonction pure qui renvoie des valeurs,
jamais d'accès direct à la base ni au réseau — le démon qui l'appelle
(`scripts/virtual_commissioning_daemon.py`) reste seul responsable de
l'envoi par `POST /edge/measurements`, exactement comme pour un équipement
réel. C'est le palier SIMULATOR_TESTED pour ce connecteur (voir ADR 017 §1) :
aucune de ces valeurs ne doit jamais être présentée comme une mesure réelle
sans que `origin` le dise explicitement (ADR 013, aucune valeur simulée
affichée comme mesurée).

Six profils, repris tels quels de `tests/bacnet_lab.py` (CVC, froid,
production électrique de secours, VRV/DRV, réseaux thermiques urbains,
comptage) — mêmes catégories d'équipement, cette fois exprimées avec les
classes de points de `app/point_vocabulary.py` plutôt qu'avec des objets
BACnet, pour qu'un point créé soit directement validable et exploitable par
le reste de la plateforme (FDD, alertes, chronologie…) sans traduction.

Déterministe à l'horodatage près (`now`) : rejouer le même `now` pour le même
point donne toujours la même valeur — aucun état mutable, aucun compteur en
mémoire d'un appel à l'autre. `now` est toujours interprété en UTC, comme le
reste de la plateforme (ADR 012, convention horaire).
"""

import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime

NumberValue = float
BooleanValue = bool

# Origine d'une ancre temporelle pour les compteurs cumulatifs (ex. énergie
# active totale) : une valeur croissante avec le temps réel, jamais remise à
# zéro entre deux appels, mais ancrée à une date récente plutôt qu'à l'epoch
# Unix pour rester un ordre de grandeur réaliste (voir `hourly_increase`).
_METER_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class VirtualPointSpec:
    """Décrit un point simulé : comment le créer dans le registre
    (`app.points.create_point`, classe/unité/type déjà valides pour
    `app.point_vocabulary`) et comment générer sa valeur dans le temps."""

    code_suffix: str
    name: str
    point_class: str
    value_type: str  # "number" ou "boolean" (pas "multistate" pour l'instant)
    unit: str | None = None
    # --- séries numériques ---
    base: float = 0.0
    diurnal_amplitude: float = 0.0  # cycle jour/nuit, +/- cette valeur
    noise: float = 0.0  # bruit de mesure borné, +/- cette valeur
    hourly_increase: float = 0.0  # compteur cumulatif (ex. énergie active)
    min_value: float | None = None
    max_value: float | None = None
    # --- séries booléennes ---
    active_hours: tuple[int, int] | None = None  # (début, fin), heure UTC ; None = toujours faux


def _bounded_noise(point_code: str, now: datetime, amplitude: float) -> float:
    """Bruit pseudo-aléatoire borné, déterministe pour (point, minute) —
    jamais `random` non amorcé : un test rejoue exactement la même valeur
    avec le même horodatage."""
    if amplitude == 0.0:
        return 0.0
    bucket = now.strftime("%Y-%m-%dT%H:%M")
    digest = hashlib.sha256(f"{point_code}:{bucket}".encode()).hexdigest()
    fraction = int(digest[:8], 16) / 0xFFFFFFFF  # dans [0, 1)
    return (fraction * 2 - 1) * amplitude


def generate_value(spec: VirtualPointSpec, *, now: datetime) -> NumberValue | BooleanValue:
    """Valeur simulée de `spec` à l'instant `now` (UTC)."""
    if spec.value_type == "boolean":
        if spec.active_hours is None:
            return False
        start, end = spec.active_hours
        return start <= now.hour < end

    value = spec.base
    if spec.diurnal_amplitude:
        hour_fraction = now.hour + now.minute / 60
        value += spec.diurnal_amplitude * math.sin(2 * math.pi * hour_fraction / 24)
    if spec.hourly_increase:
        elapsed_hours = (now - _METER_EPOCH).total_seconds() / 3600
        value += spec.hourly_increase * elapsed_hours
    value += _bounded_noise(spec.code_suffix, now, spec.noise)
    if spec.min_value is not None:
        value = max(spec.min_value, value)
    if spec.max_value is not None:
        value = min(spec.max_value, value)
    return round(value, 2)


# Six profils, un par catégorie d'équipement — jamais présentés comme une
# liste exhaustive des équipements GTB réels, seulement comme un jeu de
# départ réaliste pour le développement, les tests et la CI (même principe
# et mêmes catégories que `tests/bacnet_lab.py::PROFILES`).
PROFILES: dict[str, tuple[VirtualPointSpec, ...]] = {
    "cta": (
        VirtualPointSpec(
            "t_depart",
            "Température départ CTA",
            "supply_air_temperature_sensor",
            "number",
            "Cel",
            base=18.0,
            diurnal_amplitude=1.5,
            noise=0.2,
            min_value=10.0,
            max_value=30.0,
        ),
        VirtualPointSpec(
            "pression_refoulement",
            "Pression refoulement",
            "pressure_sensor",
            "number",
            "kPa",
            base=350.0,
            noise=5.0,
            min_value=0.0,
        ),
        VirtualPointSpec(
            "consigne_depart",
            "Consigne départ CTA",
            "temperature_setpoint",
            "number",
            "Cel",
            base=19.0,
        ),
        VirtualPointSpec("defaut_general", "Défaut général CTA", "fault_status", "boolean"),
        VirtualPointSpec(
            "marche_ventilateur",
            "Marche ventilateur",
            "run_status",
            "boolean",
            active_hours=(6, 20),
        ),
        # Les deux points qui alimentent la règle FDD déjà écrite
        # (`simultaneous_heating_cooling`, app/rules.py) — à l'état sain,
        # jamais ouvertes en même temps (voir incrément 2, scénarios de
        # panne, pour le cas contraire déclenché volontairement).
        VirtualPointSpec(
            "vanne_chaude",
            "Position vanne chaude",
            "heating_valve_position",
            "number",
            "%",
            base=0.0,
            min_value=0.0,
            max_value=100.0,
        ),
        VirtualPointSpec(
            "vanne_froide",
            "Position vanne froide",
            "cooling_valve_position",
            "number",
            "%",
            base=0.0,
            min_value=0.0,
            max_value=100.0,
        ),
    ),
    "groupe_froid": (
        VirtualPointSpec(
            "t_eau_glacee_depart",
            "Température eau glacée départ",
            "supply_water_temperature_sensor",
            "number",
            "Cel",
            base=7.0,
            noise=0.3,
            min_value=4.0,
            max_value=12.0,
        ),
        VirtualPointSpec(
            "t_eau_glacee_retour",
            "Température eau glacée retour",
            "return_water_temperature_sensor",
            "number",
            "Cel",
            base=12.5,
            noise=0.3,
            min_value=8.0,
            max_value=16.0,
        ),
        VirtualPointSpec("defaut_compresseur", "Défaut compresseur", "fault_status", "boolean"),
        VirtualPointSpec(
            "marche_compresseur",
            "Marche compresseur",
            "run_status",
            "boolean",
            active_hours=(6, 20),
        ),
    ),
    "groupe_electrogene": (
        VirtualPointSpec("defaut_groupe", "Défaut groupe électrogène", "fault_status", "boolean"),
        # Groupe de secours : à l'arrêt par défaut (jamais "actif" hors
        # scénario de panne volontaire, voir incrément 2).
        VirtualPointSpec("marche_groupe", "Marche groupe électrogène", "run_status", "boolean"),
    ),
    "vrv_drv": (
        VirtualPointSpec(
            "t_air_interieur",
            "Température air intérieur zone 1",
            "temperature_sensor",
            "number",
            "Cel",
            base=22.0,
            noise=0.3,
            min_value=15.0,
            max_value=30.0,
        ),
        VirtualPointSpec(
            "t_air_exterieur",
            "Température air extérieur",
            "temperature_sensor",
            "number",
            "Cel",
            base=8.0,
            diurnal_amplitude=4.0,
            noise=0.3,
            min_value=-10.0,
            max_value=40.0,
        ),
        VirtualPointSpec(
            "consigne_zone", "Consigne zone 1", "temperature_setpoint", "number", "Cel", base=21.0
        ),
        VirtualPointSpec(
            "marche_zone", "Marche zone 1", "run_status", "boolean", active_hours=(6, 20)
        ),
    ),
    "sous_station_thermique": (
        VirtualPointSpec(
            "t_depart_reseau",
            "Température départ réseau",
            "supply_water_temperature_sensor",
            "number",
            "Cel",
            base=75.0,
            noise=1.0,
            min_value=60.0,
            max_value=90.0,
        ),
        VirtualPointSpec(
            "t_retour_reseau",
            "Température retour réseau",
            "return_water_temperature_sensor",
            "number",
            "Cel",
            base=55.0,
            noise=1.0,
            min_value=40.0,
            max_value=70.0,
        ),
        VirtualPointSpec(
            "pression_reseau",
            "Pression réseau",
            "pressure_sensor",
            "number",
            "bar",
            base=4.2,
            noise=0.1,
            min_value=0.0,
        ),
        VirtualPointSpec(
            "etat_sous_station",
            "Sous-station active",
            "run_status",
            "boolean",
            active_hours=(0, 24),
        ),
    ),
    "comptage": (
        VirtualPointSpec(
            "energie_active_totale",
            "Énergie active totale",
            "energy_meter_reading",
            "number",
            "kW.h",
            base=154302.0,
            hourly_increase=2.0,
        ),
        VirtualPointSpec(
            "puissance_active",
            "Puissance active",
            "electric_power_sensor",
            "number",
            "kW",
            base=48.5,
            diurnal_amplitude=10.0,
            noise=1.0,
            min_value=0.0,
        ),
    ),
}


def list_profiles() -> list[str]:
    return sorted(PROFILES)


def profile_points(profile: str) -> tuple[VirtualPointSpec, ...]:
    try:
        return PROFILES[profile]
    except KeyError:
        raise ValueError(
            f"profil Virtual Commissioning Lab inconnu : {profile!r} "
            f"(profils disponibles : {', '.join(list_profiles())})"
        ) from None


def generate_profile_values(
    profile: str, *, now: datetime
) -> dict[str, NumberValue | BooleanValue]:
    """Valeur simulée de chaque point du profil à l'instant `now`, par
    `code_suffix` — la forme attendue par
    `scripts/virtual_commissioning_daemon.py` pour construire les mesures."""
    return {spec.code_suffix: generate_value(spec, now=now) for spec in profile_points(profile)}
