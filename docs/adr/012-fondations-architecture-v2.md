# ADR 012 — Fondations de l'architecture V2 : impact et plan de migration

## Statut

Acceptée (23 septembre 2026), avec l'accord de Mohamed. Complète l'ADR 001 (modèle sémantique), l'ADR 004 (vision
cible) et l'ADR 011 (modèle spatial) sans les remplacer.

## Contexte

Le 23 septembre 2026, Mohamed a ajouté au cahier des charges un **Architecture Addendum
V2** (texte complet, mot pour mot :
[`docs/spec/architecture-addendum-v2.md`](../spec/architecture-addendum-v2.md)) : 25
capacités à prévoir dans les fondations (mise en service continue, FDD, qualité des
données, état souhaité / état réel, arbitrage des commandes, sûreté, identité des
appareils, flotte Edge, certification des connecteurs, graphe de connaissances, cycle
de vie, mémoire opérationnelle, passeport numérique, scénarios, économie des actifs,
flexibilité énergétique, interopérabilité sémantique, configuration versionnée, gestion
des changements, observabilité, résilience, retrofit léger, Domain Packs, benchmark).

Consigne explicite : auditer d'abord, classer chaque élément KEEP / REFACTOR / REPLACE /
ADD / **DEFER** (prévu dans l'architecture maintenant, développé plus tard), ne pas
créer 25 microservices, et produire l'impact architectural et le plan de migration
avant toute modification majeure. C'est l'objet de ce document.

## En une page

1. **Aucun REPLACE.** Rien de l'existant n'est à jeter. Les fondations posées (RLS,
   audit chaîné, identité à trois niveaux, historiques jamais écrasés, hors ligne
   mobile idempotent) sont exactement celles que l'addendum demande.
2. **Deux changements de fond sur le modèle de données, à faire maintenant tant qu'il
   n'y a que des données de test** :
   - un **registre d'identité universel** (`graph_nodes`) et une table de **relations**
     typées (`relations`) : c'est la base du graphe de connaissances, du passeport QR,
     de la mémoire opérationnelle et du jumeau numérique ;
   - la **refonte de la télémétrie autour de la notion de point** (capteur, consigne,
     état) : aujourd'hui une mesure n'est qu'un nombre avec un nom libre, ce qui bloque
     l'état réel/souhaité, la qualité des données et l'envoi différé depuis l'Edge.
3. **Tout ce qui touche à la commande reste DEFER** : le modèle d'intention de commande,
   l'arbitrage et la chaîne de sûreté sont conçus ici, mais aucune table ni aucun code
   n'est créé tant que Mohamed n'a pas levé explicitement la règle non négociable 1.
4. **Un monolithe modulaire**, pas des microservices : une API, un processus de tâches
   de fond (même code), et plus tard l'agent Edge sur site.
5. **Plan en étapes courtes** (F1 à F6), chacune livrable et testée seule. La prochaine
   étape proposée est F1 (registre d'identité et relations).

## 1. Audit de l'existant (état réel du code au 23 septembre 2026)

| Brique existante | Ce qu'elle fait réellement | Verdict |
|---|---|---|
| RLS forcée sur chaque table métier + test d'isolation par table | Un client ne voit jamais les données d'un autre, même par identifiant | **KEEP** — renforcement proposé (clés étrangères incluant le tenant, voir risque 6) |
| Journal d'audit chaîné par hachage, un chaînage par tenant, verrou consultatif | Trace infalsifiable des actions sensibles | **KEEP** — réservé aux actions sensibles (voir risque 9) ; ancrage externe prévu par l'ADR 008 du cahier, à faire |
| Keycloak (OIDC) + rôles globaux par tenant | Identité des personnes | **KEEP** — identité des machines séparée (voir point 10) |
| ProductModel / PhysicalUnit / FunctionalLocation + affectations bitemporelles | Remplacer un équipement crée un nouvel exemplaire, la position garde son historique | **KEEP** — c'est déjà la règle « ne pas réutiliser l'identité de l'ancien équipement » |
| Historique des statuts (ordres de travail, alarmes), jamais modifié | Rien n'est écrasé | **KEEP** — même modèle réutilisé pour le cycle de vie et les constats |
| GMAO : ordres de travail, interventions, rondes, alarmes manuelles, photos | Maintenance terrain | **KEEP** |
| Application mobile hors ligne (file d'envoi SQLite, synchronisation idempotente testée) | Travail sans réseau, sans doublon | **KEEP** — même principe d'idempotence à appliquer à la télémétrie |
| Console web (registre, ordres de travail), OAuth PKCE + rafraîchissement de jeton | Pilotage par le responsable d'exploitation | **KEEP** |
| `measurements` (M2) : nom de grandeur libre, valeur décimale uniquement, clé = identifiant seul, source « simulator » | Premier maillon du squelette de bout en bout | **REFACTOR** (étape F3, voir risque 1) |
| Observabilité : `/health`, `/health/db` | Vérifie que l'API et la base répondent | **KEEP** + ADD (logs structurés, puis métriques et traces) |
| ADR 001 « adopter Brick Schema » | Vocabulaire des équipements et points | **REFACTOR du texte** : vocabulaire interne aligné sur Brick, avec correspondances versionnées vers plusieurs standards (point 17) |
| Écarts au périmètre M1 du cahier (section 36) : QR, clôture structurée (défaut, cause, action, pièce), fluides frigorigènes, rapport PDF | Non réalisés | **ADD** (étape F5) — signalé par honnêteté : la clôture structurée est la source des étiquettes du futur FDD/ML |

## 2. Les 15 priorités fondatrices : décision et forme dans le modèle de données

### 2.1 Universal Asset Identity — KEEP + ADD `graph_nodes` (F1)

Chaque chose que l'on peut relier, placer sur un plan, scanner ou diagnostiquer (site,
espace, position fonctionnelle, exemplaire physique, point, puis passerelle Edge,
prestataire…) reçoit une ligne dans un registre commun `graph_nodes (tenant_id, id,
node_type)`, avec le **même UUID** que dans sa propre table. Un déclencheur en base
crée cette ligne automatiquement à chaque insertion : aucun chemin d'écriture (API,
import, test) ne peut l'oublier.

Pourquoi : aujourd'hui, pour relier « une CTA » à « un tableau électrique » ou afficher
la mémoire d'un actif, il faudrait des références « type + identifiant » sans contrôle
par la base. Avec un registre commun, les relations ont de vraies clés étrangères, et
ces clés incluent le `tenant_id` : **un lien entre deux clients différents devient
impossible au niveau de la base**, pas seulement dans le code.

Règle conservée : un nouvel équipement physique a toujours une nouvelle identité ; la
position fonctionnelle garde la sienne (c'est voulu : « la PAC du toit » reste la même
place, occupée successivement par deux machines).

### 2.2 Asset / Spatial / Knowledge Graph — KEEP les arbres + ADD `relations` (F1)

- Les **arbres stricts** restent des colonnes (un seul parent, contrôles de cycle) :
  `spaces.parent_id` (ADR 011), `functional_locations.parent_id`,
  `functional_locations.space_id`. Ils sont exposés comme relations `contains`,
  `hasPart`, `locatedIn`, **sans être recopiés** dans la table des relations (une seule
  source de vérité).
- Les **relations transverses** (`feeds`, `poweredBy`, `measuredBy`, `controlledBy`,
  `connectedTo`, `servedBy`, `maintainedBy`, `dependsOn`, `protectedBy`) vont dans
  `relations (sujet, prédicat, objet)` avec : période de validité et date de saisie
  (bitemporel, ADR 001), origine (`manual`, `import`, `discovery`, `inferred`),
  confiance, statut (`proposed`, `validated`, `rejected`). Un seul sens est stocké ;
  l'inverse (`fedBy`, `serves`…) est déduit, pour ne jamais avoir deux versions
  contradictoires.
- Les prédicats forment un **vocabulaire interne versionné** (fichier dans le dépôt),
  avec pour chacun sa correspondance Brick et ASHRAE 223P : on s'aligne sur les
  standards sans en dépendre.
- Les zones transverses de l'ADR 011 (zone CVC couvrant plusieurs pièces) deviennent
  simplement des relations `servedBy` : pas de table spéciale.

Usage visé : analyse d'impact (« si ce tableau électrique tombe, quelles pièces perdent
leur ventilation ? ») et suppression des alarmes en cascade (point 21).

