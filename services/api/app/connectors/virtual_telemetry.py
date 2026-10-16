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

Sept profils : les six repris tels quels de `tests/bacnet_lab.py` (CVC,
froid, production électrique de secours, VRV/DRV, réseaux thermiques
urbains, comptage), plus un septième (02/10/2026, demande explicite de
Mohamed) : pompes. Mêmes catégories d'équipement, exprimées avec les
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
        # Volet d'air neuf (économiseur) : modulation saine autour d'une
        # position moyenne — le scénario `economiseur_bloque` l'immobilise.
        VirtualPointSpec(
            "volet_air_neuf",
            "Position volet d'air neuf",
            "economizer_damper_position",
            "number",
            "%",
            base=50.0,
            diurnal_amplitude=20.0,
            noise=2.0,
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
    # Septième profil (02/10/2026, demande explicite de Mohamed : « pompes »
    # dans la liste des équipements à simuler) — uniquement des classes de
    # points déjà existantes (run_status, fault_status, pressure_sensor,
    # electric_power_sensor) : aucun ajout à app/point_vocabulary.py n'était
    # nécessaire, conforme à la « règle des trois » du fichier (une classe
    # s'ajoute avec un cas réel, jamais au cas où).
    "pompe": (
        VirtualPointSpec(
            "marche",
            "Marche pompe",
            "run_status",
            "boolean",
            active_hours=(0, 24),
        ),
        VirtualPointSpec("defaut_pompe", "Défaut pompe", "fault_status", "boolean"),
        VirtualPointSpec(
            "pression_refoulement",
            "Pression refoulement pompe",
            "pressure_sensor",
            "number",
            "bar",
            base=3.5,
            noise=0.1,
            min_value=0.0,
            max_value=8.0,
        ),
        VirtualPointSpec(
            "puissance_absorbee",
            "Puissance absorbée pompe",
            "electric_power_sensor",
            "number",
            "kW",
            base=5.5,
            diurnal_amplitude=0.5,
            noise=0.2,
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


@dataclass(frozen=True)
class FailureScenario:
    """Panne déclenchable sur un profil (ADR 017 §2.2, incrément 2) — une
    perturbation volontaire de la télémétrie saine, jamais un deuxième moyen
    de produire une valeur normale. Trois formes, cumulables :

    - `overrides` : valeur fixe, imposée quelle que soit l'heure (ex. une
      vanne bloquée en position) — ignore les bornes normales du point.
    - `drift_per_hour` : dérive linéaire à partir de la valeur saine au
      moment où le scénario démarre (`scenario_started_at`), elle aussi hors
      bornes — une vraie dérive de capteur doit pouvoir sortir de la plage
      normale, sinon ce n'est pas une panne.
    - `suppressed` : plus aucune valeur générée pour ce point — simule une
      perte de communication (totale si elle couvre tous les points du
      profil, partielle sinon)."""

    name: str
    profile: str
    description: str
    overrides: dict[str, float | bool] | None = None
    drift_per_hour: dict[str, float] | None = None
    suppressed: frozenset[str] = frozenset()


# Scénarios nommés par profil — choisis pour retomber sur des mécanismes déjà
# construits et testés ailleurs dans la plateforme, jamais un nouveau moyen de
# produire une valeur : `vanne_bloquee` et `chauffage_froid_simultane`
# alimentent la règle FDD à deux points déjà écrite
# (`app.rules.CorrelationRule`, `simultaneous_heating_cooling`),
# `capteur_derive`/`derive_puissance`/`derive_echangeur` la règle de
# projection de tendance (`app.rules.TrendProjectionRule`), `cavitation` et
# `surchauffe_retour` une règle de seuil simple (`app.rules.ThresholdRule`),
# `releve_incoherent` une valeur immédiatement impossible (distincte d'une
# dérive progressive) que `app.quality_flags` qualifie dès la réception.
# `perte_communication` (ci-dessous, `communication_loss_scenario`) reste
# générique à tout profil, aucune entrée dédiée n'est nécessaire ici.
_SCENARIOS: dict[str, FailureScenario] = {
    "economiseur_bloque": FailureScenario(
        name="economiseur_bloque",
        profile="cta",
        description=(
            "Le volet d'air neuf reste bloqué en position fermée, quelle que "
            "soit la consigne (économiseur bloqué) — déclenche la règle FDD "
            "desired_state_divergence (app/rules.py) quand un état souhaité "
            "est déclaré sur ce point (app/desired_states.py)."
        ),
        overrides={"volet_air_neuf": 5.0},
    ),
    "capteur_derive": FailureScenario(
        name="capteur_derive",
        profile="cta",
        description=(
            "Le capteur de température de départ dérive progressivement, "
            "hors de sa plage normale (10-30°C)."
        ),
        drift_per_hour={"t_depart": 4.0},
    ),
    "vanne_bloquee": FailureScenario(
        name="vanne_bloquee",
        profile="cta",
        description="La vanne chaude reste bloquée ouverte, quelle que soit la demande.",
        overrides={"vanne_chaude": 80.0},
    ),
    "chauffage_froid_simultane": FailureScenario(
        name="chauffage_froid_simultane",
        profile="cta",
        description=(
            "Vannes chaude et froide ouvertes en même temps — déclenche la "
            "règle FDD simultaneous_heating_cooling (app/rules.py)."
        ),
        overrides={"vanne_chaude": 60.0, "vanne_froide": 60.0},
    ),
    "surchauffe_retour": FailureScenario(
        name="surchauffe_retour",
        profile="groupe_froid",
        description=(
            "Eau glacée retour anormalement chaude (refroidissement "
            "insuffisant) — déclenche une règle de seuil simple."
        ),
        overrides={"t_eau_glacee_retour": 22.0},
    ),
    "derive_echangeur": FailureScenario(
        name="derive_echangeur",
        profile="groupe_froid",
        description=(
            "L'échangeur s'encrasse progressivement : la température d'eau "
            "glacée départ dérive à la hausse, hors de sa plage normale."
        ),
        drift_per_hour={"t_eau_glacee_depart": 0.5},
    ),
    "cavitation": FailureScenario(
        name="cavitation",
        profile="pompe",
        description=(
            "Pression de refoulement anormalement basse (cavitation ou "
            "désamorçage) — déclenche une règle de seuil simple."
        ),
        overrides={"pression_refoulement": 0.4},
    ),
    "derive_puissance": FailureScenario(
        name="derive_puissance",
        profile="pompe",
        description=(
            "Usure progressive des roulements : la puissance absorbée dérive "
            "à la hausse avec le temps."
        ),
        drift_per_hour={"puissance_absorbee": 0.3},
    ),
    "releve_incoherent": FailureScenario(
        name="releve_incoherent",
        profile="comptage",
        description=(
            "Relevé immédiatement impossible (puissance négative sur un "
            "compteur de consommation) — valeur incohérente, jamais une "
            "dérive progressive : qualifiée dès la réception "
            "(app.quality_flags), jamais évaluée par une règle FDD."
        ),
        overrides={"puissance_active": -500.0},
    ),
}


def communication_loss_scenario(profile: str) -> FailureScenario:
    """Panne générique, valable pour n'importe quel profil : plus aucune
    mesure reçue pour l'équipement (passerelle injoignable) — à terme
    détectée par la surveillance de fraîcheur déjà construite
    (`app.monitoring.evaluate_data_freshness`, `DATA_BECAME_STALE`), jamais
    par ce module qui ne fait qu'arrêter d'envoyer."""
    return FailureScenario(
        name="perte_communication",
        profile=profile,
        description="Plus aucune mesure reçue pour cet équipement (passerelle injoignable).",
        suppressed=frozenset(spec.code_suffix for spec in profile_points(profile)),
    )


def list_failure_scenarios(profile: str) -> list[str]:
    """Noms valides pour `failure_scenario(profile, ...)` — toujours au moins
    `perte_communication`, générique à tout profil."""
    names = {"perte_communication"}
    names.update(name for name, scenario in _SCENARIOS.items() if scenario.profile == profile)
    return sorted(names)


def failure_scenario(profile: str, name: str) -> FailureScenario:
    if name == "perte_communication":
        return communication_loss_scenario(profile)
    scenario = _SCENARIOS.get(name)
    if scenario is None or scenario.profile != profile:
        raise ValueError(
            f"scénario de panne inconnu pour le profil {profile!r} : {name!r} "
            f"(scénarios disponibles : {', '.join(list_failure_scenarios(profile))})"
        )
    return scenario


def generate_profile_values(
    profile: str,
    *,
    now: datetime,
    scenario: FailureScenario | None = None,
    scenario_started_at: datetime | None = None,
) -> dict[str, NumberValue | BooleanValue]:
    """Valeur simulée de chaque point du profil à l'instant `now`, par
    `code_suffix` — la forme attendue par
    `scripts/virtual_commissioning_daemon.py` pour construire les mesures.

    Avec `scenario` : un point supprimé (`suppressed`) est absent du
    résultat — c'est au bénéficiaire (le démon) de ne rien envoyer pour lui,
    jamais à cette fonction d'inventer une valeur de remplacement. Un point
    en dérive (`drift_per_hour`) prend comme point de départ sa valeur saine
    au moment de l'appel, puis s'en écarte avec le temps écoulé depuis
    `scenario_started_at` (requis dès qu'une dérive est utilisée)."""
    overrides = scenario.overrides or {} if scenario else {}
    drifts = scenario.drift_per_hour or {} if scenario else {}
    suppressed = scenario.suppressed if scenario else frozenset()

    values: dict[str, NumberValue | BooleanValue] = {}
    for spec in profile_points(profile):
        if spec.code_suffix in suppressed:
            continue
        if spec.code_suffix in overrides:
            values[spec.code_suffix] = overrides[spec.code_suffix]
        elif spec.code_suffix in drifts:
            if scenario_started_at is None:
                raise ValueError("scenario_started_at est requis pour un scénario avec dérive")
            healthy_value = generate_value(spec, now=now)
            elapsed_hours = (now - scenario_started_at).total_seconds() / 3600
            values[spec.code_suffix] = round(
                healthy_value + drifts[spec.code_suffix] * elapsed_hours, 2
            )
        else:
            values[spec.code_suffix] = generate_value(spec, now=now)
    return values
