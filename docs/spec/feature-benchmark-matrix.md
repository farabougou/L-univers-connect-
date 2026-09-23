# Feature Benchmark Matrix — Physical Asset Intelligence & Automation OS

## But de ce document

Comparer en continu notre plateforme aux solutions importantes du marché
(GTB/GTC, GMAO, EMS, IoT/Edge, jumeaux numériques) et aux **standards** du secteur, pour
viser progressivement un niveau fonctionnel de référence mondiale — **sans copier les
concurrents ni réécrire ce qui existe déjà**. Le benchmark sert à apprendre du marché,
pas à copier aveuglément. Ce document est vivant : il est mis à jour à chaque étape (M1,
M2, M3…) et à chaque fois qu'une fonctionnalité importante est identifiée chez un
concurrent.

Directives d'origine : Mohamed, 23 septembre 2026 (directive initiale, puis
Architecture Addendum V2, qui ajoute la colonne **Standard** et l'étiquette **DEFER**).

## Concurrents suivis

- **Idealys** — GMAO/GTB pour le tertiaire (recherche web 2026 : peu de documentation
  publique indépendante trouvée ; à réévaluer avec une fiche produit officielle avant de
  fonder une décision dessus).
- **UBBEE / IOTEVA** — plateforme IoT/GTB (idem : peu de documentation publique
  indépendante trouvée lors de la recherche du 23/09/2026).
- **Smart & Connective** — « GTB Light » SaaS sans travaux pour tertiaire existant :
  pilotage CVC/éclairage par présence, plateforme multisite, automates propriétaires.
  Positionnement : économies d'énergie rapides à déployer, pas un GMAO ni un jumeau
  numérique complet.
- **MaintForge** — GMAO SaaS « IA-native » pour l'industrie : recommandation de
  stratégies de maintenance par IA, tournées techniciens optimisées, génération
  automatique de documents réglementaires (CERFA chaudières), packs IoT prêts à
  l'emploi.
- **Schneider Electric (EcoStruxure Building)**, **Siemens (Building X / Desigo)**,
  **Honeywell (Forge)**, **Johnson Controls (OpenBlue)** — grands éditeurs BMS/EMS/GMAO
  intégrés, connaissance générale (pas de fiche produit revérifiée ligne à ligne à cette
  date) : forces en connectivité multi-protocoles (BACnet/Modbus/OPC UA), automatisation
  et contrôle actif, IA prédictive, reporting ESG à grande échelle ; faiblesses connues
  du secteur : verrouillage fournisseur, coût et complexité d'intégration, hors ligne
  mobile souvent limité.
- **Outils spécialisés d'analytique et de mise en service continue** (par exemple
  SkySpark, Clockworks, CopperTree Kaizen) — connaissance générale, non revérifiée.

**Limite assumée** : les fiches des acteurs « niche » et les mentions marquées « non
revérifiée » restent volontairement prudentes — priorité donnée à ne pas inventer de
fonctionnalités que je ne peux pas vérifier. Ce tableau doit être corrigé dès qu'une
preuve concrète (démo, doc officielle, retour client) contredit une ligne.

## Processus d'évaluation (à appliquer à chaque nouvelle fonctionnalité identifiée)

1. Vérifier si elle existe déjà dans notre code.
2. Si elle existe : évaluer si l'implémentation est assez robuste, sécurisée et
   extensible (sinon → REFACTOR).
3. Si elle manque : déterminer si elle apporte une vraie valeur à notre vision (Physical
   Asset Intelligence & Automation OS, cœur universel multi-secteurs).
4. Si pertinente : l'ajouter à la roadmap et la concevoir proprement dans l'architecture
   existante (ADD), sans dépendance propriétaire dans le noyau (règle non négociable 8).
   Si elle doit être prévue maintenant mais développée plus tard : DEFER.
5. Si notre approche est meilleure ou volontairement différente : la garder et
   documenter pourquoi (colonne Justification).