### 2.3 Digital Twin — une vue composée, pas une base séparée

Le jumeau numérique d'un actif n'est **pas une nouvelle base** : c'est l'assemblage de
ce qui existe autour d'un même identifiant — identité (`graph_nodes`), modèle catalogue,
propriétés, emplacement et relations, état réel (dernières mesures avec leur qualité),
état souhaité, historique, cycle de vie, constats et maintenance. Même principe que les
plans (ADR 011) : on référence, on ne copie jamais.

Propriétés techniques (puissance nominale, fluide frigorigène, charge en kg…) : table
`node_properties` bitemporelle, avec unité et origine, **ajoutée avec la première
fonctionnalité qui en a besoin** (fluides frigorigènes, étape F5).

### 2.4 Desired State / Actual State — ADD dès F3/F4, utile même en lecture seule

- **État réel** = dernière valeur d'un point, avec horodatage et qualité (jamais une
  valeur sans sa fraîcheur).
- **État souhaité** = table `desired_states` (point, valeur attendue, période,
  origine). En lecture seule (règle 1), l'origine est une **attente déclarée** : « éclairage
  éteint de 20 h à 7 h », « consigne de départ 45 °C selon contrat ». Plus tard
  s'ajouteront les origines `schedule`, `policy`, `command_intent`.
