"""Comparison / Savings-Deviation : une lecture pure entre deux résultats déjà
persistés (`energy_normalized_results`), jamais un nouveau calcul stocké. Les
deux résultats comparés restent la seule source de vérité ; ceci ne fait que
les mettre en regard.

Notre indicateur de réduction est celui du moteur interne, pas un calcul
réglementaire : voir app/energy/__init__.py.
"""

from typing import Any


def compare_results(reference: dict[str, Any], analyzed: dict[str, Any]) -> dict[str, Any]:
    """`reference` et `analyzed` : lignes de `energy_normalized_results`
    (voir app/energy/normalization.py::get_normalized_result)."""
    if reference["normalized_consumption"] is None or analyzed["normalized_consumption"] is None:
        return {
            "comparable": False,
            "reason": "normalization_unavailable",
            "reference_result_id": reference["id"],
            "analyzed_result_id": analyzed["id"],
        }
    reference_value = reference["normalized_consumption"]
    analyzed_value = analyzed["normalized_consumption"]
    absolute_deviation = analyzed_value - reference_value
    percent_deviation = (
        round(absolute_deviation / reference_value * 100, 2) if reference_value else None
    )
    return {
        "comparable": True,
        "reference_result_id": reference["id"],
        "analyzed_result_id": analyzed["id"],
        "reference_normalized_consumption": reference_value,
        "analyzed_normalized_consumption": analyzed_value,
        "absolute_deviation": round(absolute_deviation, 3),
        "percent_deviation": percent_deviation,
        "reduced": absolute_deviation < 0,
    }