6. Ne jamais ajouter une fonctionnalité uniquement pour gonfler le nombre de
   fonctionnalités.

Chaque ligne reçoit une décision **KEEP / REFACTOR / REPLACE / ADD / DEFER** — jamais de
redémarrage du projet à zéro. Les étapes F1 à F6 renvoient au plan de migration de
l'ADR 012.

## Matrice

### Fondations : identité, isolation, audit, sécurité

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Isolation multi-tenant stricte (RLS PostgreSQL forcée par table) | ✅ Fait — RLS forcée dès la première table, test d'isolation systématique | Rare chez les GTB/GMAO historiques (souvent isolation applicative seulement) | — | Critique | `services/api` (modèles + migrations) | KEEP + REFACTOR de renforcement (clés étrangères incluant le tenant) | Isolation au niveau base = impossible à contourner par un bug applicatif. Le renforcement rend aussi impossible un lien entre deux clients (ADR 012, risque 6). |
| Journal d'audit append-only chaîné par hachage | ✅ Fait (chaînage par tenant, verrou anti-concurrence) ; ancrage externe à faire | Standard chez les gros éditeurs sur les actions de sécurité ; rarement chaîné par hachage chez les acteurs de niche | — | Haute | `services/api/app/audit.py` | KEEP + ADD ancrage externe | Le chaînage détecte une falsification a posteriori. Réservé aux actions sensibles : jamais les mesures ni les événements à fort volume. |
| Identité universelle des actifs + registre commun (`graph_nodes`) | ✅ Fait (F1, 23/09/2026) — nœud créé par la base pour chaque site, position et exemplaire ; clés composées avec le tenant | Jumeaux numériques des grands éditeurs (non revérifié) | Brick, IFC GlobalId, AAS | Critique | `app/graph.py`, migrations 706eca882498 → 2a7235eda53c | ADD (F1) — fait | Base commune du graphe, du passeport QR et de la mémoire opérationnelle, avec contrôle d'intégrité par la base. |
| Authentification OIDC (Keycloak) + rafraîchissement de jeton sécurisé, web et mobile | ✅ Fait (PKCE + state CSRF web, refresh mobile) | Standard chez les grands éditeurs ; variable chez les acteurs de niche | OAuth 2.0, OIDC, RFC 7636 (PKCE) | Haute | `apps/web/src/lib/session.ts`, `apps/mobile/src/lib/auth.ts` | KEEP | Conforme aux bonnes pratiques actuelles. |
| Autorisations fines (rôles, périmètres, ABAC) | ⚠️ Partiel — rôles Keycloak globaux par tenant | Modèles plus fins chez les grands éditeurs | — | Moyenne | ADR 003 ; arbre spatial (ADR 011) comme futurs périmètres | DEFER (ReBAC au premier vrai cas de délégation) | Règle des trois : pas de ReBAC sans cas réel. L'arbre spatial fournira les périmètres naturels (site, bâtiment, zone). |
| Identité des appareils Edge / PKI | ❌ Absent | Passerelles des grands éditeurs (non revérifié) | X.509, mTLS, EST (RFC 7030), IEC 62443 | Haute à M3 | ADR 012 §2.10 | DEFER (M3), conçu | Identité des machines séparée de celle des personnes ; certificat lié au tenant et au site. |
| Frontière de sûreté (lecture seule garantie) | ✅ Règle non négociable 1, inscrite dans la base depuis F3 (`ck_points_read_only_c0`) | Les grands éditeurs commandent déjà | IEC 62443 (zones et conduits) | Critique | ADR 012 §2.6 | KEEP + ADD contrainte `is_writable = false` en base (F3) | Lever la règle 1 exigera une migration visible et relue, jamais une modification discrète. |