- **Divergence** = un constat (voir 2.15) : « souhaité OFF, réel ON depuis 3 h ». C'est
  déjà une vraie valeur pour le client sans aucune commande : détection de gaspillage
  et de dérive, ce que vendent les « GTB légères ».
- Le cycle complet Command → Acknowledgement → Observation → Verification →
  Reconciliation est **DEFER** (règle 1) ; le modèle ci-dessus en est la base, rien ne
  sera à refaire.

### 2.5 Command Model + Arbitration — DEFER (conçu ici, rien de créé)

Forme retenue pour le jour où la règle 1 sera levée par Mohamed (et après l'ADR 007 du
cahier, « politique de commande », prévue avant M4) :

- `command_intents` : cible (point), valeur demandée, source (`schedule`, `user`,
  `energy_engine`, `automation`, `technician_override`, `safety`), acteur, niveau de
  priorité, justification, horodatage, durée et expiration, politique appliquée (avec
  sa version), valeur précédente, identifiant de causalité, statut (`proposed →
  authorized | rejected → arbitrated → dispatched → acknowledged → observed → verified
  | failed | expired | relinquished`), résultat.
- **Arbitrage déterministe inspiré du tableau de priorités BACnet** (16 niveaux, norme
  ASHRAE 135) : l'intention active la plus prioritaire gagne ; à expiration, elle est
  retirée et le niveau suivant (ou le programme normal) reprend automatiquement. Les
  sécurités locales gardent les niveaux les plus hauts et ne sont jamais écrasables.
- **Anti-boucle** : chaque intention porte la chaîne des intentions qui l'ont causée ;
  profondeur maximale et limite de fréquence par point.
- **Où s'exécute l'arbitrage** : sur l'Edge, au plus près de l'équipement, pour
  continuer à fonctionner sans Internet ; le cloud en garde la copie et l'historique.
  Quand l'équipement a déjà son propre tableau de priorités (BACnet), la plateforme
  n'utilise que le niveau qui lui est attribué, jamais ceux des sécurités.

### 2.6 Policy / Safety Boundary — KEEP la frontière, ADD une barrière en base (F3)

