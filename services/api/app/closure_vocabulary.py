"""Codes de clôture structurée d'une intervention (cahier des charges,
section 36 : « symptôme constaté, cause, action réalisée, pièce remplacée,
temps passé, résultat de la vérification »).

Inspirés de la codification des défaillances de la norme ISO 14224,
simplifiés pour le terrain CVC : choix fermés, courts, compréhensibles avec
des gants sur un téléphone. Ces codes sont les étiquettes dont dépendront le
diagnostic automatique, l'apprentissage et l'économie des actifs : on n'en
ajoute qu'avec un besoin réel, et jamais on n'en retire (versionner).
"""

CLOSURE_VOCABULARY_VERSION = "2026-09-23.1"

SYMPTOMS = {
    "no_heating": "Pas de chauffage",
    "no_cooling": "Pas de froid",
    "insufficient_performance": "Performance insuffisante",
    "abnormal_noise": "Bruit anormal",
    "vibration": "Vibrations",
    "water_leak": "Fuite d'eau",
    "refrigerant_leak": "Fuite de fluide frigorigène",
    "fault_code": "Code défaut affiché",
    "abnormal_consumption": "Consommation anormale",
    "preventive_check": "Aucun (contrôle préventif)",
    "other": "Autre",
}

CAUSES = {
    "wear": "Usure",
    "fouling": "Encrassement / colmatage",
    "refrigerant_loss": "Perte de fluide",
    "electrical_fault": "Défaut électrique",
    "control_setting": "Réglage ou programmation",
    "sensor_fault": "Capteur défaillant",
    "component_failure": "Composant défaillant",
    "external_cause": "Cause extérieure (coupure, gel, choc…)",
    "lack_of_maintenance": "Défaut d'entretien",
    "no_fault_found": "Aucun défaut trouvé",
    "unknown": "Cause non identifiée",
}

ACTIONS = {
    "adjustment": "Réglage",
    "cleaning": "Nettoyage",
    "repair": "Réparation",
    "replacement": "Remplacement de pièce",
    "refrigerant_recharge": "Recharge de fluide",
    "reset": "Réarmement",
    "inspection_only": "Contrôle seul",
    "temporary_fix": "Dépannage provisoire",
    "other": "Autre",
}

VERIFICATION_RESULTS = {
    "ok": "Fonctionnement rétabli",
    "partial": "Rétabli partiellement",
    "failed": "Non rétabli",
}