### Actifs, graphe, spatial, cycle de vie

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Modèle d'actifs à 3 niveaux (ProductModel / PhysicalUnit / FunctionalLocation) + révisions | ✅ Fait (ADR 001) | GMAO classiques souvent plates ; grands éditeurs plus riches mais propriétaires | ISO 14224 | Haute | `services/api` modèles | KEEP | Un nouvel équipement a toujours une nouvelle identité, la position garde la sienne : exactement ce que demande le cycle de vie. |
| Graphe de connaissances (feeds, poweredBy, servedBy, maintainedBy…) | ⚠️ Fondations faites (F1) — relations bitemporelles, jamais effacées, vocabulaire versionné, hiérarchie exposée sans copie ; pas encore d'espaces, de points ni de prestataires | Jumeaux numériques des grands éditeurs (non revérifié) | Brick (relations), ASHRAE 223P (projet de norme) | Critique | ADR 012 §2.2 : `relations` | ADD (F1) | Arbres stricts gardés en colonnes, relations transverses dans une table bitemporelle avec origine et confiance ; permet l'analyse d'impact d'une panne. |
| Hiérarchie spatiale (Portfolio → Site → Bâtiment → Étage → Zone/Pièce) | ✅ Fait (F2, 23/09/2026) — `spaces` (nœuds du graphe), emplacement historisé des positions, type système/équipement/composant ; Portfolio toujours différé | Standard chez Siemens, Schneider, Honeywell, Johnson Controls et logiciels de gestion immobilière (non revérifié) | IFC (IfcSite, IfcBuilding, IfcBuildingStorey, IfcSpace), Brick Location | Haute | `app/spatial.py`, `app/spatial_vocabulary.py`, migration 2f42a0af1365 | ADD (F2) + REFACTOR par ajout de colonnes — fait | Arbre spatial séparé de l'arbre technique : une CTA peut être au sous-sol et desservir cinq étages sans contorsion. |
| Aucun plan obligatoire (construction manuelle Bâtiment → Étage → Pièce → Équipement) | ⚠️ API faite (F2) — reste l'écran de la console web | Variable selon les éditeurs | — | Haute | ADR 011 : `spaces`, console web | ADD (F2, puis console) | Beaucoup de bâtiments tertiaires existants n'ont ni BIM ni plan à jour. |
| Plans 2D interactifs (visionneuse/éditeur) | ❌ Absent | Synoptiques des GTB (Siemens Desigo CC, Schneider EcoStruxure Building Operation…) ; Smart & Connective (non vérifié) | PDF, PNG, JPEG | Haute | ADR 011 : `floor_plans` versionnés + `plan_placements` | ADD (après F2) | Approche volontairement différente : le plan référence les identifiants du registre au lieu d'être un synoptique dessiné à la main qui duplique la liste des équipements. |
| Import BIM/IFC vers le registre | ❌ Absent | Jumeaux fondés sur le BIM chez les grands éditeurs (non revérifié) | IFC 4.3 (ISO 16739-1), COBie | Moyenne | ADR 011 : `external_identifiers` + propositions à valider | ADD (après les plans 2D) | L'import produit des propositions, jamais des données fiables sans validation humaine. |
| Visualisation 3D / BIM | ❌ Absent | Grands éditeurs | IFC | Basse pour le lancement | ADR 011 : visionneuse IFC open source reliée à nos identifiants | DEFER | Identité séparée de la géométrie : la 3D s'ajoutera comme une vue. |
| Analyse assistée par IA des plans et modèles BIM | ❌ Absent | Fonction émergente (acteurs non vérifiés) | — | Basse | ADR 011 : même circuit de propositions que l'IFC | DEFER | Toute détection reste une proposition vérifiable et corrigeable. |
| Cycle de vie de l'actif (commandé → installé → mis en service → déclassé) | ✅ Fait (F5) — états et historique ; installé/déposé imposés par les affectations (un exemplaire ne peut plus être monté à deux endroits) | GMAO et EAM classiques (IBM Maximo, SAP PM…) | ISO 55000, ISO 14224, COBie | Haute | ADR 012 §2.9 | KEEP + ADD états et événements (F5) | Réutilise le modèle « valeur courante + historique jamais modifié » déjà éprouvé. |
| Passeport numérique / QR-NFC depuis le mobile | ✅ Fait (F5) — étiquettes opaques révocables, passeport calculé selon les droits, écran mobile par saisie du code ; lecture caméra à venir | Courant en GMAO terrain | GS1 Digital Link ; passeport numérique produit de l'UE (règlement ESPR) | Haute | ADR 012 : étiquettes révocables + écran mobile | ADD (F5) | Le QR ne contient qu'un code opaque ; tout le contenu dépend des droits de la personne connectée. |
| Mémoire opérationnelle (pourquoi une configuration existe, des années après) | ⚠️ Partiel — audit, historiques, interventions existent séparément | Historique GMAO classique | — | Moyenne | ADR 012 §2.14 : chronologie par nœud | KEEP les briques + ADD la chronologie (F5-F6) | Pas de nouvelle base : un assemblage autour d'un même identifiant. |
| Interopérabilité sémantique (import/export de standards) | ⚠️ Partiel — ADR 001 alignée Brick, aucun export | SkySpark (Haystack), grands éditeurs (non revérifié) | Brick, Project Haystack, ASHRAE 223P, IFC, AAS (IEC 63278) | Moyenne | Vocabulaire interne versionné + correspondances | REFACTOR (ADR 001 complétée) + ADD correspondances au fil des besoins | Aligné sur les standards sans dépendre d'un seul. |