- Quatre couches séparées : **Recommendation** (IA, FDD, énergie : produisent des
  recommandations, jamais d'action), **Automation** et **Control** (DEFER), **Safety**
  (règles déterministes et protections locales, toujours prioritaires).
- Chaîne obligatoire le jour venu : Identity → Authorization → Policy → Safety
  Constraints → Command Arbitration → Edge → Controller → Verification.
- **Aujourd'hui**, la frontière est la règle 1. On la renforce dès F3 par une contrainte
  en base : un point porte `is_writable`, et une contrainte `CHECK (is_writable = false)`
  empêche physiquement qu'un point soit déclaré inscriptible. Lever la règle 1 exigera
  une migration visible et relue, jamais une modification discrète.
- Un LLM peut rédiger une explication ; il ne décide jamais seul d'un diagnostic ni
  d'une action.

### 2.7 Telemetry / Event Model — REFACTOR (F3, avant tout connecteur réel)

- **Point** (`points`, nœud du graphe) : rattaché à une position fonctionnelle ou à un
  espace ; classe (vocabulaire interne aligné Brick) ; nature (`sensor`, `setpoint`,
  `command`, `status`, `alarm`, `meter`) ; type de valeur (`number`, `boolean`,
  `multistate` avec la table des états) ; unité (codes normalisés, alignés QUDT/UCUM) ;
  intervalle attendu ; plage physiquement possible ; statut et confiance du mapping ;
  `is_writable` (toujours faux, voir 2.6).
- **Mesure** : point, `measured_at` (quand la valeur a été relevée), `received_at`
  (quand la plateforme l'a reçue), valeur numérique (un booléen ou un état multiple est
  codé en nombre, défini par le point, comme BACnet), drapeaux de qualité, origine.
  Clé primaire (point, `measured_at`) : un même relevé envoyé deux fois (reprise après
  coupure Edge) est ignoré au lieu d'être dupliqué, et cette clé est compatible avec
  TimescaleDB (M3).
- **Événements** : les actions sensibles restent dans le journal d'audit ; les
  événements à fort volume (mesures, battements de cœur Edge, constats) ont leurs
  propres tables, jamais le journal d'audit.

### 2.8 Data Quality & Provenance — ADD (F3 à l'ingestion, F4 score)

- **Origine de chaque valeur**, partout dans la plateforme : `measured`, `manual`,
  `derived`, `estimated`, `simulated`. Une valeur simulée ou estimée n'est jamais
  présentée comme mesurée (exigence du point 14).
- **Drapeaux calculés à la réception** : hors plage physique, unité incohérente,
  horloge suspecte (relevé daté dans le futur ou très en retard), valeur figée,
  doublon. Correspondance prévue avec les codes de qualité OPC UA (Good / Uncertain /
  Bad) et les indicateurs d'état BACnet.
- **Score de confiance par point** (F4) : fraîcheur, complétude, valeurs figées,
  dérive, calibration, confiance du mapping ; calculé en tâche de fond, historisé, avec
  le détail de son calcul. Son algorithme est lui-même une configuration versionnée.
- **Règle d'usage** : les règles FDD, et plus tard l'automatisation, ignorent
  explicitement un point dont le score est sous un seuil, et le disent (« constat non
  évalué : capteur non fiable »).

### 2.9 Asset Lifecycle — KEEP + ADD états et événements (F5)

`physical_units.lifecycle_state` + historique `physical_unit_lifecycle_events` (même
modèle que les statuts d'ordres de travail) : planifié, commandé, en stock, installé,
mis en service, en exploitation, hors service, déposé, déclassé, éliminé. « Entretenu »
n'est pas un état mais une suite d'interventions. L'installation et la dépose restent
cohérentes avec les affectations bitemporelles existantes.

### 2.10 Device / Edge Identity — DEFER (M3), décisions prises maintenant

- Identité des **machines séparée de celle des personnes** : une passerelle ou un
  connecteur n'utilisera jamais un compte Keycloak humain. (Le simulateur M2 utilise un
  jeton de technicien : acceptable pour un simulateur, interdit pour un vrai appareil.)
- `edge_devices` (nœud du graphe) : tenant, site, numéro de série, statut
  (`provisioning`, `active`, `suspended`, `revoked`, `decommissioned`), certificat
  (empreinte, expiration), firmware, version de configuration, dernier contact, état de
  sécurité.
- Certificats X.509 par appareil, clé générée sur l'appareil (puce TPM quand elle
  existe), enrôlement automatisé (EST ou ACME), certificats de courte durée renouvelés
  automatiquement, révocation immédiate possible, authentification mutuelle (mTLS). Le
  certificat lie l'appareil à un tenant et un site : le serveur refuse qu'il publie pour
  un autre site. Autorité de certification derrière un adaptateur (règle 8). Référence :
  IEC 62443.

### 2.11 Configuration Versioning — ADD générique (F4)

Une seule table `config_versions` pour tout ce qui influence le fonctionnement (règles
d'alarme et FDD, attentes et plannings, mappings, configurations Edge et connecteurs,
politiques, algorithme du score de confiance, puis modèles ML et tableaux de bord
critiques) : type, sujet, numéro de version, contenu, empreinte, version du schéma,
auteur, date, **raison obligatoire**, version parente, statut (`draft`, `validated`,
`approved`, `active`, `superseded`, `rolled_back`). Le diff se calcule entre deux
versions ; un retour arrière crée une **nouvelle** version avec l'ancien contenu (rien
n'est écrasé). Une seule version active par sujet, garantie par la base.

Pourquoi générique : 12 types de configuration, un seul mécanisme, testé une fois. La
première règle de seuil (M2) sera la première configuration versionnée.

**Mise en œuvre F4 (23/09/2026)** — statuts retenus pour commencer : `draft`,
`active`, `superseded`, `retired` (transitions contrôlées par la base). La validation
du contenu se fait à chaque création et à nouveau à l'activation. Les étapes
`validated` / `approved` (approbation par une seconde personne) et la simulation
préalable restent DEFER : elles deviendront indispensables avec la première
configuration à impact physique, pas avant.

