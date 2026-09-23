# Feature Benchmark Matrix — Physical Asset Intelligence & Automation OS

## But de ce document

Comparer en continu notre plateforme aux solutions importantes du marché
(GTB/GTC, GMAO, EMS, IoT/Edge, jumeaux numériques) pour viser progressivement
un niveau fonctionnel de référence mondiale — **sans copier les concurrents
ni réécrire ce qui existe déjà**. Ce document est vivant : il est mis à jour
à chaque étape (M1, M2, M3...) et à chaque fois qu'une fonctionnalité
importante est identifiée chez un concurrent.

Directive d'origine : Mohamed, 23 septembre 2026.

## Concurrents suivis

- **Idealys** — GMAO/GTB pour le tertiaire (recherche web 2026 : peu de
  documentation publique indépendante trouvée ; à réévaluer avec une fiche
  produit officielle avant de fonder une décision dessus).
- **UBBEE / IOTEVA** — plateforme IoT/GTB (idem : peu de documentation
  publique indépendante trouvée lors de la recherche du 23/09/2026).
- **Smart & Connective** — « GTB Light » SaaS sans travaux pour tertiaire
  existant : pilotage CVC/éclairage par présence, plateforme multisite,
  automates propriétaires. Positionnement : économies d'énergie rapides à
  déployer, pas un GMAO ni un jumeau numérique complet.
- **MaintForge** — GMAO SaaS « IA-native » pour l'industrie : recommandation
  de stratégies de maintenance par IA, tournées techniciens optimisées,
  génération automatique de documents réglementaires (CERFA chaudières),
  packs IoT prêts à l'emploi.
- **Schneider Electric (EcoStruxure Building)**, **Siemens (Building X /
  Desigo)**, **Honeywell (Forge)**, **Johnson Controls (OpenBlue)** —
  grands éditeurs BMS/EMS/GMAO intégrés, connaissance générale (pas de
  fiche produit revérifiée ligne à ligne à cette date) : forces en
  connectivité multi-protocoles (BACnet/Modbus/OPC-UA), automatisation et
  contrôle actif, IA prédictive, reporting ESG à grande échelle ; faiblesses
  connues du secteur : verrouillage fournisseur, coût et complexité
  d'intégration, offline mobile souvent limité.

**Limite assumée** : les fiches des 4 acteurs « niche » restent
volontairement prudentes (peu de sources fiables trouvées) — priorité
donnée à ne pas inventer de fonctionnalités que je ne peux pas vérifier.
Ce tableau doit être corrigé dès qu'une preuve concrète (démo, doc
officielle, retour client) contredit une ligne.

## Processus d'évaluation (à appliquer à chaque nouvelle fonctionnalité identifiée)

1. Vérifier si elle existe déjà dans notre code.
2. Si elle existe : évaluer si l'implémentation est assez robuste, sécurisée
   et extensible (sinon → REFACTOR).
3. Si elle manque : déterminer si elle apporte une vraie valeur à notre
   vision (Physical Asset Intelligence & Automation OS, cœur universel
   multi-secteurs).
4. Si pertinente : l'ajouter à la roadmap et la concevoir proprement dans
   l'architecture existante (ADD), sans dépendance propriétaire dans le
   noyau (règle non négociable 8).
5. Si notre approche est meilleure ou volontairement différente : la garder
   et documenter pourquoi (colonne Justification).
6. Ne jamais ajouter une fonctionnalité uniquement pour gonfler le nombre de
   fonctionnalités.

Chaque ligne reçoit une décision **KEEP / REFACTOR / REPLACE / ADD** —
jamais de redémarrage du projet à zéro.

## Matrice

