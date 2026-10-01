# ADR 017 — Deux pistes de validation, Virtual Commissioning Lab, Replay Mode et moteur de commande V2 en mode simulation

## Statut

Acceptée (1er octobre 2026), directive explicite de Mohamed du même jour : « Le manque
actuel de matériel terrain ne doit PLUS bloquer la roadmap produit ». Change de
stratégie, ne revient sur aucune règle non négociable : aucune commande vers un
équipement réel, toujours interdite (règle 1) ; aucune activation d'écriture BACnet sans
la validation terrain de la lecture seule (ADR 015, ADR 016), toujours en vigueur.

## Décision en une phrase

Deux pistes désormais explicitement séparées :

- **PRODUCT DEVELOPMENT TRACK** — le développement V1/V2/V3/V4 continue normalement,
  sans jamais attendre un accès matériel ou un site client.
- **PHYSICAL VALIDATION TRACK** — la preuve sur une installation réelle reste une étape
  à part entière, menée dès qu'un environnement autorisé ou du matériel est disponible,
  mais ne conditionne plus l'avancement du premier track.

Seule une preuve **intrinsèquement physique** (un vrai réseau BACnet, un vrai relais, un
vrai technicien sur site) reste bloquée. Tout le reste — logique métier, pipeline de
bout en bout, interface, moteur de règles, moteur de commande en simulation — avance.

## Pourquoi maintenant

Le pilote Golden Asset (30 septembre 2026) a démontré que la chaîne logicielle complète
fonctionne sans trou structurel, mais sur un seul actif simulé, sans jamais toucher un
vrai capteur. Depuis, l'attente d'un adaptateur réseau pour la validation terrain BACnet
(ADR 016, section 5) a révélé le vrai risque : confondre « pas encore prouvé sur le
terrain » avec « ne peut pas avancer ». Ce sont deux choses différentes, et les traiter
comme une seule a ralenti le développement de fonctionnalités qui n'ont, elles, aucune
dépendance physique.

## 1. Statuts de validation

Vocabulaire déjà apparu de façon informelle dans `docs/spec/feature-benchmark-matrix.md`
(ligne « Connecteurs protocoles terrain » : `UNIT_TESTED`, `SIMULATOR_TESTED`,
`BLOCKED_EXTERNAL_VALIDATION`) — cette ADR le formalise et l'étend à huit statuts
indépendants, cumulables, qu'on attribue à chaque capacité du Feature Benchmark Matrix :

| Statut | Ce qu'il prouve | Preuve attendue |
|---|---|---|
| `IMPLEMENTED` | Le code existe, respecte les règles non négociables, compile/passe le lint | Revue de code |
| `UNIT_TESTED` | La logique pure est correcte | Tests unitaires, sans réseau ni dépendance externe |
| `SIMULATOR_TESTED` | Le comportement est correct contre un simulateur logiciel du protocole/équipement | BACnet Lab, serveur OPC UA de test, Virtual Protocol Adapter (section 2) — jamais de matériel réel |
| `REPLAY_TESTED` | Le comportement est correct face à des données réelles passées | Rejeu d'un export anonymisé d'une vraie installation (Replay Mode, section 3), sans connexion live |
| `INTEGRATION_TESTED` | La chaîne complète fonctionne à travers plusieurs modules | Authentification réelle, base réelle, écrans réellement alimentés (méthode du pilote Golden Asset), source de mesure simulée ou rejouée |
| `FAILURE_TESTED` | Les scénarios de panne sont détectés et gérés correctement | Panne injectée délibérément (dérive de capteur, perte de communication, vanne bloquée) dans le Virtual Commissioning Lab |
| `SHADOW_TESTED` | Le moteur de décision/autorisation/commande fonctionne de bout en bout sans jamais écrire vers un équipement réel | Decision → Authorization → Policy & Safety → Simulated Command → Audit → Simulated Verification (section 4), `SimulatedExecutor` uniquement |
| `FIELD_TESTED` | Validé sur au moins une installation réelle, avec du matériel réel | Visite terrain, adaptateur réseau réel, client pilote |

**Règle centrale** : `FIELD_TESTED` peut rester `BLOCKED_EXTERNAL` indéfiniment sans
bloquer aucun des sept autres statuts ni la roadmap. Une capacité peut légitimement être
`IMPLEMENTED` + `UNIT_TESTED` + `SIMULATOR_TESTED` + `INTEGRATION_TESTED` +
`FAILURE_TESTED` + `SHADOW_TESTED` et rester `FIELD_TESTED: BLOCKED_EXTERNAL` — c'est
désormais l'état attendu pour la plupart des capacités avant une installation pilote
réelle, pas un défaut à excuser.

**Retrofit** : la ligne « Connecteurs protocoles terrain » de la matrice remplace
`BLOCKED_EXTERNAL_VALIDATION` par `FIELD_TESTED: BLOCKED_EXTERNAL` (même sens, vocabulaire
désormais standard — voir modification apportée par cette ADR).

