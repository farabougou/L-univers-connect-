# Architecture Addendum V2 — ajout au cahier des charges

Formulé par Mohamed le 23 septembre 2026, en complément du cahier des charges
(`Cahier_des_charges_Physical_Asset_Intelligence_OS_v1.1.docx`), de la vision cible
(`vision-cible-physical-asset-intelligence-automation-os.md`, ADR 004) et de l'exigence
Spatial & BIM Engine (`spatial-bim-engine.md`, ADR 011). Repris ici mot pour mot comme
document de référence ; voir l'ADR 012 pour l'audit du code existant, l'impact
architectural et le plan de migration qui en découlent.

---

ARCHITECTURE ADDENDUM V2 — À AJOUTER AU CAHIER DES CHARGES EXISTANT

Ce message complète les directives précédentes. Il ne remplace pas l'architecture
existante et ne doit surtout pas provoquer une réécriture complète du projet.

Après revue approfondie de l'architecture cible, je veux que les capacités suivantes
soient prévues dans les fondations du Physical Asset Intelligence & Automation OS.

L'objectif reste :

Observe → Understand → Decide → Simulate si nécessaire → Authorize → Execute → Verify →
Learn

---

## 1. Commissioning & Continuous Commissioning Engine

Ajouter une vraie couche de mise en service et de validation des installations.

Cycle cible :

Discover → Identify → Map → Commission → Validate → Operate → Continuously Recommission

Elle devra pouvoir détecter notamment :

- points incorrectement mappés ;
- capteurs incohérents ;
- équipements mal configurés ;
- horaires contradictoires ;
- commandes qui ne produisent pas l'effet attendu ;
- configurations qui dérivent dans le temps ;
- équipements qui ne respectent plus leur comportement attendu.

La plateforme ne doit pas considérer qu'un équipement connecté est automatiquement
correctement configuré.

---

## 2. Fault Detection & Diagnostics — FDD

Séparer conceptuellement :

Anomaly Detection ≠ Fault Detection ≠ Diagnosis ≠ Prediction

Créer une architecture FDD combinant progressivement :

- règles déterministes ;
- règles d'ingénierie ;
- statistiques ;
- modèles physiques lorsque disponibles ;
- comparaison avec des équipements similaires ;
- ML ;
- IA pour assister l'explication.

Un LLM ne doit jamais constituer à lui seul le mécanisme de diagnostic ou de commande.

---

## 3. Data Quality & Sensor Trust Engine

Chaque flux/point doit pouvoir avoir des métadonnées de qualité et de confiance.

Prévoir notamment :

- freshness ;
- completeness ;
- valeurs manquantes ;
- valeurs figées ;
- fréquence d'échantillonnage ;
- valeurs physiquement impossibles ;
- dérive ;
- calibration connue ;
- provenance ;
- qualité du mapping ;
- confiance de l'auto-discovery ;
- timestamps ;
- unité ;
- transformation appliquée.

Prévoir un Data Quality / Trust Score exploitable par les autres moteurs.

Une donnée de mauvaise qualité ne doit pas être utilisée aveuglément par l'IA ou
l'automatisation.

---

## 4. Desired State / Actual State

Cette distinction doit devenir fondamentale dans le Digital Twin.

Exemple :

Desired State:
Light = OFF

Actual State:
Light = ON

Le système doit pouvoir détecter cette divergence.

Cycle :

Command → Acknowledgement → Observation → Verification → Reconciliation

Ne jamais considérer qu'une commande envoyée signifie automatiquement qu'elle a été
exécutée.

---

## 5. Command Arbitration Engine

Prévoir dès maintenant la gestion des conflits de commandes.

Exemple :

- calendrier demande 24°C ;
- utilisateur demande 22°C ;
- Energy Engine demande 25°C ;
- technicien active un override ;
- automatisation demande OFF.

Le système doit déterminer la commande applicable selon des politiques déterministes.

Chaque intention de commande doit pouvoir contenir :

- source ;
- actor ;
- priorité ;
- justification ;
- timestamp ;
- durée ;
- expiration ;
- tenant ;
- asset ;
- policy applicable ;
- état précédent ;
- résultat.

Prévoir notamment :

- priorité ;
- override temporaire ;
- expiration automatique ;
- retour au programme normal ;
- prévention des boucles de commandes ;
- gestion des conflits.

---

## 6. Safety & Policy Engine

Séparer explicitement :

Recommendation
Automation
Control
Safety

L'IA peut recommander ou optimiser.

Elle ne doit pas contourner les règles déterministes de sécurité.

Une commande physique doit passer par :

Identity → Authorization → Policy → Safety Constraints → Command Arbitration → Edge →
Controller → Verification

Les protections locales et interlocks des équipements restent prioritaires.

---

## 7. Device Identity / PKI

Chaque Edge Gateway et appareil géré doit avoir une identité vérifiable.

Prévoir :

- provisioning ;
- identité unique ;
- certificats ;
- rotation ;
- révocation ;
- secrets ;
- authentification mutuelle lorsque pertinent ;
- inventaire ;
- état de sécurité ;
- firmware ;
- dernière communication ;
- propriétaire/tenant ;
- site associé.

