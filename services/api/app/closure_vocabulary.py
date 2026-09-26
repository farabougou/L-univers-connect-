"""Codes de clôture structurée d'une intervention (cahier des charges,
section 36 : « symptôme constaté, cause, action réalisée, pièce remplacée,
temps passé, résultat de la vérification »).

Inspirés de la codification des défaillances de la norme ISO 14224,
simplifiés pour le terrain CVC : choix fermés, courts, compréhensibles avec
des gants sur un téléphone. Ces codes sont les étiquettes dont dépendront le
diagnostic automatique, l'apprentissage et l'économie des actifs : on n'en
ajoute qu'avec un besoin réel, et jamais on n'en retire (versionner).
"""

from app.i18n import DEFAULT_LOCALE, load_catalog

CLOSURE_VOCABULARY_VERSION = "2026-09-24.1"

# Codes seulement : leurs libellés, en français et en anglais, sont dans le
# catalogue `shared/i18n/<langue>/closure.json` (ADR 013). Un test vérifie que
# les codes et le catalogue restent identiques.
SYMPTOMS = (
    "no_heating",
    "no_cooling",
    "insufficient_performance",
    "abnormal_noise",
    "vibration",
    "water_leak",
    "refrigerant_leak",
    "fault_code",
    "abnormal_consumption",
    "preventive_check",
    "other",
)

CAUSES = (
    "wear",
    "fouling",
    "refrigerant_loss",
    "electrical_fault",
    "control_setting",
    "sensor_fault",
    "component_failure",
    "external_cause",
    "lack_of_maintenance",
    "no_fault_found",
    "unknown",
)

ACTIONS = (
    "adjustment",
    "cleaning",
    "repair",
    "replacement",
    "refrigerant_recharge",
    "reset",
    "inspection_only",
    "temporary_fix",
    "other",
)

VERIFICATION_RESULTS = ("ok", "partial", "failed")

SECTIONS = {
    "symptoms": SYMPTOMS,
    "causes": CAUSES,
    "actions": ACTIONS,
    "verification_results": VERIFICATION_RESULTS,
}


def labels(section: str, locale: str = DEFAULT_LOCALE) -> dict[str, str]:
    """Code → libellé dans la langue demandée, dans l'ordre du vocabulaire."""
    catalog = load_catalog(locale, "closure")[section]
    return {code: catalog[code] for code in SECTIONS[section]}


def label(section: str, code: str | None, locale: str = DEFAULT_LOCALE) -> str | None:
    if code is None:
        return None
    return load_catalog(locale, "closure")[section].get(code)