## 2. Virtual Commissioning Lab — l'essentiel existe déjà

Architecture cible demandée :

```
Virtual Asset → Virtual Protocol Adapter → Edge → Telemetry → Universal Asset Model
  → Event Engine → State Engine → FDD → Alert → Timeline → Maintenance → Energy
  → Command Center
```

En comparant à l'existant, **onze des treize maillons sont déjà construits et validés**
par les jalons M1 à M5 — le Virtual Commissioning Lab n'est pas une plateforme parallèle,
c'est le pipeline de production existant nourri par une source simulée :

| Maillon | État | Module existant |
|---|---|---|
| Virtual Asset | À construire (section ci-dessous) | S'appuie sur `app/assets.py`, `app/spatial.py` (registre déjà générique) |
| Virtual Protocol Adapter | **Nouveau** | Aucun équivalent — à écrire |
| Edge | ✅ Déjà protocole-agnostique | `app/connectors/edge_client.py`, `app/devices.py`, `POST /edge/measurements` |
| Telemetry | ✅ Fait | `app/telemetry.py`, `app/telemetry_overview.py` |
| Universal Asset Model | ✅ Fait (ADR 001) | `app/assets.py` (ProductModel/PhysicalUnit/FunctionalLocation) |
| Event Engine | ✅ Fait | `app/events.py` |
| State Engine | ✅ Fait | `app/equipment_status.py`, `app/monitoring.py` |
| FDD | ✅ Fait (règles de seuil, d'écart, de corrélation) | `app/rules.py` |
| Alert | ✅ Fait (4 axes) | `app/signals.py`, `app/findings.py` |
| Timeline | ✅ Fait | `app/timeline.py` |
| Maintenance | ✅ Fait | `app/maintenance.py`, `app/closures.py` |
| Energy | ✅ Fait (M5) | `app/energy/` |
| Command Center | ✅ Fait | `apps/web/src/app/page.tsx` et les écrans dédiés |

**Décision : zéro duplication.** Un équipement virtuel passe par le même registre, les
mêmes règles, le même moteur d'événements, la même interface qu'un équipement réel —
conforme au monolithe modulaire (CLAUDE.md section 6). Seuls deux éléments manquent
réellement :

### 2.1 Virtual Asset (générateur)

Un script/CLI (`scripts/virtual_commissioning.py`, à écrire) qui peuple le registre
existant via les mêmes fonctions que la saisie manuelle ou l'import IFC (`app/assets.py`,
`app/spatial.py` — un seul chemin de création, jamais un second) : plusieurs sites,
bâtiments, espaces et équipements synthétiques. Réutilise directement les **six profils
d'équipement déjà construits pour le BACnet Lab** (CTA, groupe froid, groupe
électrogène, VRV/DRV, sous-station thermique, comptage — `tests/bacnet_lab.py`) plutôt
que d'inventer un second catalogue d'équipements : ces profils existent déjà, sont
réalistes, et sont déjà couverts par des tests.

### 2.2 Virtual Protocol Adapter (simulateur de télémétrie)

Un nouveau module (`app/connectors/virtual_telemetry.py`), analogue aux connecteurs
Modbus/BACnet/OPC UA existants mais sans protocole réseau réel : génère des valeurs
dynamiques réalistes (cycle jour/nuit, dérive lente, bruit de mesure borné) pour chaque
point d'un équipement virtuel, et des **scénarios de panne déclenchables** :

- dérive lente d'un capteur (vers `DATA_QUALITY_STALE` ou une valeur hors plage),
- perte de communication (plus aucune mesure → `DATA_BECAME_STALE`, déjà câblé),
- vanne bloquée en position,
- chauffage et refroidissement actifs simultanément (déclenche directement la règle
  `simultaneous_heating_cooling` déjà écrite, `app/rules.py`).

Tourne comme un démon analogue à `scripts/modbus_daemon.py` : s'authentifie comme un
appareil Edge provisionné normalement (`app/devices.py`), envoie via
`POST /edge/measurements` — **aucun nouvel endpoint d'ingestion**. Un équipement virtuel
est donc, du point de vue du reste de la plateforme, indiscernable d'un équipement réel
tant qu'on ne regarde pas la source des mesures.

## 3. Replay Mode

Objectif : injecter ultérieurement des exports réels anonymisés de GTB (CSV, tendances,
alarmes, historiques) sans créer un second chemin d'ingestion. Un importeur
(`scripts/replay_import.py`, à écrire au moment de l'implémentation) traduit un export
externe vers le même contrat que `POST /edge/measurements` (ou un appel direct à
`app/telemetry.py` pour un import en lot avec horodatage passé — `measured_at` est déjà
un champ de la requête, pas assigné par le serveur, donc compatible avec un historique).

**Anonymisation : responsabilité de la personne qui fournit l'export, vérifiée par une
garde minimale à l'import** (refus si une colonne ressemble à un nom, un identifiant
personnel ou une adresse — contrôle de base, pas une garantie, conforme à la règle non
négociable 9). Alarmes et événements historiques de l'export se traduisent vers
`app/events.py`/`app/signals.py` quand un équivalent direct existe ; sinon, ils restent
une pièce jointe de la chronologie (`app/timeline.py`, déjà conçu pour fusionner des
sources hétérogènes) plutôt que d'inventer un nouveau type d'événement pour un cas unique.