---

## 8. Edge Fleet Management

Ne pas concevoir Edge uniquement pour 10 gateways.

Préparer une architecture pouvant administrer à terme une grande flotte.

Prévoir :

- remote configuration ;
- OTA updates signées ;
- versions ;
- staged rollout ;
- canary deployments ;
- rollback ;
- health monitoring ;
- compatibility matrix ;
- configuration versioning ;
- logs ;
- métriques ;
- synchronisation ;
- offline mode ;
- store-and-forward.

Une perte Internet ne doit pas arrêter les automatismes locaux essentiels.

---

## 9. Connector Certification Framework

Le Connector SDK doit avoir un système de qualification.

Statuts possibles :

Experimental → Verified → Certified

Tester notamment :

- lecture ;
- écriture ;
- timeout ;
- reconnexion ;
- perte réseau ;
- données invalides ;
- permissions ;
- compatibilité versions ;
- performances ;
- sécurité ;
- récupération après panne.

Aucun connecteur tiers ne doit obtenir automatiquement des droits de contrôle sensibles.

---

## 10. Site Knowledge Graph enrichi

Le Knowledge Graph ne doit pas uniquement représenter les équipements.

Il doit progressivement comprendre les relations :

contains
locatedIn
hasPart
feeds
poweredBy
measuredBy
controlledBy
connectedTo
servedBy
maintainedBy
dependsOn
protectedBy

Exemple :

Building
→ contains Room
→ servedBy HVAC Zone
→ fedBy AHU
→ poweredBy Electrical Panel
→ measuredBy Meter
→ maintainedBy Provider.

Cela permettra notamment l'analyse d'impact d'une panne.

---

## 11. Asset Lifecycle Management

Chaque actif doit avoir un cycle de vie.

Exemple :

Designed → Procured → Installed → Commissioned → Operational → Serviced → Replaced →
Decommissioned

Conserver l'historique même lorsqu'un équipement physique est remplacé.

Ne pas réutiliser l'identité technique de l'ancien équipement pour le nouveau.

---

## 12. Operational Memory

Créer une mémoire technique structurée pour chaque actif/site.

Elle doit pouvoir relier :

- alarmes ;
- incidents ;
- interventions ;
- changements de configuration ;
- commandes ;
- overrides ;
- pièces remplacées ;
- techniciens ;
- documents ;
- commentaires ;
- versions ;
- données avant/après ;
- causes identifiées ;
- résultats des interventions.

Objectif :

pouvoir expliquer plusieurs années plus tard pourquoi une configuration ou une décision
technique existe.

---

## 13. Asset Digital Passport / QR

Prévoir un Digital Passport par actif.

Un QR/NFC ou autre identifiant pourra ouvrir, selon les permissions :

Asset → Digital Twin → état → documentation → alarmes → historique → maintenance →
pièces → procédures → actions autorisées

Cela doit fonctionner correctement depuis l'application mobile.

---

## 14. Scenario / What-if Engine

Étendre le Simulation Engine afin de pouvoir créer des scénarios virtuels sans modifier
immédiatement l'installation réelle.

Exemple :

REAL TWIN
→ Scenario A : nouvelle consigne
→ Scenario B : nouveau planning
→ Scenario C : nouvel équipement
→ Scenario D : stratégie énergétique différente.

Comparer lorsque les modèles disponibles le permettent :

- énergie ;
- coût ;
- confort ;
- émissions ;
- charge ;
- fonctionnement ;
- contraintes ;
- maintenance.

Les résultats simulés doivent être explicitement identifiés comme estimations et ne
jamais être présentés comme des mesures réelles.

---

## 15. Asset Economics Engine

Ajouter une dimension économique aux actifs.

Pouvoir associer progressivement :

- coût énergétique ;
- coût maintenance ;
- coût pièces ;
- coût interventions ;
- temps d'arrêt ;
- contrats ;
- garantie ;
- coût historique ;
- coût estimé futur ;
- remplacement ;
- durée de vie.

Cela doit permettre d'aider le client à comparer différentes stratégies sans prendre
automatiquement les décisions financières à sa place.

---

## 16. Energy Flexibility / DER Layer

Notre Energy Engine doit être conçu pour représenter :

Grid + Solar + Battery + Generator + EV Charger + HVAC + Heat Pump + Flexible Loads

Préparer l'architecture pour des standards et mécanismes futurs de Demand Response /
Grid Interaction sans les rendre obligatoires au lancement.

---

## 17. Semantic Interoperability

Notre Universal Asset Model reste notre modèle interne.

Mais il doit être conçu pour pouvoir mapper/importer/exporter progressivement des
standards/ontologies pertinents :

- Brick ;
- Project Haystack ;
- ASHRAE 223 ;
- IFC/BIM ;
- Asset Administration Shell ;
- autres standards nécessaires selon les domaines.

Ne pas faire dépendre tout notre cœur d'un seul standard externe.

Créer des adapters/mappings versionnés.

---