### 2.12 Connector abstraction — DEFER (M3), contrat fixé maintenant

Contrat du SDK : découvrir, lire, s'abonner, état de santé, capacités déclarées ;
écriture présente dans le contrat mais **désactivée** (règle 1). Un connecteur ne parle
jamais directement à la base : il émet des messages normalisés (point, valeur, qualité,
horodatage, origine). Manifeste versionné (protocole, version, capacités, niveau de
certification). Certification Experimental → Verified → Certified par une suite de
tests de conformité avec injection de pannes (inspirée des laboratoires de test BACnet,
BTL). L'écriture exigera `Certified` + accord explicite du tenant + politique : jamais
automatique.

### 2.13 Tenant isolation — KEEP + REFACTOR de renforcement

Les nouvelles tables (dès F1) utilisent des clés étrangères composées `(tenant_id, id)`.
Les tables existantes seront renforcées de la même façon dans une étape dédiée (risque
6). Les appareils Edge seront liés à leur tenant par leur certificat (2.10).

### 2.14 Audit / Event history — KEEP + ADD ancrage

Le journal d'audit reste la mémoire infalsifiable des actions sensibles. À ajouter
(prévu par l'ADR 008 du cahier) : ancrage périodique de la dernière empreinte hors de la
base (horodatage externe ou stockage à écriture unique), pour prouver que la chaîne
entière n'a pas été réécrite.

**Mémoire opérationnelle (point 12)** : pas de nouvelle base. Une chronologie par nœud
qui assemble journal d'audit, interventions, alarmes, ordres de travail, constats,
versions de configuration, événements de cycle de vie et mesures avant/après. Elle
devient simple grâce au registre d'identité commun (2.1). Notes et documents rattachés
à un nœud : ajout ultérieur.

### 2.15 Commissioning model — ADD le modèle (F3-F4), le moteur plus tard

Un seul objet **constat** (`findings`) pour les sorties analytiques, avec une nature
explicite qui respecte la séparation demandée : `data_quality`, `commissioning`,
`anomaly`, `fault`, `prediction`. Chaque constat porte : le nœud concerné, la règle ou
le modèle qui l'a produit (avec sa version de configuration), la méthode
(`deterministic_rule`, `engineering_rule`, `statistical`, `physical_model`,
`peer_comparison`, `ml`), la sévérité, la confiance, les preuves (mesures, fenêtre de
temps) et un historique de statut. Le **diagnostic** est séparé
(`diagnoses` : hypothèses de cause avec probabilité) et la **recommandation** aussi
(`recommendations` : action proposée, gain estimé marqué `estimated`, acceptée ou
rejetée par un humain, qui peut alors créer un ordre de travail).

**Mise en œuvre F4 (23/09/2026)** — `findings` et son historique de statut sont
construits. Les tables `diagnoses` et `recommendations` sont **DEFER** : aucun moteur
ne produit encore d'hypothèses de cause, et créer des tables sans producteur irait
contre la règle des trois. En attendant, un constat porte un champ
`recommended_action` (texte) et une confiance ; les tables viendront avec le premier
moteur d'ingénierie (règles AFDD de la Guideline 36) sans modifier `findings`.

Chaîne : constat → (alarme existante si besoin d'alerter) → ordre de travail existant.
Premières règles d'ingénierie visées pour le wedge : les règles de détection de défauts
des CTA de la Guideline ASHRAE 36, issues des règles APAR du NIST.

Mise en service : les statuts de mapping des points, les attentes déclarées (2.4) et les
constats `commissioning` forment le cycle Discover → Identify → Map → Commission →
Validate → Operate → Recommission. **Un équipement connecté n'est jamais considéré comme
bien configuré par défaut** : ses points commencent à l'état `proposed`.

## 3. Les 25 points de l'addendum

| # | Capacité | Existant | Décision | Quand |
|---|---|---|---|---|
| 1 | Commissioning continu | Rien | ADD le modèle (statuts de mapping, attentes, constats) ; DEFER le moteur | F3-F4, moteur M3+ |
| 2 | FDD | Alarmes manuelles seulement | ADD règles déterministes ; DEFER statistiques, modèles physiques, ML | F4, puis M3+ |
| 3 | Qualité des données / confiance | Rien | ADD drapeaux et origine à la réception, puis score | F3, F4 |
| 4 | État souhaité / réel | Rien | ADD (attentes déclarées) ; DEFER le cycle de commande | F3-F4 ; commande après levée de la règle 1 |
| 5 | Arbitrage des commandes | Rien | DEFER (conçu au 2.5) | Après levée de la règle 1 |
| 6 | Sûreté et politiques | Règle 1 | KEEP + ADD contrainte `is_writable = false` ; DEFER le moteur | F3 ; moteur plus tard |
| 7 | Identité des appareils / PKI | Rien | DEFER (conçu au 2.10) | M3 |
| 8 | Gestion de flotte Edge | Rien | DEFER ; s'appuiera sur `config_versions`, l'ingestion idempotente et l'identité des appareils | M4 |
| 9 | Certification des connecteurs | Rien | DEFER (conçu au 2.12) | M3 |
| 10 | Graphe de connaissances | Arbres FL + affectations | KEEP + ADD `graph_nodes` et `relations` | F1 |
| 11 | Cycle de vie | Exemplaires + affectations bitemporelles | KEEP + ADD états et événements | F5 |
| 12 | Mémoire opérationnelle | Audit + historiques + interventions | KEEP + ADD chronologie par nœud ; DEFER notes et documents | F5-F6 |
| 13 | Passeport numérique / QR | Rien (écart M1) | ADD étiquettes QR/NFC révocables + écran mobile | F5 |
| 14 | Scénarios « what-if » | Rien | DEFER ; règle d'origine `simulated`/`estimated` dès F3 ; résultats jamais dans la table des mesures | Après M5 |
| 15 | Économie des actifs | Rien | DEFER ; prérequis : clôture structurée (F5) | Après M5 |
| 16 | Flexibilité énergétique / DER | Rien | DEFER ; représentable avec classes + points + relations `feeds`/`poweredBy` | M5+ |
| 17 | Interopérabilité sémantique | ADR 001 (Brick) | REFACTOR ADR 001 ; ADD correspondances versionnées au fil des besoins | F1 (prédicats), F3 (classes de points) |
| 18 | Spatial / BIM | ADR 011 (proposée) | KEEP, complétée : les espaces sont des nœuds, zones transverses = relations | F2 |
| 19 | Configuration versionnée | Rien | ADD générique | F4 |
| 20 | Gestion des changements | Rien | ADD statuts minimaux ; DEFER simulation/tests préalables et déploiement progressif | F4, puis M4 |
| 21 | Observabilité | `/health`, `/health/db` | KEEP + ADD logs structurés ; DEFER métriques/traces OpenTelemetry et chaîne de causes | F6, M3-M4 |
| 22 | Résilience / modes de défaillance | Outbox mobile idempotente, verrou d'audit | KEEP + ADD document des modes de défaillance, ingestion idempotente ; DEFER file des messages rejetés | F3, F6, M3 |
| 23 | Retrofit léger, GTB non supposée | Registre utilisable sans aucune connexion | KEEP (principe déjà respecté) ; DEFER profils d'intégration par site | M3 |
| 24 | Domain Packs | Catégories en texte libre | REFACTOR progressif : vocabulaires en fichiers versionnés ; DEFER le mécanisme de pack | F1, F3 ; pack plus tard |
| 25 | Benchmark permanent | Matrice existante | KEEP + ajout de la colonne Standard (fait avec cette ADR) | Maintenant |

## 4. Architecture d'exécution : monolithe modulaire

- **Cloud** : une API (FastAPI) organisée en modules internes aux frontières claires
  (identité et graphe, spatial, actifs et cycle de vie, télémétrie et qualité,
  maintenance, analytique [constats, FDD, mise en service], configuration, appareils,
  interopérabilité, audit) ; **un processus de tâches de fond** issu du même code
  (score de confiance, règles FDD, lecture IFC, rapports), avec une file de tâches dans
  PostgreSQL au départ (Kafka reste hors périmètre, cahier section 36).
- **Site** : l'agent Edge, forcément séparé (connecteurs, mémoire tampon en cas de
  coupure, et plus tard arbitrage et sûretés locales).
- **Critères pour sortir un module en service séparé** : charge, isolation de sécurité,
  organisation de l'équipe. Candidat identifié à terme : le plan de commande, qui
  méritera un service durci et isolé le jour où les commandes existeront.
- Le module « contrôle » **n'existe pas** tant que la règle 1 s'applique : pas de
  dossier vide « pour plus tard ».
- La réorganisation du dossier `app/` en paquets par module se fera progressivement, à
  l'occasion des étapes F1 à F6, sans « grand soir ».

## 5. Risques de blocage signalés avant de coder

Classés du plus urgent au moins urgent.

1. **Élevé — modèle de télémétrie actuel.** Nom de grandeur libre, valeur décimale
   seule, clé primaire sur l'identifiant seul, aucune protection contre les doublons.
   Cela bloque : l'état réel ON/OFF, la qualité par capteur, l'envoi différé depuis
   l'Edge (chaque reprise créerait des doublons) et le passage à TimescaleDB (qui exige
   que la date fasse partie de la clé). Aujourd'hui la correction est peu coûteuse
   (données de test uniquement) ; après un premier client, elle demanderait une
   migration lourde. → **F3**.
