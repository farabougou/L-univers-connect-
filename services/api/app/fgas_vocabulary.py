"""Codes de la fiche d'intervention fluides frigorigènes fluorés (CERFA
15497*04, articles R. 543-79 et R. 543-82 du code de l'environnement).

Document officiel fourni par Mohamed le 02/10/2026, qui débloque la ligne
« Documents réglementaires » de la matrice (`DEFERRED_DOCUMENT`). Codes
fermés, un pour chaque case à cocher du formulaire ([4] nature de
l'intervention, [12] dénomination ADR/RID) : on n'en ajoute qu'avec un
nouveau formulaire officiel, et jamais on n'en retire (versionner).
"""

from app.i18n import DEFAULT_LOCALE, load_catalog

FGAS_VOCABULARY_VERSION = "2026-10-02.1"

# [4] Nature de l'intervention : une ou plusieurs cases cochées.
NATURE_CODES = (
    "assembly",
    "commissioning",
    "modification",
    "maintenance",
    "leak_check_periodic",
    "leak_check_non_periodic",
    "decommissioning",
    "other",
)

# [12] Dénomination ADR/RID du déchet de fluide récupéré.
WASTE_CLASSIFICATION_CODES = (
    "un1078_non_flammable",
    "other_non_flammable",
    "un3161_flammable",
    "other_flammable",
)

SECTIONS = {
    "nature_of_intervention": NATURE_CODES,
    "waste_classification": WASTE_CLASSIFICATION_CODES,
}


def labels(section: str, locale: str = DEFAULT_LOCALE) -> dict[str, str]:
    """Code → libellé dans la langue demandée, dans l'ordre du vocabulaire."""
    catalog = load_catalog(locale, "fgas")[section]
    return {code: catalog[code] for code in SECTIONS[section]}