## 4. Moteur de commande V2 — Shadow Mode (pas un second moteur)

Rappel ADR 016, inchangé : **jamais un second moteur de commande.** Le moteur V2 reste
`app/commands.py` — même cycle `pending → sent → acknowledged → verified`, mêmes rôles,
même audit. Ce qui change :

### 4.1 Executor, une interface au lieu d'un cas particulier

Aujourd'hui, l'unique écriture du dépôt (`app/connectors/simulated_actuator.py`) est
sélectionnée par un test de chaîne sur `device_type == "simulated_relay"`. La V2
formalise une interface (`CommandExecutor`, `app/connectors/executors.py` à écrire) dont
`SimulatedExecutor` devient la première implémentation nommée — un **REFACTOR de seam**,
jamais une nouvelle logique métier : `app/commands.py` ne change pas, seul le point de
sélection de l'exécuteur devient explicite et remplaçable. Le jour où le terrain BACnet
ou Modbus réel est autorisé (ADR 016, conditions inchangées), un `BacnetExecutor` ou
`ModbusExecutor` s'ajoute derrière la même interface, sans toucher au moteur métier.

### 4.2 Chaîne Shadow Mode

```
Decision → Authorization → Policy & Safety → Simulated Command → Audit → Simulated Verification
```

Chaque maillon tourne réellement (y compris autorisation RBAC et politique de sécurité) ;
seul l'exécuteur est toujours `SimulatedExecutor`. **Aucune commande terrain réelle** —
cette ADR ne lève ni la règle non négociable 1, ni les conditions d'activation de l'ADR
016 (validation terrain de la lecture seule + décision explicite séparée nommant
l'exécuteur réel et le `device_type`).

## 5. IA prédictive et données synthétiques

Les données synthétiques produites par le Virtual Commissioning Lab peuvent valider
l'architecture et le pipeline (ingestion, FDD, alertes) — elles ne doivent **jamais**
servir à annoncer une performance réelle d'un futur modèle prédictif. Conforme au
`product-language-directive` (ADR 013) : le jour où une prédiction entraînée sur données
synthétiques apparaît quelque part, elle porte un marqueur explicite (catalogue i18n,
jamais une phrase en dur) distinguant « validé en simulation » de « validé sur données
réelles ». La ligne « Maintenance prédictive / ML » de la matrice reste `BLOCKED` pour
toute annonce de performance réelle — ceci ne change pas (hors périmètre 12 mois,
CLAUDE.md section 4), seule la possibilité de valider l'architecture en simulation
s'ajoute.

## 6. Ce que cette ADR ne fait pas

- Ne lève pas la règle non négociable 1.
- Ne crée aucun `device_type` simulé réel pour BACnet (reste couvert par ADR 016,
  inchangée).
- Ne code aucune migration : tout ajout de schéma (ex. un éventuel tenant/provider dédié
  aux actifs virtuels, pour ne jamais mélanger données virtuelles et réelles) sera
  proposé au moment de l'implémentation, jamais une colonne destructive.
- Ne fixe pas de calendrier détaillé au-delà de l'ordre proposé en section 7.

## 7. Plan de migration proposé (aucun incrément codé par cette ADR)

1. Virtual Asset (générateur, réutilise les profils BACnet Lab) + Virtual Protocol
   Adapter (télémétrie dynamique), alimentant le pipeline existant via un appareil Edge
   virtuel provisionné normalement.
2. Scénarios de panne déclenchables → `FAILURE_TESTED` sur les règles FDD existantes.
3. Replay Mode (import CSV anonymisé → même contrat d'ingestion).
4. `CommandExecutor` (interface) + `SimulatedExecutor` nommé explicitement ; Shadow Mode
   exercé de bout en bout sur un actif virtuel.
5. Mise à jour continue de `docs/spec/feature-benchmark-matrix.md` à chaque incrément.

Isolation des données virtuelles : à trancher au moment de l'implémentation (probable :
un tenant de démonstration dédié, sur le modèle de `scripts/seed_demo_equipment.py`
existant, jamais mélangé à un tenant client réel).

## Conséquences

- `docs/spec/feature-benchmark-matrix.md` : nouvelle légende des statuts de validation
  (section « Processus d'évaluation ») ; lignes « Connecteurs protocoles terrain »,
  « Commande distante sécurisée » et « Maintenance prédictive / ML » mises à jour pour
  citer cette ADR ; nouvelle sous-section « Validation virtuelle (Virtual Commissioning
  Lab, Replay Mode) ».
- Prochaine étape réelle (non codée par cette ADR) : incrément 1 de la section 7.