2. **Élevé — pas de registre d'identité commun.** Sans lui, relations, passeport QR et
   mémoire opérationnelle devraient utiliser des références sans contrôle de la base.
   → **F1**.
3. **Moyen — ingestion avec un jeton humain.** Acceptable pour le simulateur, interdit
   pour un vrai appareil. → identité machine en **M3** (2.10).
4. **Moyen — sens du lien Edge ↔ cloud.** Il faudra le concevoir dès M3 comme un canal
   bidirectionnel sécurisé (par exemple MQTT avec mTLS), même si les commandes restent
   désactivées : configuration à distance, mises à jour et, un jour, commandes en
   dépendent. Un simple envoi HTTP dans un seul sens obligerait à tout refaire.
5. **Moyen — données simulées mêlées aux données réelles.** Le simulateur M2 écrit dans
   la même table. → origine `simulated` obligatoire (F3), exclue par défaut des
   analyses, et simulateur réservé aux tenants de démonstration ou de test.
6. **Moyen — clés étrangères sans tenant.** Les tables existantes vérifient
   l'appartenance au tenant dans le code (tests à l'appui), pas dans la base. Un futur
   oubli dans le code pourrait relier deux clients. → renforcement par clés composées,
   étape dédiée après F1.
7. **Moyen — clôture d'intervention non structurée.** Le cahier la voulait « dès le
   premier jour » : ce sont les étiquettes dont dépendront le FDD, le ML et l'économie
   des actifs. → **F5**.