## 18. Spatial/BIM Integration

Conserver la directive précédente :

Spatial Model ↔ Asset Graph ↔ Digital Twin ↔ Telemetry ↔ Automation/Control

Les plans 2D/3D et BIM ne doivent jamais créer une seconde base d'équipements
indépendante.

Un actif possède une identité universelle ; les représentations spatiales ne font que
le référencer.

---

## 19. Configuration as Versioned Data

Tout ce qui influence le fonctionnement doit être versionnable lorsque pertinent :

- schedules ;
- automation rules ;
- policies ;
- mappings ;
- Digital Twins ;
- connectors ;
- schemas ;
- configurations Edge ;
- alarm rules ;
- setpoint policies ;
- modèles ML ;
- dashboards critiques.

Prévoir :
version → author → timestamp → reason → diff → rollback.

---

## 20. Change Management / Safe Deployment

Une modification importante d'automatisation ou de contrôle ne doit pas passer
directement de l'édition à la production.

Prévoir progressivement :

Draft → Validate → Simulate/Test → Approve si nécessaire → Deploy → Observe → Rollback

Cela doit s'appliquer particulièrement aux changements ayant un impact physique.

---

## 21. Observability complète

La plateforme doit pouvoir s'observer elle-même.

Prévoir :

- metrics ;
- logs structurés ;
- traces distribuées ;
- health checks ;
- Edge health ;
- connector health ;
- queue lag ;
- ingestion latency ;
- command latency ;
- data freshness ;
- error budgets ;
- alerting ;
- audit.

Il faut pouvoir distinguer :

équipement en panne
de
capteur en panne
de
gateway hors ligne
de
connecteur défaillant
de
cloud indisponible.

---

## 22. Resilience / Failure Modes

Pour chaque composant important, documenter :

What happens if this fails?

Exemples :

- Internet coupé ;
- Edge redémarre ;
- cloud inaccessible ;
- DB temporairement indisponible ;
- MQTT déconnecté ;
- commande dupliquée ;
- événement reçu deux fois ;
- événement reçu en retard ;
- horloge Edge incorrecte ;
- capteur bloqué ;
- stockage Edge plein ;
- certificat expiré ;
- nouvelle version défectueuse.

Prévoir idempotency, retries contrôlés, backpressure, dead-letter handling et
mécanismes de récupération appropriés.

---

## 23. No/Low-Work Retrofit

Conserver comme principe produit majeur :

la plateforme ne doit pas supposer qu'une GTB existe.

Elle doit supporter :

1. bâtiments avec GTB existante ;
2. équipements communicants sans GTB ;
3. retrofit léger via Edge + équipements compatibles ;
4. monitoring sans contrôle ;
5. installations anciennes nécessitant l'intervention d'un intégrateur qualifié.

L'architecture doit permettre au client de commencer petit et d'étendre progressivement
son installation.

---

## 24. Domain Packs

Le noyau reste commun.

Les domaines doivent être ajoutables par packs :

- Building ;
- Industry ;
- Energy ;
- Water ;
- Residential ;
- Data Center ;
- Hospitality ;
- Retail ;
- Healthcare Facilities ;
- Public Infrastructure ;
- Agriculture technique ;
- autres futurs domaines.

Un Domain Pack ne doit pas dupliquer les moteurs fondamentaux.

---

## 25. Feature Benchmark permanent

Conserver également notre directive précédente.

Maintenir :

Feature | Notre statut | Concurrent(s) | Standard | Priorité | Décision | Justification

Le benchmark sert à apprendre du marché, pas à copier aveuglément.

---

## RÈGLE D'ARCHITECTURE

Avant d'implémenter ces ajouts, audite le code existant.

Pour chaque élément :

KEEP
REFACTOR
REPLACE
ADD
DEFER

DEFER est important : certaines capacités doivent être prévues architecturalement
maintenant mais développées plus tard.

Ne transforme pas cette liste en 25 microservices.

Commencer avec une architecture raisonnablement modulaire et faire évoluer les
frontières de services lorsque la charge, la sécurité, l'organisation ou l'isolation
technique le justifient.

---

## PRIORITÉ FONDATRICE

Les éléments qui doivent influencer l'architecture et le modèle de données dès
maintenant sont en priorité :

1. Universal Asset Identity
2. Asset/Spatial/Knowledge Graph
3. Digital Twin
4. Desired State / Actual State
5. Command Model + Arbitration
6. Policy/Safety Boundary
7. Telemetry/Event Model
8. Data Quality & Provenance
9. Asset Lifecycle
10. Device/Edge Identity
11. Configuration Versioning
12. Connector abstraction
13. Tenant isolation
14. Audit/Event history
15. Commissioning model

Les fonctionnalités avancées comme 3D complexe, simulation physique poussée, Fleet AI
avancée, marketplace mondiale ou optimisation énergétique très avancée peuvent être
DEFER, à condition que l'architecture actuelle ne les rende pas difficiles à ajouter
plus tard.

Avant toute modification majeure, produis d'abord l'impact architectural et le plan de
migration correspondant.
