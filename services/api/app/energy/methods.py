"""Méthodes de normalisation climatique du moteur interne — jamais une
méthode réglementaire (OPERAT a la sienne, non implémentée ici : voir
app/energy/__init__.py). Chaque méthode est nommée et versionnée
explicitement ; une référence énergétique (`baseline.py`) fige le couple
(méthode, version) qu'elle utilise pour toujours, même si une version plus
récente apparaît un jour — jamais de recalcul silencieux d'un résultat déjà
produit.
"""

from collections.abc import Callable

NormalizationMethod = Callable[..., float | None]


def _degree_day_ratio_v1(
    *, raw_consumption: float, degree_days_analyzed: float, degree_days_reference: float
) -> float | None:
    """Consommation observée, ramenée aux degrés-jours de la période de
    référence : ce que la consommation aurait été si la période analysée
    avait connu le même climat que la référence. Aucun résultat si la
    période analysée n'a aucun degré-jour (division impossible, pas une
    approximation par zéro)."""
    if degree_days_analyzed <= 0:
        return None
    return raw_consumption / degree_days_analyzed * degree_days_reference


METHOD_REGISTRY: dict[str, dict[str, NormalizationMethod]] = {
    "degree_day_ratio": {"v1": _degree_day_ratio_v1},
}


def is_known_method(method: str, method_version: str) -> bool:
    return method in METHOD_REGISTRY and method_version in METHOD_REGISTRY[method]


def get_method(method: str, method_version: str) -> NormalizationMethod:
    return METHOD_REGISTRY[method][method_version]