8. **Faible — ADR 001 « adopter Brick ».** À reformuler : vocabulaire interne aligné sur
   Brick, correspondances versionnées vers Brick, Haystack, ASHRAE 223P (encore à l'état
   de projet de norme), IFC, AAS. → fait avec cette ADR (complément dans l'ADR 001).
9. **Faible — journal d'audit sérialisé par tenant.** Parfait pour les actions sensibles,
   inadapté aux gros volumes : il ne doit jamais recevoir mesures ni événements
   techniques. → règle écrite au 2.7.
10. **Faible — rôles globaux par tenant.** Suffisants aujourd'hui ; l'arbre spatial
    fournira les périmètres du futur ReBAC (ADR 003), et les commandes exigeront des
    règles d'accès par attribut (ABAC) le moment venu.

## 6. Plan de migration

Chaque étape est livrée seule, testée, vérifiée en CI, puis soumise à l'accord de
Mohamed avant la suivante. Toutes les migrations suivent la règle des trois temps
(élargir, migrer, contracter) ; aucune n'efface de donnée métier.

| Étape | Contenu | Migrations | Impact sur le code existant |
|---|---|---|---|
| **F1 — Identité et relations** | `graph_nodes` + déclencheurs + rattrapage des lignes existantes (sites, positions, exemplaires) ; `relations` (bitemporelle, origine, confiance, statut, clés composées avec tenant) ; vocabulaire versionné des prédicats ; lecture des voisins d'un nœud | Élargir : nouvelles tables et déclencheurs. Migrer : rattrapage. Contracter : clés étrangères des tables existantes vers `graph_nodes` | Aucune route existante modifiée ; les tests insérant directement en SQL continuent de fonctionner grâce aux déclencheurs |
| **F2 — Modèle spatial (S1 de l'ADR 011)** | `spaces` (nœuds), `functional_locations.space_id` + historique, `functional_locations.kind` | Élargir seulement (colonnes facultatives) | Routes d'actifs complétées, rien de retiré |
| **F3 — Points et télémétrie v2** | `points` (nœuds, `is_writable = false` imposé), `external_identifiers`, refonte de `measurements` (point, dates de relevé et de réception, origine, drapeaux, clé anti-doublon), contrôles de qualité à la réception, simulateur adapté | Élargir : nouvelles colonnes et tables. Migrer : les mesures de test rattachées à des points. Contracter : retrait des anciennes colonnes | `POST /measurements` attend un point au lieu d'un nom libre : aucun client externe aujourd'hui, tests mis à jour |
| **F4 — Configuration versionnée et premiers constats** | `config_versions` ; `findings`, `diagnoses`, `recommendations` ; `desired_states` ; première règle de seuil et première règle d'écart souhaité/réel → constat → alarme → ordre de travail ; score de confiance v1 | Élargir seulement | Réutilise les alarmes et ordres de travail existants ; **termine le squelette de bout en bout M2** |
| **F5 — Cycle de vie, passeport QR, clôture structurée** | États et événements de cycle de vie ; étiquettes QR/NFC ; écran « passeport » mobile ; clôture structurée ; propriétés techniques (fluides frigorigènes) | Élargir seulement | Mobile et web complétés ; comble les écarts M1 |
| **F6 — Observabilité et résilience de base** | Logs structurés (identifiant de requête, tenant, sans donnée personnelle) ; document vivant des modes de défaillance pour chaque composant existant | Aucune | Aucun |
| **M3** | Identité des appareils et PKI, lien MQTT sécurisé, SDK de connecteur + certification, premier connecteur réel en lecture seule, TimescaleDB, contrôles de mise en service, métriques et traces | — | — |
| **M4** | Gestion de flotte Edge (mises à jour signées, déploiement progressif, retour arrière), résilience durcie | — | — |
| **DEFER** | Intentions de commande, arbitrage, moteur de sûreté (après levée explicite de la règle 1 et ADR 007) ; scénarios what-if ; économie des actifs ; DER ; mécanisme des Domain Packs ; assistance IA ; 3D | — | — |

L'ADR 011 (modèle spatial) reste valable ; son étape S1 devient F2 et ses points
(ancienne S5) remontent en F3. La règle de seuil annoncée pour M2 est intégrée à F4,
pour naître directement sous forme de configuration versionnée produisant un constat.

## 7. Garde-fous inchangés

- Règle non négociable 1 intacte : aucune ligne de ce plan n'écrit vers un équipement.
- Aucun modèle d'actifs parallèle : jumeau numérique, plans, BIM, mémoire opérationnelle
  et passeport sont des vues ou des références autour des mêmes identifiants.
- Chaque nouvelle table : `tenant_id`, RLS forcée, test d'isolation.
- Rien n'est écrasé : historiques, bitemporalité, versions.

## 8. Avancement (23 septembre 2026)

| Étape | État | Reste à faire (repris dans la matrice) |
|---|---|---|
| F1 | ✅ Livrée, CI verte | — |
| F2 | ✅ Livrée, CI verte | Plans 2D et IFC : ADR 011, plus tard |
| F3 | ✅ Livrée, CI verte | File des messages rejetés : M3 |
| F4 | ✅ Livrée, CI verte | Tables `diagnoses` / `recommendations` et statuts validé/approuvé : DEFER |
| F5 | ✅ Serveur livré ; écran passeport mobile par saisie du code ou lecture du QR par l'appareil photo (`expo-camera` 57.0.5, version du SDK 57 ; autorisations réduites au seul appareil photo) | Calcul CO₂ équivalent : DEFER ; essais sur téléphone réel. Clôture structurée saisie sur mobile hors ligne : faite (base locale versionnée, clôture rejouable côté API) |
| F6 | ✅ Logs JSON (identifiant de requête, tenant, sans donnée personnelle) ; [modes de défaillance](../architecture/failure-modes.md) | Doublon mobile trouvé en rédigeant, corrigé ensuite (clé `client_ref`, migration `c0b50f293eec`, élargir seulement) ; faille corrigée au passage : la confirmation d'une photo acceptait une clé de stockage d'un autre client |

## Conséquences

- L'ADR 001 reçoit un complément (vocabulaire interne + correspondances versionnées).
- L'ADR 011 reçoit un complément (espaces = nœuds du graphe, nouvelle numérotation).
- `CLAUDE.md` : étiquette DEFER ajoutée à la règle KEEP/REFACTOR/REPLACE/ADD, colonne
  Standard ajoutée au benchmark, règle du monolithe modulaire.
- La Feature Benchmark Matrix est réécrite avec la colonne Standard et les capacités de
  l'addendum.
- Cette ADR passera au statut « Acceptée » avec l'accord de Mohamed, avant l'étape F1.
