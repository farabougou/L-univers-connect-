"""Energy Intelligence Core (M5, décision de Mohamed du 24/09/2026).

Moteur interne d'analyse et de normalisation énergétique — indépendant de
toute réglementation nationale. Chaîne :

    Telemetry → Energy Aggregation → Weather Context → Baseline
    → Normalized Performance → Comparison → Savings / Deviation → Reporting

Frontière stricte, non négociable : ce paquet ne connaît ni OPERAT, ni BACS,
ni aucun format réglementaire. Les futures couches réglementaires
(`Regulatory / Reporting Adapters` : OPERAT, BACS, ESG, futurs dispositifs)
liront les résultats produits ici sans jamais que ce moteur ait besoin de
les connaître. Une évolution d'un format réglementaire ne touche jamais ce
paquet.

Notre méthode de calcul (voir `normalization.py`) est la nôtre : versionnée,
documentée, jamais présentée comme équivalente à un calcul réglementaire
(OPERAT en particulier a sa propre méthode officielle, non implémentée ici).
"""
