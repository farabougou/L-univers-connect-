# BACS / GTB (Building Automation and Control Systems)

## Référence officielle

- Texte : articles R175-1 à R175-6 du code de la construction et de
  l'habitation (« décret BACS »), sur Légifrance.
- Objet : obligation d'équiper certains bâtiments tertiaires d'un système
  de GTB (seuil de puissance de chauffage/refroidissement/climatisation),
  avec des fonctions minimales de suivi, d'analyse et d'alerte.

Avertissement de méthode : ce document reprend les fonctions demandées par
Mohamed le 02/10/2026 (« suivi et historique énergétique, analyse
d'efficacité, interopérabilité, exploitation/maintenance et inspection »,
« conservation mensuelle des données pendant cinq ans ») et les met en
regard de notre architecture. Il ne prétend pas reproduire le texte exact
des articles R175-1 à R175-6 — à vérifier avec un texte consolidé avant
toute communication officielle de conformité.

## Ce qu'ENORYX doit prévoir

Suivi et historique énergétique, analyse d'efficacité, interopérabilité,
exploitation/maintenance et inspection, conservation mensuelle des données
pendant cinq ans pour les systèmes concernés.

## État réel du code (02/10/2026)

Contrairement aux autres fiches de ce dossier, BACS ne demande **aucun
nouveau code** : chaque fonction listée est déjà couverte par une brique
existante, construite pour d'autres raisons mais qui s'applique ici sans
modification.

| Fonction demandée | Brique existante | Statut |
|---|---|---|
| Suivi et historique énergétique | `app/energy/` (agrégation, normalisation), `measurements` (jamais réécrit) | ✅ Fait |
| Conservation ≥ 5 ans, au pas mensuel | Aucune donnée n'est jamais supprimée (`measurements`, `audit_log`, `config_versions`, `energy_normalized_results`, `weather_observations`) ; aucune tâche de purge n'existe dans le dépôt | ✅ Fait par construction — la question ne se pose pas puisque rien n'est effacé |
| Analyse d'efficacité | `app/energy/comparison.py` (référence vs réel) ; règles FDD (`app/rules.py`) : seuil, écart à la consigne, corrélation, cycles courts, projection | ✅ Fait |
| Interopérabilité | Connecteurs protocolaires indépendants du fabricant (Modbus, BACnet, OPC UA, MQTT, `app/connectors/`), vocabulaire aligné sur Brick (ADR 001) | ✅ Fait |
| Exploitation/maintenance | GMAO (ordres de travail, interventions, clôture structurée ISO 14224) | ✅ Fait |
| Inspection | Constats (`findings`), chronologie fusionnée (`app/timeline.py`), passeport numérique | ✅ Fait |

## Décision

**KEEP** — aucun chantier à ouvrir. Si une inspection ou un audit futur
demande un export spécifique (format imposé par un contrôleur, par
exemple), il sera traité comme un nouvel adaptateur au-dessus des données
déjà collectées, jamais comme une nouvelle collecte.