### Maintenance et terrain

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| GMAO de base (ordres de travail, interventions, rondes, alarmes) | ✅ Fait | Cœur de MaintForge, Idealys et des GMAO généralistes | Catégories CMMS/EAM usuelles | Haute | `services/api/app/routers/maintenance.py` | KEEP | Couvre le besoin M1. |
| Clôture structurée d'intervention (symptôme, cause, action, pièce, temps) | ⚠️ API faite (F5) — codes fermés inspirés ISO 14224, preuve immuable ; saisie mobile hors ligne à faire | GMAO matures | ISO 14224 (codification des défaillances) | Haute | ADR 012, étape F5 | ADD (F5) | Source des étiquettes dont dépendront FDD, ML et économie des actifs. |
| Application technicien hors ligne (file d'envoi idempotente) | ✅ Fait (SQLite, reprise étape par étape testée ; clé d'idempotence `client_ref` : un renvoi après réponse perdue ne crée plus de doublon) | Point faible fréquent des grands éditeurs | — | Haute | `apps/mobile` + `client_ref` unique par tenant côté API | KEEP + REFACTOR (clé d'idempotence, fait) | Avantage concret, pas un retard à combler. |
| Photos d'intervention (URL pré-signées) | ✅ Fait (ADR 006) | Courant en GMAO terrain | API S3 | Moyenne | `services/api`, `apps/mobile/src/lib/photos.ts` | KEEP | — |
| Documents réglementaires (CERFA fluides frigorigènes, F-Gas) | ❌ Absent | MaintForge le met en avant | Règlement F-Gas (UE) | Haute | Propriétés techniques (F5) + génération de documents | ADD (après F5) | Obligation réglementaire réelle du wedge CVC/froid. |
| Tournées techniciens optimisées | ❌ Absent | MaintForge | — | Basse pour le MVP | Planification | DEFER | Utile seulement avec plusieurs techniciens et tournées réelles à gérer. |
| Console web responsable d'exploitation | ✅ Fait (M1) | Tous les concurrents cités | — | Haute | `apps/web` | KEEP | — |

### Télémétrie, qualité des données, analytique

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Télémétrie en lecture seule | ✅ v2 faite (F3, 23/09/2026) — mesures par point, anti-doublon, conflit signalé jamais écrasé, réception par lot, origine et drapeaux de qualité ; pas encore de vrai connecteur | Standard chez tous les grands éditeurs et chez Smart & Connective | — | Critique | `app/telemetry.py`, ADR 012 §2.7 | REFACTOR (F3) — fait ; clé (point, date) compatible TimescaleDB | Le modèle actuel (nom libre, décimal seul, pas d'anti-doublon) bloquerait l'état réel, la qualité et l'envoi différé depuis l'Edge (ADR 012, risque 1). |
| Points (capteurs, consignes, états, compteurs) | ✅ Fait (F3) — nœuds du graphe, cycle proposé → validé → figé, unités UCUM contrôlées, `is_writable = false` imposé par la base | Standard GTB | Brick Point, BACnet objects, QUDT/UCUM (unités) | Critique | ADR 012 §2.7 | ADD (F3) | Unité de base de la télémétrie, de l'état réel/souhaité et de la qualité. |
| Qualité des données et score de confiance par point | ✅ Fait (F3-F4) — drapeaux à la réception + score de confiance explicable (figé, périmé, complétude, relevés douteux) ; les règles ne s'y fient pas en dessous du seuil | Outils d'analytique spécialisés (non revérifié) | OPC UA StatusCode, indicateurs d'état BACnet | Haute | ADR 012 §2.8 | ADD (F3 drapeaux, F4 score) | Une donnée douteuse n'est jamais utilisée aveuglément ; les règles le disent explicitement. |
| État souhaité / état réel et détection d'écart | ✅ Fait en lecture seule (F4) — attentes déclarées avec plage horaire et fuseau, règle d'écart → constat de mise en service | Jumeaux d'objets connectés des clouds (état souhaité/rapporté) | Tableau de priorités BACnet | Haute | ADR 012 §2.4 : `desired_states` | ADD (F3-F4) pour les attentes déclarées ; DEFER le cycle de commande | Utile dès la lecture seule : détection de gaspillage (« souhaité OFF, réel ON »). |
| FDD (détection et diagnostic de défauts) | ⚠️ Premier maillon (F4) — règles de seuil versionnées → constat → alarme → ordre de travail ; natures séparées ; diagnostics DEFER | Outils spécialisés, Siemens, Johnson Controls, Honeywell (non revérifié) | ASHRAE Guideline 36 (règles AFDD des CTA, issues des règles APAR du NIST) | Haute | ADR 012 §2.15 : `findings`, `diagnoses`, `recommendations` | ADD règles déterministes (F4) ; DEFER statistiques, modèles physiques, ML | Anomalie ≠ défaut ≠ diagnostic ≠ prédiction : natures séparées. Un LLM peut expliquer, jamais décider seul. |
| Mise en service et recommissioning continu | ⚠️ Modèle posé (F3-F4) — points proposés → validés, écarts à l'attendu en constats « commissioning » ; moteur de découverte DEFER (M3) | Outils spécialisés de mise en service continue (non revérifié) | ASHRAE Guideline 0 / 1.1 | Haute | ADR 012 §2.15 : statuts de mapping, attentes, constats `commissioning` | ADD le modèle (F3-F4) ; DEFER le moteur (M3+) | Un équipement connecté n'est jamais considéré comme bien configuré par défaut. |
| Maintenance prédictive / ML | ❌ Absent | MaintForge, Honeywell Forge, Siemens | — | Moyenne, après données réelles | Constats de nature `prediction` | DEFER | Sans données réelles de plusieurs cycles, un modèle serait invérifiable. |
| Affichage temps réel sur plan | ❌ Absent | Standard dans les GTB | — | Haute, après les points | ADR 011 + points (F3) | ADD (après plans 2D) | Occupation uniquement agrégée (vie privée). |

### Edge, connecteurs, commande

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Connecteurs protocoles terrain (BACnet, Modbus, OPC UA, MQTT) | ❌ Absent | Cœur des grands éditeurs ; Smart & Connective et UBBEE via leurs automates | BACnet (ASHRAE 135), Modbus, OPC UA, MQTT 5 | Haute | ADR 012 §2.12 : SDK de connecteur | DEFER (M3, un connecteur réel d'abord) | Contrat fixé maintenant ; écriture présente dans le contrat mais désactivée. |
| Certification des connecteurs (Experimental → Verified → Certified) | ❌ Absent | Programmes de certification des protocoles | BTL (BACnet), certification OPC Foundation | Moyenne | ADR 012 §2.12 | DEFER (M3) | Aucun connecteur tiers n'obtient automatiquement de droit de commande. |
| Edge runtime (tampon hors ligne, envoi différé) | ❌ Absent | Passerelles matures chez Schneider/Siemens ; automates Smart & Connective | MQTT 5 (sessions persistantes, QoS 1) | Haute | Agent Edge ; ingestion idempotente (F3) | DEFER (M3-M4) ; l'idempotence est préparée en F3 | Lien Edge ↔ cloud à concevoir bidirectionnel dès M3 (ADR 012, risque 4). |
| Gestion de flotte Edge (mises à jour signées, déploiement progressif, retour arrière) | ❌ Absent | Plateformes IoT des grands clouds (non revérifié) | TUF / Uptane (mises à jour sécurisées) | Moyenne | `config_versions` + identité des appareils | DEFER (M4) | Conçue pour une grande flotte, pas pour 10 passerelles. |
| Commande distante sécurisée | ❌ Absent, **interdit par la règle non négociable 1** | Honeywell Forge, Johnson Controls OpenBlue, Schneider EcoStruxure | IEC 62443 | N/A tant que la règle 1 n'est pas levée | ADR 012 §2.5-2.6 | DEFER (aucune table ni code) | Chaîne Identity → Authorization → Policy → Safety → Arbitration → Edge → Controller → Verification ; sécurités locales toujours prioritaires. |
| Arbitrage des commandes (priorités, dérogations temporaires, expiration) | ❌ Absent | Natif dans BACnet et les GTB | Tableau de priorités BACnet (16 niveaux) | N/A tant que la règle 1 n'est pas levée | ADR 012 §2.5 | DEFER, conçu | Arbitrage déterministe exécuté sur l'Edge pour fonctionner sans Internet ; anti-boucle par chaîne de causalité. |
| Moteur d'automatisation / GTB native | ❌ Absent | Cœur des grands éditeurs et de Smart & Connective | — | Postérieure à la sûreté | ADR 004 | DEFER | Aucune fonction de pilotage avant le feu vert explicite de Mohamed. |
| Retrofit léger (GTB non supposée, monitoring sans contrôle) | ✅ Principe respecté — registre et GMAO utilisables sans aucune connexion | Smart & Connective (GTB Light sans travaux) | LoRaWAN, EnOcean, Zigbee (capteurs sans fil de retrofit) | Haute | Profils d'intégration par site | KEEP + DEFER profils (M3) | Le client peut commencer par la maintenance seule, puis ajouter des capteurs. |

### Configuration, exploitation de la plateforme

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Configuration versionnée (version, auteur, raison, diff, retour arrière) | ✅ Fait (F4) — générique, raison obligatoire, une seule version active garantie par la base, retour arrière = nouvelle version | Variable | — | Haute | ADR 012 §2.11 : `config_versions` générique | ADD (F4) | Un seul mécanisme pour 12 types de configuration ; la première règle de seuil en sera la première utilisatrice. |
| Gestion des changements (brouillon → validation → approbation → déploiement → retour arrière) | ⚠️ Partiel (F4) — brouillon → actif → remplacé/retiré, validation automatique ; approbation à deux et simulation DEFER | Variable | — | Moyenne | Statuts de `config_versions` | ADD statuts minimaux (F4) ; DEFER simulation préalable et déploiement progressif | Indispensable avant toute automatisation à impact physique. |
| Observabilité (logs structurés, métriques, traces, fraîcheur) | ⚠️ Partiel — `/health`, `/health/db`, logs JSON avec identifiant de requête et tenant, sans donnée personnelle (F6) ; métriques et traces absentes | Plateformes des grands éditeurs | OpenTelemetry | Moyenne | `app/observability.py` (F6), OpenTelemetry (M3) | KEEP + ADD ; DEFER métriques/traces (M3) | Distinguer équipement, capteur, passerelle, connecteur et cloud en panne grâce aux relations `connectedTo`, pour éviter les avalanches d'alarmes. |
| Résilience et modes de défaillance documentés | ✅ Documenté (F6) — `docs/architecture/failure-modes.md`, composant par composant, risques ouverts signalés | — | — | Moyenne | Document vivant (F6), ingestion idempotente (F3) | KEEP + ADD ; DEFER file des messages rejetés (M3) | « Que se passe-t-il si ce composant tombe ? » documenté pour chaque composant. |
| API/connecteurs ouverts pour intégrations tierces | ⚠️ Partiel — API interne, pas encore publique et versionnée | Marketplace de connecteurs chez les grands éditeurs | OpenAPI | Basse | `services/api` | DEFER (marketplace hors périmètre 12 mois) | Pas de changement de cap pour suivre un concurrent. |
| Domain Packs (bâtiment, industrie, énergie, eau…) | ❌ Absent — catégories en texte libre | Offres par verticale des grands éditeurs | — | Basse | Vocabulaires versionnés par pack (F1, F3) | REFACTOR progressif + DEFER le mécanisme | Un pack apporte vocabulaire, règles et tableaux de bord, jamais une copie des moteurs. |

### Énergie, économie, simulation

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Reporting ESG / conformité énergétique (décret tertiaire, BACS) | ❌ Absent | Smart & Connective et les grands éditeurs | Décret tertiaire (OPERAT), décret BACS | Haute à moyen terme | Energy & Sustainability (M5) | DEFER (M5) | Déjà dans la feuille de route officielle. |
| Flexibilité énergétique / DER (solaire, batterie, bornes, effacement) | ❌ Absent | Grands éditeurs (non revérifié) | OpenADR, IEEE 2030.5, OCPP (bornes), SunSpec (solaire/batteries) | Basse | Classes d'équipements + points + relations `feeds`/`poweredBy` | DEFER | Le modèle générique suffit à les représenter ; aucun standard imposé au lancement. |
| Économie des actifs (coûts, garantie, remplacement) | ❌ Absent | EAM/GMAO matures | ISO 15686-5 (coût global) | Basse | Clôture structurée (F5) comme prérequis | DEFER | Aide à comparer des stratégies, sans jamais décider à la place du client. |
| Scénarios « what-if » / simulation | ❌ Absent | Grands éditeurs (jumeaux avancés) | EnergyPlus, Modelica | Basse | Espace de scénarios séparé ; origine `simulated`/`estimated` dès F3 | DEFER | Un résultat simulé n'est jamais présenté ni stocké comme une mesure. |
| Intelligence de flotte (analyse multi-sites) | ❌ Absent | Honeywell Forge, Johnson Controls OpenBlue | — | Basse | S'appuie sur RLS et le graphe | DEFER | Dépend d'un volume réel de sites. |

### Langage, codes et internationalisation (ADR 013)

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Référentiel terminologique unique (produit, documentation, API, support) | ⚠️ Projet — `docs/product/glossaire.md`, termes « à valider » | Souvent implicite chez les grands éditeurs ; incohérences fréquentes chez les acteurs de niche | NF EN 13306, ISA-18.2, ISO 55000, IFC, Brick | Haute | ADR 013, étape L1 | ADD | Un concept = un terme ; condition d'une IA, d'une documentation et d'un support cohérents. |
| Messages et erreurs par codes stables, traduits à l'affichage | ⚠️ Erreurs de l'API faites (L2 : 121 codes, français et anglais, RFC 9457) ; titres de constats encore stockés en français (L3) | Codes d'erreur courants chez Siemens, Schneider Electric ; variable ailleurs | RFC 9457 (Problem Details), ICU MessageFormat | Haute | ADR 013, étapes L2-L3 | REFACTOR | Les règles dépendent du code, pas de la phrase ; traduction sans réécriture des données. |
| Internationalisation français / anglais (dates, nombres, pluriels, fuseau du site) | ❌ Textes en dur, sites sans fuseau | Standard chez les grands éditeurs | Unicode CLDR, BCP 47, IANA tz | Haute | ADR 013, étape L4 | ADD | Coût faible aujourd'hui, élevé après la multiplication des écrans. |
| Taxonomie des signalements (nature, gravité, condition, acquittement, traitement) | ⚠️ Nature et gravité (3 niveaux sans définition) ; statut unique mêlant acquittement et condition | Gestion d'alarmes des GTB (Siemens Desigo CC, Honeywell, Johnson Controls) | ISA-18.2 / IEC 62682 | Haute | ADR 013, étape L3 | REFACTOR | Indispensable pour les alarmes de GTB en M3 (retour à la normale non acquitté). |
| Niveau de certitude des résultats d'analyse | ⚠️ Nature, méthode et confiance ; pas de niveau explicite | Rarement explicite sur le marché | — | Haute | ADR 013, section 4.4 (L3) | ADD | Ne jamais présenter une hypothèse ou une prédiction comme un fait. |
| État de fonctionnement et état de communication distincts | ❌ Absent | Courant en GTB, souvent confondus (« hors ligne » = « arrêté ») | Brick (points d'état) | Moyenne | ADR 013, section 4.5 (L6) | ADD | « Hors ligne » affiche le dernier état connu et sa date, jamais un état supposé. |
| Nomenclature des équipements (type universel, désignation constructeur, alias) | ❌ Catégorie en texte libre | Bibliothèques d'équipements chez les grands éditeurs | Brick (classes d'équipement) | Moyenne | ADR 013, étape L5 | REFACTOR | Condition de la recherche, des statistiques de flotte et de l'IA. |
| Présentation selon le profil (métier / technique) | ⚠️ Actions calculées par rôle dans le passeport | Vues par profil chez les grands éditeurs | — | Basse | ADR 013 (libellé métier + technique par terme) | KEEP + DEFER | L'information technique n'est jamais retirée, seulement présentée autrement. |
| Vocabulaire des commandes (demandée → vérifiée) | ✅ Défini, aucune commande codée | Chez les éditeurs de GTB, « envoyée » est souvent affiché comme « exécutée » | ISA-18.2 (acquittement distinct) | — | Glossaire, section 8 ; ADR 013, section 4.6 | DEFER | Prêt pour le jour où la règle 1 serait levée (ADR 007), sans ambiguïté avec l'acquittement d'alarme. |

## Décisions techniques actuelles signalées comme risques de blocage

La liste complète, classée par urgence, est tenue dans l'**ADR 012, section 5**. Rappel
des deux risques élevés :

1. **Modèle de télémétrie actuel** (nom libre, valeur décimale seule, pas
   d'anti-doublon, clé incompatible TimescaleDB) → corrigé à l'étape F3, tant qu'il n'y
   a que des données de test.
2. **Pas de registre d'identité commun** → corrigé à l'étape F1.

Risques ajoutés par l'ADR 013 (section 2) : **phrases générées stockées en base** pour
les constats (élevé, étape L3) ; **statut unique des alarmes** mêlant acquittement et
condition (élevé avant M3, étape L3) ; **catégories d'équipement en texte libre**
(moyen, étape L5).

Convention proposée par l'ADR 011, à appliquer dès maintenant : les bâtiments, étages,
pièces et zones ne sont plus créés comme positions fonctionnelles.

## Mise à jour de ce document

- À réviser à chaque jalon (M1 → M5) et chaque fois qu'une fonctionnalité concurrente
  significative est identifiée (nouvelle recherche, démo, retour client).
- Toute nouvelle ligne suit le processus d'évaluation en 6 étapes ci-dessus et reçoit
  une décision KEEP / REFACTOR / REPLACE / ADD / DEFER explicite et justifiée.
- Ne jamais ajouter une ligne juste pour « faire aussi bien » sur le nombre de
  fonctionnalités : seule la valeur réelle pour la vision Physical Asset Intelligence &
  Automation OS compte.