| Feature | Notre statut | Concurrent(s) | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|
| Isolation multi-tenant stricte (RLS PostgreSQL forcée par table) | ✅ Fait — RLS forcée dès la première table, test d'isolation systématique | Rare chez les GTB/GMAO historiques (souvent isolation applicative seulement, pas au niveau base) | Critique | `services/api` (modèles + migrations Alembic) | KEEP | Isolation au niveau base de données = impossible à contourner par un bug applicatif. C'est plus robuste que ce que font la plupart des concurrents connus ; aucune raison de changer. |
| Journal d'audit append-only chaîné par hachage | ✅ Fait | Standard chez les gros éditeurs (Schneider, Siemens...) sur les actions de sécurité ; rarement chaîné par hachage (intégrité vérifiable) chez les acteurs de niche | Haute | `services/api` (module audit) | KEEP | Le chaînage par hachage détecte une falsification a posteriori, pas seulement une trace — au-dessus du standard du marché. |
| Modèle d'actifs à 3 niveaux (ProductModel / PhysicalUnit / FunctionalLocation) + révisions (jamais d'écrasement) | ✅ Fait (ADR 001) ; typage explicite de la hiérarchie Facility/Building/Zone/System **pas encore fait** | Les GMAO classiques ont souvent un modèle plat (« équipement » + « site ») ; les grands éditeurs ont des jumeaux numériques plus riches mais propriétaires | Haute | `services/api` modèles + migrations | KEEP le principe / REFACTOR l'étendue plus tard | Bonne base pour un vrai jumeau numérique universel. On ajoute le typage de hiérarchie seulement quand un vrai besoin multi-portefeuilles apparaît (règle des trois), pas par anticipation. |
| GMAO de base (ordres de travail, interventions, alarmes) | ✅ Fait | Cœur de métier de MaintForge, Idealys et de tous les GMAO généralistes | Haute | `services/api/app/routers` | KEEP | Couvre le besoin M1. Les fonctions avancées (checklists réglementaires type CERFA, tournées optimisées) restent à évaluer plus bas. |
| Application technicien mobile hors ligne (offline-first, file d'attente de synchro idempotente) | ✅ Fait (SQLite outbox, sync idempotente testée) | Point faible fréquent chez les grands éditeurs (apps souvent dégradées hors connexion) ; MaintForge met en avant le terrain mais sans détail vérifié sur le offline | Haute | `apps/mobile` | KEEP | Notre approche (outbox local + reprise sans double-création) est déjà robuste et testée — c'est un avantage concret, pas un retard à combler. |
| Authentification OIDC (Keycloak) + rafraîchissement de jeton sécurisé, web et mobile | ✅ Fait (PKCE + state CSRF web, refresh mobile) | Standard chez les grands éditeurs ; variable chez les acteurs de niche | Haute | `apps/web/src/lib/session.ts`, `apps/mobile/src/lib/auth.ts` | KEEP | Conforme aux bonnes pratiques OAuth2/PKCE actuelles. |
| Stockage photos d'intervention (upload sécurisé, URL pré-signée) | ✅ Fait (ADR 006) | Fonctionnalité courante en GMAO terrain | Moyenne | `services/api`, `apps/mobile/src/lib/photos.ts` | KEEP | — |
| Génération automatique de documents réglementaires (ex. CERFA fluides frigorigènes, F-Gas) | ❌ Absent | MaintForge le met en avant explicitement pour le CVC | **Haute** — pertinent pour notre wedge CVC tertiaire (fluides frigorigènes = obligation réglementaire réelle en France/UE) | Nouveau module `services/api` (génération de documents) + template par type de document | ADD (roadmap M2/M3, après le squelette de bout en bout) | Valeur réelle et directement alignée avec notre wedge (CVC/froid) ; ne dépend d'aucune brique manquante (pas besoin de connecteurs GTB). Bon candidat pour un ADD relativement tôt. |
| Tournées techniciens optimisées (planification géographique/temporelle) | ❌ Absent | MaintForge le met en avant | Basse pour le MVP | `services/api` (planification) + mobile | Pas de décision immédiate | Valeur réelle mais seulement utile une fois plusieurs techniciens/tournées réelles à gérer (règle des trois : pas de client actif avec ce besoin aujourd'hui). À réévaluer quand un client réel le demande. |
| Connecteurs protocoles terrain (BACnet, Modbus, OPC-UA, MQTT) | ❌ Absent | Cœur de métier Schneider/Siemens/Honeywell/JCI ; Smart & Connective et UBBEE en dépendent aussi (automates propriétaires) | Haute (bloquant pour toute la suite : télémétrie, automatisation) | Nouvelle brique **Connector Layer**, à concevoir comme adaptateur générique (règle non négociable 8) | ADD (M3, un seul connecteur réel d'abord) | C'est la brique qui débloque le plus de valeur ensuite (télémétrie, EMS, automatisation). On commence par UN protocole réel avec un client pilote, jamais une couche d'abstraction générique inventée à l'avance sans cas réel. |
| Télémétrie en lecture seule (courbes, historisation) | ⚠️ Fondations posées (23/09/2026) — table `measurements` avec RLS + test d'isolation, ingestion d'un point simulé, lecture par position fonctionnelle ; pas encore de vrai connecteur, ni de courbes/tableau de bord | Standard chez tous les grands éditeurs et chez Smart & Connective | Haute | `services/api/app/telemetry.py`, `app/routers/telemetry.py`, table `measurements` | ADD en cours (M2, squelette de bout en bout) | Première brique du squelette de bout en bout (cahier des charges 36.2). Le premier connecteur réel et l'historisation à grande échelle (TimescaleDB) restent prévus pour M3, pas avant. |
| Edge runtime local (résilience coupure réseau, agrégation locale) | ❌ Absent | Schneider/Siemens ont des passerelles edge matures ; Smart & Connective a ses propres automates | Moyenne | Nouvelle brique **Edge Runtime** | ADD (M4) | Nécessaire pour un vrai produit « edge-first » mais dépend du Connector Layer — ordre respecté, pas de raccourci. |
| GTB/GTC natif (pilotage centralisé de tous les lots techniques) | ❌ Absent | Cœur de Schneider/Siemens/Honeywell/JCI et de Smart & Connective (GTB Light) | Haute mais **postérieure** à la sûreté | Brique **Automation & Control Engine** | ADD, strictement après le pipeline de sûreté (voir ADR 004) | Toute commande active reste bloquée par la règle non négociable 1 tant que Mohamed ne l'amende pas explicitement. Aucune fonctionnalité de pilotage ne sera codée avant ce feu vert, même si des concurrents l'ont déjà. |
| Commande distante sécurisée (write vers équipement) | ❌ Absent, **interdit par la règle non négociable 1** | Honeywell Forge, JCI OpenBlue, Schneider EcoStruxure le font | N/A tant que la règle 1 n'est pas levée | Brique **Remote Command**, derrière pipeline Observe→Understand→Decide→Simulate→Authorize→Execute→Verify→Learn | Pas de décision — explicitement hors périmètre sans accord écrit de Mohamed | Rappel direct de la règle non négociable 1 et de l'ADR 004 : aucun contournement, même partiel (pas de « juste un toggle simple »). |
| Maintenance prédictive / IA-ML sur données de télémétrie | ❌ Absent | Mis en avant par MaintForge (« IA-native »), Honeywell Forge, Siemens | Moyenne, **postérieure** à la télémétrie | Brique **AI/ML**, jamais en amont d'une commande (LLM ne pilote jamais un équipement, cf. directive OUDSAEVL) | ADD, seulement une fois des données réelles de plusieurs cycles de maintenance accumulées | Sans données réelles, un modèle prédictif serait inventé et non validable — règle des trois appliquée aux données, pas seulement au code. |
| Simulation (jumeau numérique prédictif, test de scénarios avant action) | ❌ Absent | Rare chez les acteurs de niche ; présent chez les grands éditeurs sous forme de « digital twin » avancé | Basse actuellement | Brique **Simulation Engine** | ADD (tardif, après automatisation) | Utile surtout une fois qu'il y a des commandes à tester avant exécution réelle — n'a pas de valeur isolée aujourd'hui. |
| Reporting ESG / conformité énergétique (F-Gas, DPE, décret tertiaire) | ❌ Absent | Smart & Connective et les grands éditeurs le proposent (argument de vente fort en France : décret tertiaire) | Haute à moyen terme | Brique **Energy & Sustainability** (M5, cahier des charges) | ADD (M5), mais les documents réglementaires CVC (ligne plus haut) peuvent démarrer avant | Directement dans notre roadmap officielle (M5) ; pas de changement à faire, juste confirmer l'ordre. |
| Intelligence de flotte (analyse comparative multi-sites/multi-clients) | ❌ Absent | Argument marketing fort chez Honeywell Forge et JCI OpenBlue (portefeuilles multi-bâtiments) | Basse actuellement | Brique **Fleet Intelligence**, s'appuie sur RLS multi-tenant existant | ADD (tardif) | Dépend d'un volume réel de sites/actifs pour être utile — prématuré avant plusieurs clients actifs avec plusieurs sites chacun. |
| API/connecteurs ouverts pour intégrations tierces | ⚠️ Partiel — API FastAPI interne existe, pas encore pensée comme API publique versionnée pour des tiers | Marketplace de connecteurs chez les grands éditeurs (hors périmètre 12 mois chez nous, décision déjà actée) | Basse (déjà explicitement hors périmètre 12 mois) | `services/api` | Pas de décision — conforme à la portée déjà actée | Rien à faire : notre propre feuille de route exclut déjà la marketplace de connecteurs pour 12 mois. Pas de changement de cap pour suivre un concurrent. |
| Web console responsable d'exploitation (registre d'actifs, planification d'ordres de travail) | ✅ Fait (vertical slice M1) | Équivalent chez tous les concurrents cités | Haute | `apps/web` | KEEP | — |
| Zero-Trust / sécurité des accès (rôles, permissions fines) | ⚠️ Partiel — rôles Keycloak de base ; pas de modèle de permissions fin (ReBAC) | Modèle de permissions souvent plus fin chez les grands éditeurs (multi-niveaux d'organisation) | Moyenne | `services/api` (autorisations, ADR 003) | Pas de décision immédiate (REFACTOR différé) | Règle des trois déjà appliquée : un modèle ReBAC complet a été volontairement reporté faute de 3 cas réels distincts. Cette matrice confirme que ce report reste correct — à revoir dès qu'un vrai besoin (ex. sous-traitant avec accès limité) apparaît. |

## Décisions techniques actuelles signalées comme à risque de blocage futur

Conformément à la demande explicite de Mohamed (« si une décision technique
actuelle risque de bloquer une capacité future importante, signale-la avant
de coder »), voici ce qui a été identifié en construisant cette matrice —
**aucun de ces points ne bloque aujourd'hui**, mais chacun mérite d'être
gardé en tête pour ne pas devoir réécrire plus tard :

1. **Couche de connecteurs pas encore conçue.** Tant qu'elle n'existe pas,
   c'est sans risque. Le risque apparaîtrait seulement si un premier
   connecteur était codé directement contre un protocole précis sans
   passer par un adaptateur générique (règle non négociable 8) — donc
   vigilance à avoir explicitement au moment de M3, pas maintenant.
2. **FunctionalLocation sans typage de hiérarchie.** Pas bloquant tant
   qu'un seul type de site est géré. Si un client avec plusieurs niveaux
   de portefeuille (ex. groupe → site → bâtiment → zone) arrive avant M2,
   il faudra une migration en trois temps (élargir/migrer/contracter,
   règle 6) plutôt qu'un ajout de colonne improvisé.
3. **Modèle de permissions Keycloak actuel (rôles simples).** Suffisant
   pour un seul niveau d'organisation par tenant. Si un client demande un
   sous-traitant avec accès restreint à un sous-ensemble de sites avant
   qu'un vrai modèle ReBAC soit conçu, ce sera un ADD, pas un blocage —
   mais mieux vaut le concevoir dès qu'un deuxième cas réel se présente
   plutôt qu'au moment où un client le réclame en urgence.
4. **Aucune dépendance propriétaire engagée pour l'instant** envers un
   fabricant ou un protocole précis — c'est une force, pas un risque : à
   maintenir strictement quand le Connector Layer sera conçu.

Aucun de ces points ne justifie un changement de code aujourd'hui. Ils sont
listés ici pour que la vigilance soit explicite au bon moment, pas oubliée.

## Mise à jour de ce document

- À réviser à chaque jalon (M1 → M5) et chaque fois qu'une fonctionnalité
  concurrente significative est identifiée (nouvelle recherche, démo,
  retour client).
- Toute nouvelle ligne suit le processus d'évaluation en 6 étapes ci-dessus
  et reçoit une décision KEEP/REFACTOR/REPLACE/ADD explicite et justifiée.
- Ne jamais ajouter une ligne juste pour « faire aussi bien » sur le nombre
  de fonctionnalités : seule la valeur réelle pour la vision Physical Asset
  Intelligence & Automation OS compte.
