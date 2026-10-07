"""Vocabulaire des signalements : alarmes et constats (ADR 013, sections 4.2 à 4.4).

Quatre informations séparées, qui ne se remplacent jamais l'une l'autre :
- la gravité (`severity`), définie par la réponse attendue ;
- l'état de la condition (`condition_state`) : la situation existe-t-elle
  encore ? (« revenue à la normale » au sens ISA-18.2) ;
- l'acquittement (`ack_state`) : quelqu'un en a-t-il pris connaissance ?
- le traitement (`handling_status`) : où en est la prise en charge ?
La nature est portée par `kind` (constats) ; les alarmes sont par nature des
alarmes. Les constats portent aussi un niveau de certitude.
"""

SEVERITIES = ("info", "warning", "major", "critical")
CONDITION_STATES = ("active", "cleared")
ACK_STATES = ("unacknowledged", "acknowledged")
HANDLING_STATUSES = ("open", "in_progress", "closed", "false_positive")
# Traitement en cours : un même problème n'ouvre qu'un seul constat.
HANDLING_OPEN = ("open", "in_progress")

CERTAINTIES = (
    "detected",
    "confirmed",
    "probable_cause",
    "hypothesis",
    "prediction",
    "recommendation",
    "simulation_result",
    "unavailable",
)

# Priorité de l'ordre de travail créé automatiquement, selon la gravité.
WORK_ORDER_PRIORITY = {"info": "low", "warning": "medium", "major": "high", "critical": "urgent"}
