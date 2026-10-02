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

### Statuts de validation (ADR 017, 1er octobre 2026)

Le manque de matériel terrain ne bloque plus la roadmap : `PRODUCT DEVELOPMENT TRACK`
(développement V1 à V4) et `PHYSICAL VALIDATION TRACK` (preuve sur site réel) sont deux
pistes séparées. Chaque capacité peut porter plusieurs de ces huit statuts, cumulables :
`IMPLEMENTED`, `UNIT_TESTED`, `SIMULATOR_TESTED`, `REPLAY_TESTED`, `INTEGRATION_TESTED`,
`FAILURE_TESTED`, `SHADOW_TESTED` (moteur de commande, toujours simulé — ADR 017 §4) et
`FIELD_TESTED`. Seul `FIELD_TESTED` peut rester `BLOCKED_EXTERNAL` sans bloquer aucun des
sept autres ni la roadmap — c'est l'état attendu, pas une anomalie, pour toute capacité
en attente d'une installation pilote réelle.

**Audit du 02/10/2026** (demande explicite de Mohamed : vérifier qu'aucun élément ne
dépend d'un achat de matériel ou d'une validation terrain pour continuer jusqu'à V4) —
**deux corrections de statut apportées le même jour par Mohamed** après une première
version de cet audit. Trois catégories distinctes existent dans cette matrice, à ne pas
confondre sous un même « bloqué » :

1. **Bloqué par le matériel/le terrain réel** (`FIELD_TESTED: BLOCKED_EXTERNAL`,
   vocabulaire ADR 017 — synonyme choisi par Mohamed : `DEFERRED_PHYSICAL_VALIDATION`,
   utilisé indifféremment dans cette matrice) — seule catégorie où manque un achat de
   matériel ou un accès site. Une seule ligne entièrement bloquée de la sorte :
   « Connecteurs protocoles terrain » (un vrai réseau BACnet/Modbus/OPC UA/MQTT ne se
   simule pas de façon fiable). **Correction du 02/10/2026** : « Maintenance
   prédictive / ML » n'appartient plus entièrement à cette catégorie — seule
   l'annonce d'une performance réelle y reste soumise (un historique réel de
   plusieurs cycles ne s'invente pas) ; le pipeline logiciel et sa validation en
   simulation avancent dès maintenant (voir la ligne dédiée).
2. **`DEFERRED_DOCUMENT`** (terme choisi par Mohamed le 02/10/2026, pas une question de
   matériel) — « Documents réglementaires (CERFA/F-Gas) » (modèle officiel manquant),
   « Reporting ESG/OPERAT » (spécification officielle manquante). Du code pourrait être
   écrit dès que le document arrive ; aucun achat, aucune visite terrain ; ce blocage ne
   retarde aucun autre chantier de la roadmap.
3. **Bloqué par une décision de sécurité déjà fixée, pas par une absence de matériel
   ni une question en attente** — « Commande distante sécurisée », « Arbitrage des
   commandes », « Moteur d'automatisation » : la règle non négociable 1 bloquerait
   même avec du matériel disponible. **Correction du 02/10/2026** : ce n'est pas une
   question ouverte à redemander à chaque audit — Mohamed a fixé la décision pour
   toute la roadmap : aucun LIVE CONTROL avant la fin de V4, Shadow/Dry Run continue
   de se développer et se prouver sans interruption ni nouvelle demande de feu vert.

Conclusion de l'audit : rien n'est actuellement mal classé, rien ne bloque le
développement du produit (V1 à V4) faute de matériel. Une correction a été faite en
passant : la ligne « Mise en service et recommissioning continu » affirmait encore
« moteur de découverte DEFER (M3) » alors que ce moteur existe pour BACnet depuis le
27/09/2026 (voir la ligne dédiée) — périmée, corrigée le jour de cet audit.

## Matrice

### Fondations : identité, isolation, audit, sécurité

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Isolation multi-tenant stricte (RLS PostgreSQL forcée par table) | ✅ Fait — RLS forcée dès la première table, test d'isolation systématique | Rare chez les GTB/GMAO historiques (souvent isolation applicative seulement) | — | Critique | `services/api` (modèles + migrations) | KEEP + REFACTOR de renforcement (clés étrangères incluant le tenant) | Isolation au niveau base = impossible à contourner par un bug applicatif. Le renforcement rend aussi impossible un lien entre deux clients (ADR 012, risque 6). |
| Journal d'audit append-only chaîné par hachage | ✅ Fait (chaînage par tenant, verrou anti-concurrence) ; ancrage externe fait (26/09/2026) — `app/audit_anchor.py` journalise périodiquement, pour chaque tenant, le dernier hachage connu dans les journaux applicatifs (hors Postgres), pour qu'un accès direct et complet à la base ne permette plus de réécrire toute la chaîne sans que cela se voie | Standard chez les gros éditeurs sur les actions de sécurité ; rarement chaîné par hachage chez les acteurs de niche | — | Haute | `services/api/app/audit.py`, `app/audit_anchor.py`, `scripts/anchor_audit_log.py` | KEEP + ADD ancrage externe (fait) | Le chaînage détecte une falsification a posteriori. Réservé aux actions sensibles : jamais les mesures ni les événements à fort volume. |
| Identité universelle des actifs + registre commun (`graph_nodes`) | ✅ Fait (F1, 23/09/2026) — nœud créé par la base pour chaque site, position et exemplaire ; clés composées avec le tenant | Jumeaux numériques des grands éditeurs (non revérifié) | Brick, IFC GlobalId, AAS | Critique | `app/graph.py`, migrations 706eca882498 → 2a7235eda53c | ADD (F1) — fait | Base commune du graphe, du passeport QR et de la mémoire opérationnelle, avec contrôle d'intégrité par la base. |
| Authentification OIDC (Keycloak) + rafraîchissement de jeton sécurisé, web et mobile | ✅ Fait (PKCE + state CSRF web, refresh mobile) | Standard chez les grands éditeurs ; variable chez les acteurs de niche | OAuth 2.0, OIDC, RFC 7636 (PKCE) | Haute | `apps/web/src/lib/session.ts`, `apps/mobile/src/lib/auth.ts` | KEEP | Conforme aux bonnes pratiques actuelles. |
| Autorisations fines (rôles, périmètres, ABAC) | ⚠️ Partiel — rôles Keycloak globaux par tenant | Modèles plus fins chez les grands éditeurs | — | Moyenne | ADR 003 ; arbre spatial (ADR 011) comme futurs périmètres | DEFER (ReBAC au premier vrai cas de délégation) | Règle des trois : pas de ReBAC sans cas réel. L'arbre spatial fournira les périmètres naturels (site, bâtiment, zone). |
| Identité des appareils Edge / PKI | ⚠️ Modèle cible posé (24/09/2026, `app/devices.py`) — identité par paire de clés asymétriques (EC P-256) et preuve cryptographique applicative (JWT ES256, RFC 7523, à usage unique et courte durée, anti-rejeu par `device_assertion_nonces`) : la clé privée ne quitte jamais l'appareil, jamais transmise ni journalisée. Pas de mTLS transport littéral (l'hébergeur ne vérifie pas de certificat client sur sa terminaison HTTPS standard — vérifié avant de coder) : HTTPS reste obligatoire, la preuve le complète sans le remplacer. `shared_secret` (secret partagé haché) gardé en compatibilité pour les appareils déjà provisionnés, migration par `set_public_key` (audité) ; jeton d'appareil HS256 15 min inchangé après authentification. Rotation de clé, révocation, statut en ligne/hors ligne/inconnu, empreinte de clé, historique des changements d'identité (journal d'audit) : déjà en place. mTLS transport et PKI gérée (autorité de certification, émission/rotation automatisées, EST/ACME) : DEFER, jusqu'à ce que la maturité et le nombre d'appareils le justifient — le concept d'identité ne changera pas à cette étape | Passerelles des grands éditeurs (non revérifié) | X.509, mTLS, EST (RFC 7030), RFC 7523 (JWT Bearer), IEC 62443 | Haute à M3 | ADR 012 §2.10 | ADD identité par clé publique (24/09/2026) ; KEEP shared_secret (compatibilité) ; DEFER mTLS transport/PKI gérée | Identité des machines séparée de celle des personnes ; migration vers PKI/mTLS géré prévue sans réécrire ce concept. |
| Frontière de sûreté (lecture seule garantie) | ✅ Règle non négociable 1, inscrite dans la base depuis F3 (`ck_points_read_only_c0`) | Les grands éditeurs commandent déjà | IEC 62443 (zones et conduits) | Critique | ADR 012 §2.6 | KEEP + ADD contrainte `is_writable = false` en base (F3) | Lever la règle 1 exigera une migration visible et relue, jamais une modification discrète. |
| Cybersécurité OT/GTB (segmentation, identités, accès, journalisation, résilience) | ✅ **02/10/2026 : audit documenté** — `docs/regulatory/05-anssi-cybersecurite-ot.md`, demandé par Mohamed, met en regard les recommandations ANSSI et l'architecture existante : chaque thème (réduction de la surface d'attaque, segmentation par construction de l'agent Edge, identités machine séparées des identités humaines, journalisation append-only, résilience par tenant) est déjà couvert par une brique construite pour d'autres raisons de sécurité. Aucune politique de segmentation réseau formalisée ni plan de réponse à incident documenté (dépendent d'un déploiement réel chez un client, pas du code) | Rarement documenté ainsi chez les acteurs de niche | ANSSI, cybersécurité des systèmes industriels ; IEC 62443 | Haute | `docs/regulatory/05-anssi-cybersecurite-ot.md` ; aucune nouvelle brique de code (audit de l'existant) | KEEP (aucun code nouveau nécessaire) ; `TO_FINALIZE` politique de segmentation et plan de réponse à incident (dépendent d'un site réel) | Les mesures de sécurité du dépôt n'ont jamais été construites « pour » ANSSI : elles existent pour la sûreté OT elle-même (règle non négociable 1 en premier lieu) et s'y trouvent alignées a posteriori — jamais l'inverse. |
| Protection des données personnelles (RGPD/CNIL) | ⚠️ **02/10/2026 : registre des traitements rédigé** — `docs/regulatory/04-rgpd-cnil.md` liste les cinq traitements réels du noyau (comptes/authentification, journal d'audit, interventions/clôtures/fiches F-Gas, photos d'intervention, prestataires) avec finalité, catégories de données, base légale et conservation ; mesures de sécurité déjà en place citées (RLS, identité des appareils par preuve cryptographique, append-only). **Lacune identifiée et signalée, pas corrigée** : aucun endpoint applicatif n'exporte ni n'anonymise les données personnelles d'une personne (champs texte libre `technician`/`closed_by`/`created_by`) — un administrateur Keycloak peut gérer un compte, rien ne couvre le noyau métier. Identité du responsable de traitement, sous-traitants réels, durées de conservation précises : `TO_FINALIZE` (dépendent de l'entreprise exploitante, pas du code) | Variable chez les acteurs de niche ; rarement un registre détaillé public | RGPD (règlement UE 2016/679), CNIL | Haute | `docs/regulatory/04-rgpd-cnil.md` | ADD registre des traitements (02/10/2026) ; DEFER export/effacement applicatif des données personnelles (prochain incrément, non bloquant pour V1-V4) ; `TO_FINALIZE` informations administratives | Minimisation déjà appliquée par construction : le noyau technique (actifs, points, mesures) ne porte aucune donnée personnelle, les noms de personnes n'apparaissent que là où une preuve réglementaire ou contractuelle l'exige. |

### Actifs, graphe, spatial, cycle de vie

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Modèle d'actifs à 3 niveaux (ProductModel / PhysicalUnit / FunctionalLocation) + révisions | ✅ Fait (ADR 001) | GMAO classiques souvent plates ; grands éditeurs plus riches mais propriétaires | ISO 14224 | Haute | `services/api` modèles | KEEP | Un nouvel équipement a toujours une nouvelle identité, la position garde la sienne : exactement ce que demande le cycle de vie. |
| Graphe de connaissances (feeds, poweredBy, servedBy, maintainedBy…) | ✅ Fait — relations bitemporelles, jamais effacées, vocabulaire versionné, hiérarchie exposée sans copie (F1) ; espaces et points déjà sujets/objets depuis F2-F3 (note « pas encore d'espaces, de points » périmée, corrigée le 27/09/2026). Prestataires (27/09/2026, `providers`) : seul type d'objet pour « maintainedBy », qui n'avait jusqu'ici aucune cible possible (`object_types = ()`) — un répertoire simple (nom, contact), enregistré dans graph_nodes comme les autres types ; écran web (27/09/2026) : gestion des prestataires dans le registre, déclaration/retrait d'un mainteneur sur la page d'un équipement. « dependsOn » (27/09/2026) : même écart comblé — le prédicat existait sans aucun consommateur, désormais utilisé par l'analyse d'impact (`app/impact_analysis.py`, voir ligne « Modèle État → Événement → Politique → Alerte ») | Jumeaux numériques des grands éditeurs (non revérifié) | Brick (relations), ASHRAE 223P (projet de norme) | Critique | ADR 012 §2.2 : `relations` ; `app/routers/providers.py`, migration 1017a1520913 ; `apps/web/src/app/registre/` ; `app/impact_analysis.py` | ADD (F1) ; ADD prestataires (27/09/2026) ; ADD écran web (27/09/2026) ; ADD usage de dependsOn (27/09/2026) | Arbres stricts gardés en colonnes, relations transverses dans une table bitemporelle avec origine et confiance ; permet l'analyse d'impact d'une panne. Un prestataire est un répertoire, jamais un compte : aucun accès à la plateforme. |
| Hiérarchie spatiale (Portfolio → Site → Bâtiment → Étage → Zone/Pièce) | ✅ Fait (F2, 23/09/2026) — `spaces` (nœuds du graphe), emplacement historisé des positions, type système/équipement/composant ; Portfolio toujours différé | Standard chez Siemens, Schneider, Honeywell, Johnson Controls et logiciels de gestion immobilière (non revérifié) | IFC (IfcSite, IfcBuilding, IfcBuildingStorey, IfcSpace), Brick Location | Haute | `app/spatial.py`, `app/spatial_vocabulary.py`, migration 2f42a0af1365 | ADD (F2) + REFACTOR par ajout de colonnes — fait | Arbre spatial séparé de l'arbre technique : une CTA peut être au sous-sol et desservir cinq étages sans contorsion. |
| Aucun plan obligatoire (construction manuelle Bâtiment → Étage → Pièce → Équipement) | ✅ Fait (F2, console web 24/09/2026) — création, fermeture et placement d'un équipement dans un bâtiment/local depuis `/registre` | Variable selon les éditeurs | — | Haute | ADR 011 : `spaces`, console web | ADD (F2, puis console) — fait | Beaucoup de bâtiments tertiaires existants n'ont ni BIM ni plan à jour. |
| Plans 2D (envoi, versions, affichage) | ✅ Étape S3 faite (26/09/2026) — `floor_plans` (PDF/PNG/JPEG, stocké comme les photos, empreinte SHA-256, une nouvelle version jamais un écrasement, protégé en base contre toute modification/suppression comme les autres preuves) ; endpoints d'envoi (URL présignée puis confirmation), liste par espace, lecture ; console web (sélection d'un espace, liste des versions avec lien de téléchargement, envoi d'un nouveau plan) | Synoptiques des GTB (Siemens Desigo CC, Schneider EcoStruxure Building Operation…) ; Smart & Connective (non vérifié) | PDF, PNG, JPEG | Haute | `app/floor_plans.py`, `app/routers/floor_plans.py`, migration f65006c6d8c7, `apps/web/src/app/registre` | ADD (S3, fait) | Approche volontairement différente : le plan référence les identifiants du registre au lieu d'être un synoptique dessiné à la main qui duplique la liste des équipements. Affichage natif du navigateur (lien de téléchargement, rendu PDF/image intégré au navigateur) plutôt que pdf.js : même résultat sans dépendance supplémentaire. |
| Placement des actifs sur un plan | ✅ Étape S4 complète (26/09/2026) — `plan_placements` : espace, position fonctionnelle ou point (exactement un des trois, vraies clés étrangères), coordonnées normalisées (0 à 1, indépendantes de la résolution de l'image), cycle proposé → validé, journal d'audit sur chaque action ; aucun nom ni caractéristique d'équipement copié (tout se lit depuis le registre). Éditeur visuel (`/registre/plans/{id}`, PNG/JPEG uniquement) : cliquer sur l'image du plan capture la position, choisir l'espace ou la position fonctionnelle visée, puis valider ou supprimer un repère depuis une liste — seul composant client (JavaScript navigateur) de toute la console web, le reste des actions restant des formulaires ordinaires. Repère de type point : lecture seule dans cette liste, pas encore créable depuis l'éditeur visuel (reste possible par l'API) | Éditeurs de synoptiques des grands éditeurs (non revérifié) | GeoJSON (coordonnées normalisées, même principe) | Haute | `app/plan_placements.py`, `app/routers/floor_plans.py`, migration 583c6957ff99 ; `apps/web/src/app/registre/plans/[floorPlanId]/` | ADD (S4, complet le 26/09/2026) | Modifiable/supprimable directement (pas une preuve comme audit_log ou les clôtures) : un placement décrit une position d'affichage, jamais un fait opérationnel de l'actif — celui-ci reste entièrement dans functional_locations/points/spaces, inchangés. |
| Import BIM/IFC vers le registre | ✅ Fait (26/09/2026, décision explicite de Mohamed pour la dépendance externe) — envoi d'un fichier IFC (dance en deux temps : URL présignée puis confirmation, comme les photos et les plans), analyse par `ifcopenshell` (LGPL-3.0-or-later, mûre, maintenue, binaires précompilés compatibles avec notre image Docker — vérifié avant d'ajouter la dépendance), jamais appelée hors de `app/importers/ifc_parser.py` : le domaine (`app/ifc_import.py`) ne connaît que des structures simples (espaces et équipements candidats), jamais la bibliothèque. Correspondance sûre uniquement (IfcBuilding/IfcBuildingStorey/IfcSpace, déjà déclarée dans `app/spatial_vocabulary.py` ; IfcZone et IfcSite volontairement ignorés, aucune correspondance fiable) ; équipements limités au sous-arbre IFC4 de distribution CVC/froid/plomberie/électricité (`IfcDistributionElement` et proches). Chaque élément reste une proposition jusqu'à acceptation par une personne, dans l'ordre de la hiérarchie (bâtiment → étage → pièce → équipement), qui crée alors un vrai espace ou une vraie position par les mêmes fonctions que la saisie manuelle (`app.spatial.create_space`, `app.assets.create_functional_location` — un seul chemin de création). Protections avant tout appel à la bibliothèque : taille maximale (200 Mo), en-tête ISO 10303-21 obligatoire, toute exception non prévue de la bibliothèque devient une erreur de format ordinaire. IFC-ZIP, IfcXML, IFC 4.3 et COBie : pas encore pris en charge (seul le texte STEP IFC4/IFC2X3 est lu). Console web (26/09/2026, `/registre`) : envoi du fichier par site, liste des imports avec leur état et leurs compteurs, liste des propositions avec bouton accepter/refuser (motif obligatoire) ; pas encore de visualisation graphique de la hiérarchie, seulement une liste | Jumeaux fondés sur le BIM chez les grands éditeurs ; IBM Maximo Real Estate and Facilities (revérifié 26/09/2026 : connecteur qui crée bâtiment/étage/espaces/actifs depuis un modèle Revit à la livraison) | IFC 4.3 (ISO 16739-1), COBie | Moyenne | `app/importers/ifc_parser.py` (adaptateur, seul point de dépendance), `app/ifc_import.py` (domaine), migration b202e7f21592 ; ADR 011 : propositions à valider | ADD (26/09/2026) ; DEFER IFC-ZIP/IfcXML/IFC 4.3/COBie tant qu'un besoin réel ne les impose pas | L'import produit des propositions, jamais des données fiables sans validation humaine. Bibliothèque isolée derrière un adaptateur : la remplacer (ou changer de version majeure) ne touche jamais `app/ifc_import.py` ni le reste du domaine. |
| Visualisation 3D / BIM | ❌ Absent | Grands éditeurs | IFC | Basse pour le lancement | ADR 011 : visionneuse IFC open source reliée à nos identifiants | DEFER | Identité séparée de la géométrie : la 3D s'ajoutera comme une vue. |
| Analyse assistée par IA des plans et modèles BIM | ❌ Absent | Fonction émergente (acteurs non vérifiés) | — | Basse | ADR 011 : même circuit de propositions que l'IFC | DEFER | Toute détection reste une proposition vérifiable et corrigeable. |
| Cycle de vie de l'actif (commandé → installé → mis en service → déclassé) | ✅ Fait (F5) — états et historique ; installé/déposé imposés par les affectations (un exemplaire ne peut plus être monté à deux endroits) | GMAO et EAM classiques (IBM Maximo, SAP PM…) | ISO 55000, ISO 14224, COBie | Haute | ADR 012 §2.9 | KEEP + ADD états et événements (F5) | Réutilise le modèle « valeur courante + historique jamais modifié » déjà éprouvé. |
| Nettoyage du registre (doublons, sites/équipements de test) | ✅ Fait (30/09/2026, demande de Mohamed après un doublon de site créé par double-clic sur mobile) — **archivage, jamais une suppression** : migration a3e8c1f0d9b2 (`archived_at`/`archived_by`, nullable, sur `sites` et `functional_locations`) ; `app/assets.py::archive_site/unarchive_site/archive_functional_location/unarchive_functional_location`, idempotents ; `POST /sites/{id}/archive`, `/unarchive` et les mêmes pour `/functional-locations/{id}` (rôles responsable_exploitation/admin_tenant) ; `GET /sites` et `GET /functional-locations` excluent les archivés par défaut, `include_archived=true` les redonne pour les désarchiver. Console web (`/registre`) : bouton « Archiver » sur chaque ligne, section repliée « N site(s)/équipement(s) archivé(s) » avec bouton « Désarchiver ». Un vrai DELETE SQL n'a jamais été envisagé au-delà de la question initiale : il aurait contredit la règle non négociable 3 (rien n'est écrasé) et le motif de protection déjà en place au niveau base pour `audit_log`, `config_versions`, `relations`, `floor_plans` et `intervention_closures` (déclencheurs `..._no_delete`, voir `tests/db_helpers.py`) — l'archivage suit exactement le même principe, étendu à `sites` et `functional_locations` | GMAO matures : statut « inactif »/« archivé » plutôt qu'une suppression réelle | — | Moyenne | Migration a3e8c1f0d9b2 ; `app/assets.py`, `app/routers/assets.py` ; `apps/web/src/app/registre/` | ADD (30/09/2026) | **Grille produit (ADR 014)** : Backend DONE, API DONE, Web DONE, Mobile N/A (nettoyage du registre, pas un geste terrain), Edge N/A, Tests DONE (domaine, API, isolation tenant, actions web — 15 tests API + 4 tests web ajoutés, suite complète 692 tests API + 103 tests web au vert), Documentation DONE (ce document). Aucune cascade automatique (archiver un site n'archive pas ses équipements) : décision volontaire pour rester simple tant qu'aucun besoin réel ne l'impose — signalé ici pour ne pas le perdre de vue. |
| Passeport numérique / QR-NFC depuis le mobile | ✅ Fait (F5) — étiquettes opaques révocables, passeport calculé selon les droits, écran mobile par lecture du QR ou saisie du code (non testé sur téléphone réel). Jumeau numérique V1 (24/09/2026) : chaque point réunit maintenant état réel (mesure), état souhaité déclaré (`app/desired_states.py`) et commandes de test (`app/commands.py`) dans la même réponse — identité, métadonnées, relations, état actuel, télémétrie, événements et historique d'audit étaient déjà présents séparément | Courant en GMAO terrain | GS1 Digital Link ; passeport numérique produit de l'UE (règlement ESPR) | Haute | ADR 012 : étiquettes révocables + écran mobile ; ADR 004 (jumeau numérique) | ADD (F5) ; ADD état souhaité + commandes au passeport (24/09/2026) | Le QR ne contient qu'un code opaque ; tout le contenu dépend des droits de la personne connectée. Un seul modèle de lecture pour tout le jumeau, pas une vue par fonctionnalité. |
| Mémoire opérationnelle (pourquoi une configuration existe, des années après) | ✅ Chronologie faite côté moteur (26/09/2026) — `GET /graph/nodes/{id}/timeline` (position fonctionnelle ou exemplaire) fusionne interventions, changements de statut d'ordre de travail, changements d'alarme, changements de constat et, pour un exemplaire, son cycle de vie, la plus récente d'abord ; pagination par curseur de date (`before`) pour remonter dans une longue histoire sans tout charger. Vue pure comme le passeport : rien de nouveau n'est stocké. `config_versions` volontairement laissé hors de cette fusion (son lien à une position n'est qu'indirect par `subject_key`) : son propre diff entre versions, déjà exposé depuis la fiche équipement, reste la référence pour « pourquoi cette configuration ». **Web faite (27/09/2026, ADR 014 §9)** : section « Chronologie » sur la fiche équipement (`/registre/{id}`), pagination « Voir plus ancien ». **Mobile fait (01/10/2026)** : même section sur l'écran passeport (`apps/mobile/app/passeport.tsx`, `fetchTimeline` dans `src/lib/passport.ts`), même donnée et même comportement (bouton « Voir plus ancien » quand la page est pleine), aucune traduction nouvelle (le catalogue partagé `timeline.*` existait déjà) | Historique GMAO classique | — | Moyenne | `app/timeline.py`, `app/routers/passport.py`, `apps/web/src/app/registre/[id]/`, `apps/mobile/app/passeport.tsx` | KEEP les briques + ADD la chronologie (26/09/2026) ; ADD l'écran web (27/09/2026) ; ADD l'écran mobile (01/10/2026) | **Grille produit (ADR 014)** : Backend DONE, API DONE, Web DONE (27/09/2026), Mobile DONE (01/10/2026), Edge N/A, Tests DONE, Documentation DONE. Pas de nouvelle base : un assemblage, au moment de la consultation, des historiques qui existent déjà séparément. |
| Interopérabilité sémantique (import/export de standards) | ⚠️ Partiel — ADR 001 alignée Brick, aucun export | SkySpark (Haystack), grands éditeurs (non revérifié) | Brick, Project Haystack, ASHRAE 223P, IFC, AAS (IEC 63278) | Moyenne | Vocabulaire interne versionné + correspondances | REFACTOR (ADR 001 complétée) + ADD correspondances au fil des besoins | Aligné sur les standards sans dépendre d'un seul. |

### Maintenance et terrain

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| GMAO de base (ordres de travail, interventions, rondes, alarmes) | ✅ Fait | Cœur de MaintForge, Idealys et des GMAO généralistes | Catégories CMMS/EAM usuelles | Haute | `services/api/app/routers/maintenance.py` | KEEP | Couvre le besoin M1. |
| Clôture structurée d'intervention (symptôme, cause, action, pièce, temps) | ✅ Fait (F5) — codes fermés inspirés ISO 14224, preuve immuable, saisie mobile hors ligne (non testée sur téléphone réel) | GMAO matures | ISO 14224 (codification des défaillances) | Haute | ADR 012, étape F5 | ADD (F5) | Source des étiquettes dont dépendront FDD, ML et économie des actifs. |
| Application technicien hors ligne (file d'envoi idempotente) | ✅ Fait (SQLite, reprise étape par étape testée ; clé d'idempotence `client_ref` : un renvoi après réponse perdue ne crée plus de doublon) | Point faible fréquent des grands éditeurs | — | Haute | `apps/mobile` + `client_ref` unique par tenant côté API | KEEP + REFACTOR (clé d'idempotence, fait) | Avantage concret, pas un retard à combler. |
| Photos d'intervention (URL pré-signées) | ✅ Fait (ADR 006) | Courant en GMAO terrain | API S3 | Moyenne | `services/api`, `apps/mobile/src/lib/photos.ts` | KEEP | — |
| Documents réglementaires (CERFA fluides frigorigènes, F-Gas) | ✅ **02/10/2026 : débloqué, modèle de données fait** — Mohamed a fourni le CERFA 15497*04 officiel (PDF, formulaire interactif à 72 champs), condition exacte posée le 27/09/2026 pour lever `DEFERRED_DOCUMENT`. Nouvelle table `fgas_intervention_records` (migration adce8b5d46b8) : une fiche par intervention, preuve légale jamais modifiée ni supprimée (mêmes déclencheurs que `intervention_closures`/`documents`), toutes les identités (opérateur, détenteur, équipement, fluide) enregistrées en texte au moment de la signature — jamais une référence vivante qu'un renommage ultérieur pourrait changer. `app/fgas.py` (`record_fgas_intervention`, même protection contre la double saisie terrain que `app.closures`) ; `app/fgas_vocabulary.py` : 8 codes de nature d'intervention ([4] du formulaire), 4 codes de classification ADR/RID ([12]), catalogue `shared/i18n/*/fgas.json`. Les totaux de manipulation ([11], A+B+C et D+E) sont calculés par le domaine à partir de leurs composants, jamais acceptés indépendamment — élimine une classe d'erreur possible sur le papier. **Point resté ouvert, distinct du blocage levé** : le tonnage équivalent CO2 ([3]) reste une saisie manuelle de l'opérateur, comme sur le papier — son calcul exigerait une table officielle de PRG (pouvoir de réchauffement global) vérifiée, qu'aucun document fourni ne contient encore (même réserve déjà posée dans `app/properties.py` pour les propriétés techniques F-Gas) ; jamais une valeur devinée. **02/10/2026 (suite) : remplissage réel du PDF officiel** — `app/fgas_pdf.py` (dépendance `pypdf==6.19.0`, pure Python, licence BSD, sans dépendance native) remplit les 72 champs du formulaire AcroForm fourni (`app/resources/cerfa_15497-04.pdf`, document public de l'administration) à partir de la fiche déjà enregistrée ; `GET /interventions/{id}/fgas/cerfa.pdf` renvoie le PDF rempli en téléchargement. Limite assumée et documentée dans le code : les cases de fréquence minimale de contrôle ([6]/[8]/[9], qui exigeraient de classer le fluide saisi en texte libre dans une famille HCFC/HFC/HFO) restent vierges — aucune table de correspondance fiable et exhaustive n'a été fournie, et inventer ce classement violerait la règle du dépôt sur les données réglementaires. **02/10/2026 (suite) : Trackdéchets/BSFF** — `app/connectors/trackdechets.py`, interface abstraite `TrackDechetsClient` dans le même style que les connecteurs protocolaires (Modbus, BACnet, OPC UA, MQTT) : aucun compte ni jeton Trackdéchets fourni, `NotConfiguredTrackDechetsClient` échoue explicitement plutôt que de prétendre consulter un bordereau (`DEFERRED_EXTERNAL_INTEGRATION`, voir `docs/regulatory/03-trackdechets-bsff.md`). Le numéro de BSFF (`bsff_number`) était déjà une saisie manuelle dans `app/fgas.py`, inchangée — ce module permettra un jour de le vérifier, pas de le remplacer. **02/10/2026 (suite) : API et saisie terrain hors ligne** — `POST`/`GET /interventions/{id}/fgas` et `GET /fgas-vocabulary` (`app/routers/maintenance.py`), mêmes codes d'erreur et même protection contre la double saisie que la clôture structurée ; écran mobile (`app/nouvelle-intervention.tsx`) : bascule « Remplir la fiche fluides frigorigènes », formulaire complet (identités, nature d'intervention et classification ADR/RID à cases multiples, fuites, quantités, signature), saisi et stocké hors ligne (`pending_interventions.fgas`, migration locale SQLite n°3) puis envoyé après la photo et la clôture, rejouable comme elles (`src/lib/sync.ts::sendFgas`) | MaintForge le met en avant | Règlement F-Gas (UE), CERFA 15497*04, API Trackdéchets | Haute | `app/fgas.py`, `app/fgas_vocabulary.py`, `app/fgas_pdf.py`, `app/resources/cerfa_15497-04.pdf`, `app/routers/maintenance.py`, migration adce8b5d46b8, `app/connectors/trackdechets.py` ; `apps/mobile/src/lib/fgas.ts`, `src/lib/db.ts`, `src/lib/sync.ts`, `src/lib/localSchema.ts`, `app/nouvelle-intervention.tsx` ; `shared/i18n/*/fgas.json`, `docs/regulatory/03-trackdechets-bsff.md` | ADD modèle de données + domaine (02/10/2026) ; ADD API + écran mobile hors ligne (02/10/2026) ; ADD remplissage PDF officiel (`pypdf`, 02/10/2026) ; DEFER calcul du tonnage CO2 (table PRG manquante, saisie manuelle en attendant) ; DEFER classement HCFC/HFC/HFO pour les cases de fréquence de contrôle (aucune table de correspondance fiable fournie), écran web de consultation ; ADD interface Trackdéchets (02/10/2026) ; `DEFERRED_EXTERNAL_INTEGRATION` consultation réelle d'un BSFF | **Grille produit (ADR 014)** : Backend DONE (domaine + migration + RLS + preuve non modifiable + remplissage CERFA officiel), API DONE (02/10/2026, y compris `GET .../fgas/cerfa.pdf`), Web N/A (geste terrain, pas de saisie de bureau prévue pour cette fiche), Mobile DONE (02/10/2026, hors ligne complet), Edge N/A, Tests DONE (15 tests sur la fiche, 17 tests API — enregistrement, idempotence, conflit, validations, isolation tenant, catalogue, téléchargement CERFA —, 2 tests unitaires sur le remplissage PDF (`test_fgas_pdf.py`), 18 tests unitaires mobiles (`fgas.test.ts`) et 3 tests de synchronisation hors ligne (`sync.test.ts`) ; 1 test sur l'adaptateur Trackdéchets, qui échoue explicitement plutôt que de prétendre réussir ; 893 tests backend, 167 tests web et 114 tests mobile au vert sans régression), Documentation DONE (ce document). Un formulaire inventé aurait été pire qu'aucun formulaire ; celui-ci reproduit exactement le CERFA officiel, champ par champ, et le remplit réellement. |
| Tournées techniciens optimisées | ❌ Absent | MaintForge | — | Basse pour le MVP | Planification | DEFER | Utile seulement avec plusieurs techniciens et tournées réelles à gérer. |
| Console web responsable d'exploitation | ✅ Fait (M1, étoffée 24/09/2026) — registre (sites, bâtiments/locaux, équipements, étiquettes), fiche équipement (état, mesures, consignes, règles de détection, connexion Modbus), alarmes/constats (acquitter, retour à la normale, faux positif, clore, confirmer), ordres de travail (création, statut, lien vers l'équipement), cycle de vie, caractéristiques techniques. Vue d'ensemble Portfolio (27/09/2026, ADR 014 §2) : l'accueil (`/`), auparavant un tableau plat de tous les équipements, devient un vrai regroupement par site — KPI de patrimoine (sites, équipements, alarmes/constats ouverts par gravité, ordres de travail ouverts), une ligne par site avec sa propre répartition par gravité et l'état de ses passerelles Edge (colonne absente pour un rôle sans droit de gestion, jamais une colonne à zéro fabriquée), puis un drill-down (`?site=`) vers ses équipements — aucun endpoint créé, uniquement `/sites`, `/functional-locations`, `/alarms`, `/findings`, `/work-orders`, `/devices`, déjà existants | Tous les concurrents cités | — | Haute | `apps/web/src/app/page.tsx`, `apps/web/src/lib/portfolio.ts` | KEEP + ADD la vue Portfolio (27/09/2026) | **Grille produit (ADR 014)** : Backend DONE, API DONE, Web DONE (vue Portfolio), Mobile N/A (supervision approfondie multi-sites, hors périmètre terrain — ADR 014 §11), Edge N/A, Tests DONE (`portfolio.test.ts`, agrégation testée indépendamment du rendu), Documentation DONE. |

### Télémétrie, qualité des données, analytique

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Télémétrie en lecture seule | ✅ v2 faite (F3, 23/09/2026) — mesures par point, anti-doublon, conflit signalé jamais écrasé, réception par lot, origine et drapeaux de qualité. Connecteur Modbus relié (24/09/2026, `app/connectors/ingest.py`) : validé contre un simulateur logiciel, jamais encore contre un appareil réel | Standard chez tous les grands éditeurs et chez Smart & Connective | — | Critique | `app/telemetry.py`, ADR 012 §2.7 | REFACTOR (F3) — fait ; clé (point, date) compatible TimescaleDB | Le modèle actuel (nom libre, décimal seul, pas d'anti-doublon) bloquerait l'état réel, la qualité et l'envoi différé depuis l'Edge (ADR 012, risque 1). |
| Points (capteurs, consignes, états, compteurs) | ✅ Fait (F3) — nœuds du graphe, cycle proposé → validé → figé, unités UCUM contrôlées, `is_writable = false` imposé par la base | Standard GTB | Brick Point, BACnet objects, QUDT/UCUM (unités) | Critique | ADR 012 §2.7 | ADD (F3) | Unité de base de la télémétrie, de l'état réel/souhaité et de la qualité. |
| Qualité des données et score de confiance par point | ✅ Fait (F3-F4) — drapeaux à la réception + score de confiance explicable (figé, périmé, complétude, relevés douteux) ; les règles ne s'y fient pas en dessous du seuil | Outils d'analytique spécialisés (non revérifié) | OPC UA StatusCode, indicateurs d'état BACnet | Haute | ADR 012 §2.8 | ADD (F3 drapeaux, F4 score) | Une donnée douteuse n'est jamais utilisée aveuglément ; les règles le disent explicitement. |
| État souhaité / état réel et détection d'écart | ✅ Fait en lecture seule (F4, console web 24/09/2026) — attentes déclarées avec plage horaire et fuseau depuis la fiche équipement, règle d'écart → constat de mise en service | Jumeaux d'objets connectés des clouds (état souhaité/rapporté) | Tableau de priorités BACnet | Haute | ADR 012 §2.4 : `desired_states` | ADD (F3-F4) pour les attentes déclarées ; DEFER le cycle de commande | Utile dès la lecture seule : détection de gaspillage (« souhaité OFF, réel ON »). |
| FDD (détection et diagnostic de défauts) | ⚠️ Premier maillon (F4, console web 24/09/2026) — règles de seuil et d'écart à la consigne créées, activées, retirées et restaurées depuis la fiche équipement (brouillon → actif → retiré, diff entre versions) ; natures séparées ; diagnostics DEFER. Ordre de travail depuis un constat : automatique si la règle le demande (`create_work_order`, existant) **et**, depuis le 26/09/2026, décidé par une personne à tout moment (`POST /findings/{id}/work-order`, `app/routers/maintenance.py`) — titre, priorité (reprend la gravité) et position pré-remplis depuis le constat, jamais générés puis stockés comme une nouvelle vérité : ce sont des champs libres modifiables ensuite, comme pour tout ordre de travail. **01/10/2026 : premier type de règle AFDD au sens strict** — `simultaneous_heating_cooling` (`CorrelationRule`, `app/rules.py`) : chauffage et refroidissement actifs au même instant sur le même équipement, comparaison déterministe entre deux points (vanne chaude, vanne froide), jamais un seul point comme `threshold`/`desired_state_divergence`. Vérifié dans la littérature FDD du secteur (Honeywell, Siemens, Johnson Controls le proposent tous ; imposé par Title 24 en Californie sur les économiseurs) et distinct de la maintenance prédictive ML (ligne suivante) : une comparaison physique immédiate, jamais un historique entraîné ni une projection. Réutilise `latest_usable_bulk` (`app/equipment_status.py`, quatrième réemploi) pour la valeur actuelle du point qui n'a pas été mesuré, avec la même garde de péremption que la télémétrie — jamais une simultanéité supposée si le second point n'a pas de relevé assez récent. Deux nouvelles classes de points (`heating_valve_position`, `cooling_valve_position`, `app/point_vocabulary.py`) : cas réel, pas « au cas où ». **Correction du 02/10/2026** : la ligne « Web absent » ci-dessous était erronée — le formulaire de création (choix des deux points, seuils, gravité) existe depuis le 01/10/2026 (`CorrelationRuleBlock`, `createCorrelationRule`, `apps/web/src/app/registre/[id]/`), simplement jamais remonté dans ce document. **01/10/2026 (suite) : économiseur bloqué couvert sans nouveau moteur de règle** — réutilise `DivergenceRule`/`desired_state_divergence` déjà existante : un volet d'air neuf qui ne suit pas l'état souhaité déclaré (`app/desired_states.py`) ouvre déjà un constat de mise en service. Ajouts : classe de point `economizer_damper_position` (`app/point_vocabulary.py`), point et scénario de panne `economiseur_bloque` au Virtual Commissioning Lab (`app/connectors/virtual_telemetry.py`), palier FAILURE_TESTED prouvé par `tests/test_virtual_telemetry_failure_scenarios.py` (constat `commissioning`, `RULE_DESIRED_STATE_DIVERGENCE`, contrôle négatif sur la modulation saine). **01/10/2026 (suite) : cycles courts** — troisième type de règle (`ShortCyclingRule`, `kind="short_cycling"`), premier qui porte sur un historique de mesures plutôt que sur l'instant présent seul : trop de démarrages (transition arrêt → marche d'un point `run_status` booléen) sur une fenêtre de temps glissante (`max_starts`/`window_minutes`). Déterministe (compte des transitions, jamais de statistique ni de modèle entraîné) ; l'état avant le début de la fenêtre sert d'amorce pour ne jamais compter comme un démarrage un équipement déjà en marche avant la fenêtre ; évalué à chaque relevé (marche ou arrêt) pour que le constat reste actif tant que la fenêtre contient trop de démarrages, au lieu d'apparaître puis disparaître à chaque arrêt. Validé par 7 tests contre une vraie base (`tests/test_rules_short_cycling.py`) : trop de démarrages déclenche le constat, en dessous de la limite rien, les relevés « marche » répétés sans arrêt ne comptent que pour un seul démarrage, les démarrages hors fenêtre ne comptent pas, le constat revient à la normale une fois les anciens démarrages sortis de la fenêtre, la validation refuse un point non booléen, isolation entre clients. Pas encore de scénario dédié dans le Virtual Commissioning Lab (nécessiterait un mécanisme d'oscillation marche/arrêt absent du simulateur actuel, contrairement à l'économiseur bloqué qui réutilisait un mécanisme déjà là) — DEFER, non bloquant : la rigueur de preuve contre une vraie base (insertion réelle, vraie transaction, vrai moteur de règle) est équivalente | Johnson Controls OpenBlue (revérifié 26/09/2026 : détection 24/7, priorisation avant l'alarme, création d'ordre de travail manuelle et automatisée depuis un défaut) ; Honeywell Forge, Siemens (AFDD confirmé le 01/10/2026 pour les règles standards du secteur — simultanéité chauffage/froid, économiseur bloqué, cycles courts — non revérifié ligne à ligne pour le reste) | ASHRAE Guideline 36 (règles AFDD des CTA, issues des règles APAR du NIST ; protection moteur/compresseur contre les cycles courts) ; Title 24 (Californie, AFDD obligatoire sur économiseur) | Haute | ADR 012 §2.15 : `findings`, `diagnoses`, `recommendations` ; `app/findings.py` (`link_finding`) ; `app/rules.py` (`CorrelationRule`, `DivergenceRule`, `ShortCyclingRule`) | ADD règles déterministes (F4) + console web ; ADD ordre de travail décidé par une personne (26/09/2026) ; ADD première règle à deux points (01/10/2026) ; ADD économiseur bloqué (01/10/2026, réutilise `DivergenceRule`) ; ADD cycles courts (01/10/2026, nouveau type de règle, premier sur historique) ; DEFER statistiques, modèles physiques, ML ; DEFER scénario Virtual Commissioning Lab pour les cycles courts (mécanisme d'oscillation à construire, non bloquant) | Anomalie ≠ défaut ≠ diagnostic ≠ prédiction : natures séparées. Un LLM peut expliquer, jamais décider seul. Contrairement à OpenBlue, aucune escalade automatique vers un ordre de travail sans que la règle l'ait explicitement demandée : la création reste un choix, automatisé ou humain, jamais une conséquence implicite d'une alarme. **Grille produit (ADR 014)**, pour la règle à deux points : Backend DONE, API DONE (créable via `POST /configs`), Web DONE (formulaire de création existant, voir correction du 02/10/2026 ci-dessus), Mobile N/A, Edge N/A, Tests DONE (7 tests : simultanéité détectée, un seul circuit ouvert sans effet, contrepartie périmée sans faux positif, retour à la normale, les trois validations — points identiques, équipement différent, point non numérique), Documentation DONE. |
| Mise en service et recommissioning continu | ⚠️ **02/10/2026 : correction** — « moteur de découverte DEFER (M3) » était périmé : le moteur de découverte et correspondance sémantique existe depuis le 27/09/2026 pour BACnet (voir ligne « Découverte automatique et correspondance sémantique » ci-dessous, ✅ Fait), jamais reporté ici. État réel — modèle posé (F3-F4) : points proposés → validés, écarts à l'attendu en constats « commissioning » ; moteur de découverte fait pour BACnet (lecture seule), DEFER seulement pour Modbus/OPC UA/MQTT (aucun catalogue de registres à deviner pour ces protocoles, le besoin ne s'est pas présenté) | Outils spécialisés de mise en service continue (non revérifié) | ASHRAE Guideline 0 / 1.1 | Haute | ADR 012 §2.15 : statuts de mapping, attentes, constats `commissioning` ; `app/connectors/bacnet_semantics.py` | ADD le modèle (F3-F4) ; ADD le moteur pour BACnet (27/09/2026, correction de cette ligne le 02/10/2026) ; DEFER son extension à Modbus/OPC UA/MQTT (aucun besoin réel) | Un équipement connecté n'est jamais considéré comme bien configuré par défaut. |
| Maintenance prédictive / ML | ⚠️ **02/10/2026 : correction de statut (décision de Mohamed)** — n'est plus `BLOCKED` dans son ensemble. Seule l'annonce d'une performance réelle reste `DEFERRED_PHYSICAL_VALIDATION` (terme choisi par Mohamed, équivalent à `FIELD_TESTED: BLOCKED_EXTERNAL`, ADR 017) : un historique réel de mesures et de pannes/interventions, couvrant plusieurs cycles, sur au moins une installation réelle — condition inchangée. Tout le reste avance dès maintenant : pipeline logiciel complet et validation en simulation, exactement comme pour les quatre autres statuts déjà en cours pour cette ligne (`IMPLEMENTED`, `UNIT_TESTED`, `SIMULATOR_TESTED`, `INTEGRATION_TESTED`). Premier incrément (02/10/2026) : `TrendProjectionRule` (`app/rules.py`) — projection linéaire déterministe d'un point numérique sur son historique récent, constat de nature `prediction` (`method="statistical"`, jamais `"ml"` : aucun modèle entraîné, une extrapolation explicable) si la tendance atteindrait un seuil dans l'horizon donné ; jamais déclenchée si le seuil est déjà franchi (ce cas relève de `ThresholdRule`, pas d'une prédiction). Certitude et confiance jamais à 1,0 comme les règles déterministes instantanées (`evaluate_after_measurement` distingue désormais `kind == "prediction"`) : une projection reste une extrapolation, jamais un fait constaté. `UNIT_TESTED` : 9 tests contre une vraie base (`tests/test_rules_trend_projection.py`) — tendance montante vers un seuil haut, descendante vers un seuil bas, valeur stable sans effet, tendance qui s'éloigne du seuil sans effet, projection au-delà de l'horizon sans effet, seuil déjà franchi jamais traité comme une prédiction, un seul point dans la fenêtre sans effet (jamais une pente inventée), validation qui refuse un point non numérique, isolation entre tenants. `FAILURE_TESTED` : 2 tests contre le scénario de dérive déjà existant du Virtual Commissioning Lab (`capteur_derive`, `app/connectors/virtual_telemetry.py`, dérive linéaire de 4°C/heure déjà simulée, `tests/test_virtual_telemetry_failure_scenarios.py`) — la dérive déclenche réellement une prédiction avec `certainty="prediction"` et `confidence=None`, la télémétrie saine n'en déclenche aucune — aucun nouveau mécanisme de simulation, seulement une règle de plus qui lit la même télémétrie | MaintForge, Honeywell Forge, Siemens | — | Haute (développement) ; `DEFERRED_PHYSICAL_VALIDATION` pour l'annonce de performance réelle | Constats de nature `prediction` ; `app/rules.py` (`TrendProjectionRule`) | ADD pipeline logiciel + première règle de projection (02/10/2026, décision de Mohamed) ; `DEFERRED_PHYSICAL_VALIDATION` conservé uniquement pour la validation sur historique réel | Sans données réelles de plusieurs cycles, une performance réelle resterait invérifiable — mais le pipeline, lui, n'a besoin que de télémétrie, réelle ou simulée, pour être construit et prouvé en simulation (ADR 017 §5). |
| Affichage temps réel sur plan | ✅ Fait — `GET /floor-plans/{id}/placements/live` : pour chaque placement **validé** ciblant un point, renvoie sa dernière valeur mesurée, son type, son unité, ses états nommés et son score de confiance (réutilise `app/trust.py` et `app/monitoring.py`, comme `GET /points/{id}/trust`) ; un placement encore proposé n'est jamais montré comme confirmé. Aucun agrégat d'occupation calculé (pas encore de besoin réel). Superposition visuelle (console web, `/registre/plans/{id}`) : infobulle au survol (texte complet, statut et constat inclus) ; mise en évidence par constat ouvert (27/09/2026) — un repère dont le point porte un constat ouvert ou en cours (`GET /findings`, même règle de sujet que `app/rules.py::_subject`) reçoit un anneau rouge sur le plan et une mention dans la liste. **01/10/2026 : étiquette de valeur affichée en permanence** à côté du repère (`PlacementEditor.tsx`), plus seulement au survol — pure superposition visuelle, aucun ajout côté API | Standard dans les GTB ; Siemens Building X Lifecycle Twin (revérifié 26/09/2026 : mise en surbrillance dynamique d'un espace ou d'un équipement sur le plan selon son état ou un défaut actif) | — | Haute, après les points | ADR 011 + points (F3) ; `apps/web/src/app/registre/plans/[floorPlanId]/` | ADD (API 26/09/2026, infobulle web 26/09/2026) ; ADD mise en évidence par constat ouvert (27/09/2026) ; ADD étiquette de valeur permanente (01/10/2026) | Occupation uniquement agrégée le jour où elle sera nécessaire (vie privée) — pour l'instant, seules des valeurs de points techniques (température, marche/arrêt…) sont montrées, jamais une présence humaine. |

### Edge, connecteurs, commande

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Connecteurs protocoles terrain (BACnet, Modbus, OPC UA, MQTT) | ⚠️ Modbus, BACnet et OPC UA faits (25/09/2026, 27/09/2026) — trois adaptateurs génériques indépendants du fabricant (`app/connectors/modbus.py`, `app/connectors/bacnet.py`, `app/connectors/opcua.py`), lecture seule (Modbus : function codes 03/04 ; BACnet : ReadProperty ; OPC UA : service Read (`Node.read_value`) — aucun des trois n'a de fonction d'écriture dans ce dépôt). Modbus : carte de registres d'un appareil donnée en paramètre (SDM120 fournie comme donnée, pas comme logique). BACnet et OPC UA : aucun catalogue nécessaire, le protocole normalise déjà l'adressage (BACnet : type d'objet + instance + propriété ; OPC UA : NodeId, ex. `ns=2;i=1001`) — la carte de points est directement le contenu de la configuration (`bacnet_device_mapping`, `opcua_device_mapping`). Bibliothèques BACnet (`bacpypes3`) et OPC UA (`asyncua`, LGPL-3.0, v2.0.1, pure Python, client **et** serveur — le serveur sert de simulateur dans les tests) asynchrones : même pont synchrone par `asyncio.run` à chaque relève que Modbus, pour rester appelable depuis le même modèle de démon sans le réécrire en async. Démon dédié (`scripts/opcua_daemon.py`, même modèle que `scripts/bacnet_daemon.py`), endpoint `GET /edge/config/opcua`. Connexions Modbus/BACnet persistées et pilotables depuis la console web (config versionnée) ; OPC UA géré par API/CLI pour l'instant, pas encore de section dédiée dans la console web (aucun besoin réel exprimé). Les trois validés contre des simulateurs logiciels uniquement, jamais contre un appareil réel. **02/10/2026 : quatrième protocole, MQTT** (`app/connectors/mqtt.py`) — contrairement aux trois autres, publication/abonnement plutôt que requête/réponse : le connecteur se connecte au courtier, s'abonne à chaque sujet, attend ce qui est retenu (« retained ») ou publié dans le délai, puis se déconnecte, pour rester compatible avec le même rythme de relève périodique que les trois autres (jamais de connexion permanente ni de boucle événementielle séparée). Aucun catalogue de registres nécessaire (comme BACnet et OPC UA) : la carte de points est directement le sujet MQTT où chaque valeur est publiée (`mqtt_device_mapping`). Bibliothèque `paho-mqtt` (zéro dépendance transitive, client de référence du protocole). Démon dédié (`scripts/mqtt_daemon.py`, même modèle que les trois autres), endpoint `GET /edge/config/mqtt`, géré par API/CLI comme OPC UA (aucun besoin réel exprimé pour un écran web dédié). Validé contre un vrai courtier MQTT (mosquitto, sous-processus dans les tests — jamais un simulacre Python) : connecteur (5 tests), configuration de relève (9 tests), démon de bout en bout (6 tests, y compris plusieurs points du même appareil et un courtier injoignable qui n'arrête pas la boucle). Courtier ajouté à `infra/docker-compose.yml` (développement local hors ligne) et à la CI (`mosquitto` installé avant les tests). Les quatre protocoles validés contre des simulateurs/courtiers logiciels uniquement, jamais contre un appareil réel. Découverte BACnet V1 (27/09/2026, lecture seule) : ✅ Fait — diffusion Who-Is/I-Am unicast vers une adresse donnée (`discover_device`), puis inventaire des objets « point » par ReadProperty (`read_device_objects`) ; voir ADR 015 et la ligne dédiée « Découverte automatique et correspondance sémantique » ci-dessous. Exécution par l'Edge (30/09/2026, ADR 015 révisée) : un appareil BACnet/IP vit sur le réseau du site, injoignable depuis l'API hébergée — `POST /bacnet-discovery/scan` ne fait plus qu'une demande (lot 'processing', sans réseau), un agent Edge dédié (`scripts/bacnet_discovery_agent.py`, portée d'appareil `discovery:execute`) récupère les scans en attente (`GET /edge/bacnet-discovery/pending`) et rapporte le résultat ou l'échec (`POST .../result`, `POST .../failure`), sans rupture du contrat déjà affiché côté personne (un lot naissait déjà en 'processing'). Connexion BACnet de relève (`bacnet_device_mapping`) désormais aussi configurable depuis la console web (30/09/2026), fermant la boucle découverte → relève sans API/CLI. BACnet Lab enrichi de six profils d'équipement (CTA, groupe froid, groupe électrogène, VRV/DRV, sous-station thermique, comptage). Outil de comparaison terrain (GTB ↔ découverte ↔ sémantique) prêt (`app/bacnet_field_comparison.py`, `scripts/bacnet_field_comparison.py`). Future écriture/commande BACnet spécifiée sans être activée (ADR 016). `UNIT_TESTED` (devineur sémantique, outil de comparaison, aucun réseau) et `SIMULATOR_TESTED` (BACnet Lab : vrai appareil `bacpypes3` en boucle locale, connecteur/domaine/API/agent Edge/six profils) ; validation sur un vrai appareil BACnet, sur un vrai réseau : **`FIELD_TESTED` : `BLOCKED_EXTERNAL`** (ADR 017 — adressage, diffusion et pare-feu réels ne se simulent pas de façon fiable, contrairement à la lecture de points déjà validée ; ce blocage ne retarde plus aucune autre capacité de la roadmap). **Grille produit (ADR 014)** : Backend DONE, API DONE, Web DONE pour BACnet (découverte, propositions et connexion de relève, toutes trois pilotables depuis la fiche équipement) ; PARTIAL pour l'ensemble de la ligne (OPC UA et MQTT API/CLI seulement — pas d'écran dédié, aucun besoin réel exprimé), Mobile N/A (configuration Edge, pas un usage terrain), Edge DONE (agent de relève et, depuis le 30/09/2026, agent de découverte — les deux seuls processus qui dialoguent réellement en BACnet), Tests DONE, Documentation DONE (ADR 015, ADR 016) | Cœur des grands éditeurs ; Smart & Connective et UBBEE via leurs automates | BACnet (ASHRAE 135), Modbus, OPC UA (IEC 62541), MQTT 5 | Haute | ADR 012 §2.12 : SDK de connecteur ; ADR 015 (découverte BACnet) ; ADR 016 (écriture BACnet, spécifiée non activée) | ADD Modbus (24/09/2026) ; ADD BACnet (25/09/2026) ; ADD OPC UA (27/09/2026) ; ADD découverte BACnet V1 (27/09/2026) ; ADD exécution Edge de la découverte + config web de relève + BACnet Lab enrichi + outil de comparaison terrain (30/09/2026) ; ADD MQTT (02/10/2026) ; DEFER section web dédiée à OPC UA et MQTT (aucun besoin réel encore) ; DEFER écriture BACnet (ADR 016, spécifiée non activée) | Contrat fixé maintenant, un protocole implémenté dessus ; écriture absente du code, pas seulement désactivée. |
| Découverte automatique et correspondance sémantique (auto-mapping) des points | ✅ Fait (BACnet V1, 27/09/2026, lecture seule) — pipeline BACnet Point → devineur sémantique (`app/connectors/bacnet_semantics.py`, unité BACnet ou mot-clé du nom → classe `point_class` proposée, confiance, code de raison stable) → proposition (`bacnet_discovery_proposals`, statut `proposed`/`accepted`/`rejected`/`duplicate`) → validation par une personne → point réel (`app/points.py::create_point`, même chemin que la saisie manuelle) → Digital Twin. Jamais de correspondance inventée : sans unité ni mot-clé reconnu, la proposition reste `point_class=None` avec le code `NO_RELIABLE_SIGNAL` (ou `MULTISTATE_NOT_YET_MAPPED` pour un mode multi-état, la « règle des trois » n'ayant encore aucune classe multi-état générique) ; raison toujours traduite (`reason_message`, catalogue `shared/i18n/*/bacnet_discovery.json`, jamais une phrase stockée). Une nouvelle relève sur le même équipement/adresse marque les objets déjà acceptés `duplicate` au lieu de reproposer un doublon. Provenance conservée (`mapping_confidence` sur le point créé). **Grille produit (ADR 014)** : Backend DONE, API DONE (`/bacnet-discovery/*`, `/edge/bacnet-discovery/*`), Web DONE (propositions, correction de la classe/unité avant acceptation, refus avec motif obligatoire, depuis la fiche équipement), Mobile N/A, Edge DONE depuis le 30/09/2026 (l'agent de découverte exécute réellement le dialogue BACnet ; seule la correspondance sémantique elle-même reste un calcul serveur, sans réseau), Tests DONE (UNIT_TESTED + SIMULATOR_TESTED, y compris isolation des tenants et agent Edge), Documentation DONE (ADR 015) | Auto-discovery/auto-tagging annoncé par plusieurs éditeurs GTB, rarement avec un niveau de confiance explicite ou un état « à revoir » assumé | Brick Schema (classes de points), aucun standard normalisant la méthode de correspondance elle-même | Haute | ADR 012 §2.7 (vocabulaire des points) ; ADR 015 | ADD (27/09/2026) ; ADD exécution Edge de la découverte (30/09/2026) | Base réutilisable pour tout futur protocole (Modbus, OPC UA, MQTT) : le devineur ne connaît que des métadonnées génériques (unité, nom), jamais `bacpypes3`. |
| Certification des connecteurs (Experimental → Verified → Certified) | ❌ Absent | Programmes de certification des protocoles | BTL (BACnet), certification OPC Foundation | Moyenne | ADR 012 §2.12 | DEFER (M3) | Aucun connecteur tiers n'obtient automatiquement de droit de commande. |
| Edge runtime (tampon hors ligne, envoi différé) | ✅ Démon parle par HTTP, plus d'accès direct base (24/09/2026, `app/connectors/edge_client.py`) — le démon Modbus s'authentifie avec sa propre identité d'appareil et n'utilise plus jamais les identifiants de l'API : `GET /edge/config` pour la configuration, `POST /edge/measurements` pour la télémétrie. Tampon hors ligne (`app/connectors/offline_buffer.py`) : fichier local, une mesure déjà lue n'est jamais perdue si l'API est injoignable, renvoi automatique dès la reprise. Démon mono-processus : pas de flotte, pas de PKI, pas encore un vrai agent Edge déployable | Passerelles matures chez Schneider/Siemens ; automates Smart & Connective | MQTT 5 (sessions persistantes, QoS 1) | Haute | Agent Edge ; ingestion idempotente (F3) | ADD frontière HTTP + tampon fichier (24/09/2026) ; DEFER flotte/PKI/MQTT (M4+) | Lien Edge ↔ cloud à concevoir bidirectionnel dès M3 (ADR 012, risque 4). La frontière réseau que la PKI protégera existe maintenant : plus seulement une base de données partagée. |
| Gestion de flotte Edge (mises à jour signées, déploiement progressif, retour arrière) | ❌ Absent | Plateformes IoT des grands clouds (non revérifié) | TUF / Uptane (mises à jour sécurisées) | Moyenne | `config_versions` + identité des appareils | DEFER (M4) | Conçue pour une grande flotte, pas pour 10 passerelles. |
| Commande distante sécurisée | ⚠️ Partiel (incrément 4 fait, 1er octobre 2026) — interdite vers un équipement réel par la règle non négociable 1, inchangée. `IMPLEMENTED`, `SHADOW_TESTED` : interface `CommandExecutor` (`app/connectors/executors.py`, ADR 017 §4.1) — `SimulatedExecutor` nommé explicitement, `resolve_executor(device_type)` remplace le branchement implicite qu'avait `scripts/modbus_daemon.py` (REFACTOR de seam, aucune nouvelle logique métier : `app/commands.py` inchangé, `tests/test_modbus_daemon_commands.py` — la preuve de bout en bout Decision → Authorization → Policy & Safety → Simulated Command → Audit → Simulated Verification — toujours au vert sans modification). 4 nouveaux tests contre un vrai relais Modbus simulé (écriture/relecture réelles, code d'échec stable `MODBUS_WRITE_ERROR` si injoignable, jamais une phrase en dur dans la donnée persistée). Toujours un seul `device_type` commandable (`simulated_relay`) : l'ajout d'un futur exécuteur réel (BACnet ou Modbus) sera une entrée de table, jamais une nouvelle branche de code, et reste couvert par l'ADR 016 (validation terrain + décision explicite séparée). **02/10/2026 : précision de Mohamed** — aucun LIVE CONTROL avant la fin de V4, décision déjà fixée pour toute la durée de la roadmap, pas une question en attente d'un feu vert à chaque audit : Shadow/Dry Run continue de se développer et se prouver sans qu'il y ait quoi que ce soit à redemander | Honeywell Forge, Johnson Controls OpenBlue, Schneider EcoStruxure | IEC 62443 | Haute pour le Shadow Mode ; aucun LIVE CONTROL avant la fin de V4 (décision fixée, pas en attente) | ADR 012 §2.5-2.6 ; ADR 016 (BACnet) ; ADR 017 §4 ; `app/connectors/executors.py` | ADD Shadow Mode (incrément 4 fait, ADR 017) ; DEFER toute commande réelle jusqu'à la fin de V4 (décision fixée le 02/10/2026) | Chaîne Identity → Authorization → Policy → Safety → Arbitration → Edge → Controller → Verification ; sécurités locales toujours prioritaires. `SimulatedExecutor` remplaçable plus tard par un exécuteur réel sans changer le moteur métier ni la boucle du démon. |
| Arbitrage des commandes (priorités, dérogations temporaires, expiration) | ❌ Absent | Natif dans BACnet et les GTB | Tableau de priorités BACnet (16 niveaux) | Aucun LIVE CONTROL avant la fin de V4 (décision fixée, pas en attente) | ADR 012 §2.5 ; ADR 016 (spécification de la future écriture BACnet, non activée) | DEFER, conçu | Arbitrage déterministe exécuté sur l'Edge pour fonctionner sans Internet ; anti-boucle par chaîne de causalité. |
| Moteur d'automatisation / GTB native | ❌ Absent | Cœur des grands éditeurs et de Smart & Connective | — | Postérieure à la sûreté | ADR 004 | DEFER | Aucun LIVE CONTROL avant la fin de V4 (décision fixée le 02/10/2026, pas une question en attente d'un feu vert). |
| Retrofit léger (GTB non supposée, monitoring sans contrôle) | ✅ Principe respecté — registre et GMAO utilisables sans aucune connexion | Smart & Connective (GTB Light sans travaux) | LoRaWAN, EnOcean, Zigbee (capteurs sans fil de retrofit) | Haute | Profils d'intégration par site | KEEP + DEFER profils (M3) | Le client peut commencer par la maintenance seule, puis ajouter des capteurs. |

### Validation virtuelle (Virtual Commissioning Lab, Replay Mode — ADR 017, 1er octobre 2026)

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Virtual Commissioning Lab (sites, bâtiments, équipements et télémétrie simulés, scénarios de panne, règles FDD multi-points, commandes DRY_RUN/SHADOW) | ✅ **02/10/2026 : câblage complet (demande explicite de Mohamed)** — `IMPLEMENTED`, `UNIT_TESTED`, `SIMULATOR_TESTED`, `FAILURE_TESTED`, `INTEGRATION_TESTED`. **Sept profils** (`app/connectors/virtual_telemetry.py`) : les six existants (CTA, groupe froid, groupe électrogène, VRV/DRV, sous-station thermique, comptage) plus un septième, **pompe** — uniquement des classes de points déjà existantes (run_status, fault_status, pressure_sensor, electric_power_sensor), aucun ajout à `app/point_vocabulary.py`. **Neuf scénarios de panne** nommés (contre quatre, tous CTA, avant ce jour) : `vanne_bloquee`/`chauffage_froid_simultane`/`economiseur_bloque`/`capteur_derive` (CTA, inchangés), `surchauffe_retour`/`derive_echangeur` (groupe froid), `cavitation`/`derive_puissance` (pompe), `releve_incoherent` (comptage, **valeur incohérente** — une puissance négative, immédiatement impossible, distincte d'une dérive progressive, qualifiée dès la réception par `app.quality_flags`, jamais évaluée par une règle) ; `perte_communication` reste générique à tout profil (stale/offline). **`scripts/seed_virtual_site.py` câble désormais, pour chaque équipement créé, exactement la même chaîne qu'un équipement réel** (jamais une deuxième donnée seedée en plus de la télémétrie) : règles FDD par défaut par profil (seuil, corrélation à deux points `simultaneous_heating_cooling` — le seul type multi-points du moteur —, divergence à l'état souhaité, projection de tendance ; `short_cycling` volontairement absent, DEFER déjà documenté, aucun mécanisme d'oscillation dans le simulateur, non bloquant), un état souhaité sur le volet d'air neuf de chaque CTA, un point commandable par pompe (`simulated_relay`, strictement Shadow/Dry Run, CLAUDE.md exception scopée à la règle non négociable 1), une relation `dependsOn` entre une pompe et le groupe froid qu'elle dessert (alimente l'analyse d'impact, `GET /graph/nodes/{id}/impact`, de données réalistes). Alarmes, chronologie et ordres de travail ne sont jamais seedés séparément : effets automatiques déjà câblés (`app.rules._escalate`) ou vues pures, visibles dès qu'un scénario de panne est joué par le démon. Énergie : le profil comptage utilise déjà `energy_meter_reading`, le même point_class que `app/energy/` consomme pour tout compteur réel ou virtuel — aucune adaptation nécessaire (moteur générique par classe de point, jamais par origine de la donnée) ; pas de test dédié supplémentaire au-delà de ceux déjà existants pour le moteur énergétique (`tests/test_energy.py`), qui couvrent déjà le même code indépendamment de la source. Idempotent de bout en bout (règles, état souhaité, point commandable, relation), prouvé par un nouveau test qui exécute `seed()` deux fois de suite et vérifie l'absence de doublon (`tests/test_seed_virtual_site.py`, 1 test — premier test qui exerce directement le script de seed, jusqu'ici seul le générateur pur était testé). 9 tests supplémentaires sur les nouveaux scénarios (`tests/test_virtual_telemetry.py`, 39 tests au total pour ce module) | Outils de mise en service continue avec simulateurs intégrés (acteurs non vérifiés) | — | Haute (découple la roadmap du matériel terrain) | ADR 017 §2 ; `app/connectors/virtual_telemetry.py` ; `scripts/seed_virtual_site.py` ; `scripts/virtual_commissioning_daemon.py` ; réutilise `app/assets.py`, `app/spatial.py`, `app/points.py`, `app/devices.py`, `app/connectors/edge_client.py`, `app/rules.py`, `app/desired_states.py`, `app/graph.py`, `app/connectors/device_mapping.py` | ADD profil pompe + cinq scénarios + câblage règles/état souhaité/relais commandable/relation dependsOn (02/10/2026, décision de Mohamed) ; DEFER `short_cycling` dans le simulateur (mécanisme d'oscillation à construire, non bloquant, déjà documenté) ; DEFER le démon multi-équipement en un seul processus (un processus par équipement reste cohérent avec Modbus/BACnet/OPC UA/MQTT — aucune flotte à ce stade, lancer plusieurs processus suffit à simuler un site complet) | Zéro nouvelle plateforme parallèle : un actif virtuel traverse exactement le même pipeline qu'un actif réel, y compris pour une panne, une règle FDD, une commande ou une analyse d'impact — jamais un deuxième moteur, jamais un deuxième chemin d'ingestion, jamais une donnée inventée au-delà de la télémétrie elle-même. |
| Replay Mode (rejeu d'exports GTB réels anonymisés : CSV, tendances, alarmes, historiques) | ✅ Incrément 3 fait (1er octobre 2026) — `IMPLEMENTED`, `UNIT_TESTED`, `INTEGRATION_TESTED` : `app/replay_import.py` (traduction pure d'un export CSV au format large vers des relevés individuels, garde anti-donnée-personnelle sur l'en-tête et un échantillon de valeurs — en-têtes suspects type « nom »/« e-mail »/« téléphone », cellules ressemblant à un e-mail ou un numéro complet ; 13 tests), `scripts/replay_import.py` (résout les points déjà enregistrés — Replay Mode n'invente jamais un point — et appelle `app.telemetry.record_measurement`, exactement le chemin d'une mesure en direct ; `--dry-run` pour valider le mapping sans écrire). 3 tests d'intégration prouvent qu'un export rejoué déclenche réellement la règle FDD `simultaneous_heating_cooling`, qu'un point absent du registre est refusé plutôt qu'inventé, et que `--dry-run` n'écrit rien. Revérifié par la vraie CLI contre un site virtuel réel (import effectif, refus réel d'un export avec une colonne « Nom technicien »). **Trouvaille documentée, pas un défaut** : un export vieux de plusieurs mois déclenche honnêtement le drapeau « arrivée tardive » déjà existant (`app.telemetry`), ce qui fait chuter la confiance du point sous le seuil requis par les règles FDD (`MIN_TRUST_FOR_RULES`) — l'historique s'enregistre, la détection attend que la confiance se rétablisse ; même protection qu'un capteur réel arrivé en retard, pas une limite propre à Replay Mode | Outils d'analytique spécialisés qui rejouent des historiques BMS (non revérifié) | — | Moyenne, utile dès qu'un premier export anonymisé est fourni | ADR 017 §3 ; `app/replay_import.py` ; `scripts/replay_import.py` ; réutilise `app.telemetry.record_measurement`, `app.points`, `app.trust` | ADD (incrément 3 fait, ADR 017) | Permet de valider le moteur FDD/alertes sur de vraies dynamiques de bâtiment avant tout accès terrain live, sans jamais exposer de donnée personnelle (règle non négociable 9) — et sans jamais laisser une règle se fier à une donnée arrivée tard, réelle ou rejouée. |

### Configuration, exploitation de la plateforme

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Configuration versionnée (version, auteur, raison, diff, retour arrière) | ✅ Fait (F4) — générique, raison obligatoire, une seule version active garantie par la base, retour arrière = nouvelle version | Variable | — | Haute | ADR 012 §2.11 : `config_versions` générique | ADD (F4) | Un seul mécanisme pour 12 types de configuration ; la première règle de seuil en sera la première utilisatrice. |
| Gestion des changements (brouillon → validation → approbation → déploiement → retour arrière) | ⚠️ Partiel — brouillon → actif → remplacé/retiré → restauré, avec diff entre versions, exposés depuis la fiche équipement (F4, console web 24/09/2026). Approbation à deux (27/09/2026) : `register_config_type(..., requires_second_person=True)` — celui qui active ne peut jamais être celui qui a proposé, uniquement pour les types de configuration qui peuvent déclencher une action (aujourd'hui : les règles d'alarme, seules à pouvoir créer un ordre de travail). Un mapping Modbus/BACnet ou un paramètre énergétique reste à une seule personne : pas d'impact physique direct, pas de friction inutile pour un client avec un seul compte de gestion. Le retour arrière (`restore_version`) reste une action décisive d'une seule personne : le contenu restauré était déjà actif et validé, ce n'est pas un changement nouveau à faire réviser. Simulation préalable (27/09/2026) : `GET /configs/{id}/simulate`, pour une règle de seuil ou d'écart à la consigne (`alarm_rule`) en brouillon ou déjà active — combien de mesures récentes du point auraient enfreint cette règle, sans rien créer (aucun constat, aucune alarme, aucun ordre de travail). **01/10/2026 : bouton « Simuler » côté web** — lien sur chaque version de règle (`RulesBlock` et `CorrelationRuleBlock`, `apps/web/src/app/registre/[id]/page.tsx`), affichant le nombre de mesures en infraction sur l'échantillon récent ; pure lecture, aucun nouvel appel côté serveur que `GET /configs/{id}/simulate` déjà existant. **Grille produit (ADR 014)** : Backend DONE, API DONE, Web DONE (01/10/2026), Mobile N/A, Edge N/A, Tests DONE, Documentation DONE. Réutilise `_evaluate()` tel quel, jamais de nouvelle logique de règle. Déploiement progressif : toujours DEFER (pas de sens pour une configuration à une seule version active) | Variable | — | Moyenne | `app/config_versions.py` (`_requires_second_person`), `app/rules.py` (`simulate_rule`) | ADD statuts minimaux (F4) + console web ; ADD approbation à deux (27/09/2026) ; ADD simulation préalable (27/09/2026) ; ADD bouton web (01/10/2026) ; DEFER déploiement progressif | Indispensable avant toute automatisation à impact physique — mais seulement là où il y a un impact physique, pour rester utilisable par une petite équipe. |
| Observabilité (logs structurés, métriques, traces, fraîcheur) | ⚠️ Partiel — `/health`, `/health/db`, logs JSON avec identifiant de requête et tenant, sans donnée personnelle (F6) ; métriques minimales ajoutées (27/09/2026) : `GET /metrics`, format Prometheus (`app/metrics.py`, bibliothèque `prometheus_client`) — requêtes comptées par méthode/route/statut et leur durée, agrégats seulement, jamais de donnée métier ni par tenant, sans authentification (même sensibilité que `/health`). Traces distribuées toujours absentes (OpenTelemetry exigerait un collecteur à héberger, hors périmètre sans décision d'infrastructure). **Grille produit (ADR 014)** : Backend DONE, API DONE, Web N/A (observabilité de la plateforme elle-même, jamais un écran pour l'exploitant d'un tenant — un composant purement interne, voir ADR 014 §1), Mobile N/A, Edge N/A, Tests DONE, Documentation DONE | Plateformes des grands éditeurs | OpenTelemetry (traces) ; format d'exposition Prometheus (texte) pour les métriques | Moyenne | `app/observability.py` (F6), `app/metrics.py` (27/09/2026) ; OpenTelemetry (traces, reste M3+) | KEEP + ADD métriques (27/09/2026) ; DEFER traces (M3, nécessite un collecteur — décision d'infrastructure) | Distinguer équipement, capteur, passerelle, connecteur et cloud en panne grâce aux relations `connectedTo`/`dependsOn` (voir aussi `app/impact_analysis.py`), pour éviter les avalanches d'alarmes. |
| Résilience et modes de défaillance documentés | ✅ Documenté (F6) — `docs/architecture/failure-modes.md`, composant par composant, risques ouverts signalés | — | — | Moyenne | Document vivant (F6), ingestion idempotente (F3) | KEEP + ADD ; DEFER file des messages rejetés (M3) | « Que se passe-t-il si ce composant tombe ? » documenté pour chaque composant. |
| API/connecteurs ouverts pour intégrations tierces | ⚠️ Partiel — API interne, pas encore publique et versionnée | Marketplace de connecteurs chez les grands éditeurs | OpenAPI | Basse | `services/api` | DEFER (marketplace hors périmètre 12 mois) | Pas de changement de cap pour suivre un concurrent. |
| Domain Packs (bâtiment, industrie, énergie, eau…) | ❌ Absent — catégories en texte libre | Offres par verticale des grands éditeurs | — | Basse | Vocabulaires versionnés par pack (F1, F3) | REFACTOR progressif + DEFER le mécanisme | Un pack apporte vocabulaire, règles et tableaux de bord, jamais une copie des moteurs. |

### Énergie, économie, simulation

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Moteur interne de normalisation énergétique (agrégation, degrés-jours, référence, comparaison) | ✅ Fait (M5, 24/09/2026, directive de Mohamed) — `app/energy/` : agrégation d'un compteur cumulatif (delta, jamais une somme, détection de remise à zéro), contexte météo quotidien saisi manuellement, référence énergétique versionnée (`config_versions`, config_type `energy_baseline`), normalisation par degrés-jours (`degree_day_ratio/v1`, méthode nommée et versionnée), comparaison pure entre deux résultats. Chaque résultat persisté (`energy_normalized_results`, jamais réécrit) porte sa traçabilité complète : période de référence et analysée, consommation brute et son origine, données météo utilisées, méthode et version, paramètres, données manquantes, qualité, date et auteur. Endpoints `/energy/*`, section « Performance énergétique » sur la fiche équipement (web) | Aucun éditeur ne documente publiquement une méthode interne aussi traçable ; les grands éditeurs couplent en général leur normalisation à leur propre reporting | Aucun standard imposé — degrés-jours est une pratique reconnue, pas une norme unique | Haute | `app/energy/` (moteur, indépendant de toute réglementation), `app/routers/energy.py` | ADD (M5) | Frontière stricte et non négociable (directive de Mohamed, 24/09/2026) : ce moteur ne connaît ni OPERAT ni BACS ; les couches réglementaires liront ses résultats sans jamais le modifier. **Précision du 02/10/2026** (audit de bout en bout) : ce moteur ne lit pas non plus les interventions — il ne consomme que des compteurs (`energy_meter_reading`) et le contexte météo, qu'ils proviennent d'un équipement réel ou virtuel. Une intervention de maintenance ne déclenche aucun recalcul automatique ici ; les deux restent des consommateurs indépendants de la télémétrie, par choix d'architecture, pas par oubli. |
| Reporting ESG / conformité énergétique (décret tertiaire, BACS, export OPERAT) | ⚠️ **02/10/2026 : politique changée (directive de Mohamed)** — `DEFERRED_DOCUMENT` levé : une absence de compte ou d'API officielle ne bloque plus le modèle de données, le workflow ni l'interface, seul l'appel externe réel est différé (`DEFERRED_EXTERNAL_INTEGRATION`). **OPERAT** : table `operat_declarations` (migration `ada08b67a28c`, une déclaration par site et par année, workflow brouillon → prêt → transmis), `app/regulatory/operat.py` — `export_operat_summary` produit les chiffres à saisir sur le portail ADEME, `record_manual_submission` enregistre qu'une personne l'a fait (aucune transmission automatique simulée), interface `OperatApiAdapter` posée pour une future intégration programmatique (`NotConfiguredOperatApiAdapter`, échoue explicitement). **BACS** : aucun nouveau code nécessaire — audit complet dans `docs/regulatory/02-bacs-gtb.md`, chaque fonction demandée (suivi énergétique, conservation ≥ 5 ans, analyse d'efficacité, interopérabilité, exploitation/inspection) déjà couverte par une brique existante. **02/10/2026 (suite) : API et écran web** — `app/routers/regulatory.py` (créer/lister/lire/modifier une déclaration, passer « prête », enregistrer une transmission manuelle, résumé pour le portail ADEME, liste portefeuille en un seul appel) ; page `/operat` (liste par site, création d'un brouillon) et `/operat/{id}` (formulaire complet, résumé, enregistrement de la transmission, gelée une fois transmise) — tâche de bureau, réservée aux rôles de gestion comme les documents d'équipement, jamais un geste terrain | Smart & Connective et les grands éditeurs | Décret tertiaire (OPERAT, arrêté du 10 avril 2020), articles R175-1 à R175-6 (BACS) | Haute à moyen terme | `app/regulatory/operat.py`, `app/routers/regulatory.py`, migration `ada08b67a28c` ; `apps/web/src/app/operat/` ; `docs/regulatory/01-operat-eco-energie-tertiaire.md`, `docs/regulatory/02-bacs-gtb.md` | ADD modèle + workflow + interface OPERAT (02/10/2026) ; ADD API + écran web (02/10/2026) ; KEEP BACS (aucun écart) ; `DEFERRED_EXTERNAL_INTEGRATION` transmission programmatique OPERAT (aucun identifiant API) | **Grille produit (ADR 014)** : Backend DONE, API DONE (02/10/2026), Web DONE (02/10/2026), Mobile N/A (tâche de bureau annuelle, pas un geste terrain), Edge N/A, Tests DONE (12 tests de domaine : création, conflit site+année, site introuvable, complétude avant « prêt », transitions de statut refusées hors ordre, gel après transmission, quantité négative rejetée, export, adaptateur par défaut qui échoue explicitement, isolation tenant ; 7 tests d'API : workflow complet brouillon→prêt→transmis, rôle technicien refusé, liste portefeuille, isolation tenant ; TypeScript, ESLint et build web propres ; 887 tests backend et 167 tests web au vert sans régression), Documentation DONE (`docs/regulatory/`). Ne jamais déduire un contrat API ou un format CSV réglementaire à partir d'exemples approximatifs ; la plateforme conserve déjà les données utiles à une future preuve BACS (historique, énergie, paramétrages, événements, commandes). |
| Flexibilité énergétique / DER (solaire, batterie, bornes, effacement) | ❌ Absent | Grands éditeurs (non revérifié) | OpenADR, IEEE 2030.5, OCPP (bornes), SunSpec (solaire/batteries) | Basse | Classes d'équipements + points + relations `feeds`/`poweredBy` | DEFER | Le modèle générique suffit à les représenter ; aucun standard imposé au lancement. |
| Économie des actifs (coûts, garantie, remplacement) | ❌ Absent | EAM/GMAO matures | ISO 15686-5 (coût global) | Basse | Clôture structurée (F5) comme prérequis | DEFER | Aide à comparer des stratégies, sans jamais décider à la place du client. |
| Scénarios « what-if » / simulation | ❌ Absent | Grands éditeurs (jumeaux avancés) | EnergyPlus, Modelica | Basse | Espace de scénarios séparé ; origine `simulated`/`estimated` dès F3 | DEFER | Un résultat simulé n'est jamais présenté ni stocké comme une mesure. |
| Intelligence de flotte (analyse multi-sites) | ❌ Absent | Honeywell Forge, Johnson Controls OpenBlue | — | Basse | S'appuie sur RLS et le graphe | DEFER | Dépend d'un volume réel de sites. |

### Langage, codes et internationalisation (ADR 013)

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Référentiel terminologique unique (produit, documentation, API, support) | ✅ `docs/product/glossaire.md` — version 1, validée (23/09/2026, ADR 013 acceptée). Ligne mise à jour le 26/09/2026 : la note « termes à valider » était périmée, le glossaire lui-même l'indique en tête de document | Souvent implicite chez les grands éditeurs ; incohérences fréquentes chez les acteurs de niche | NF EN 13306, ISA-18.2, ISO 55000, IFC, Brick | Haute | ADR 013, étape L1 | ADD (fait) | Un concept = un terme ; condition d'une IA, d'une documentation et d'un support cohérents. |
| Messages et erreurs par codes stables, traduits à l'affichage | ✅ Erreurs de l'API (L2, RFC 9457) et constats (L3 : code de raison + paramètres) ; interfaces en L4 | Codes d'erreur courants chez Siemens, Schneider Electric ; variable ailleurs | RFC 9457 (Problem Details), ICU MessageFormat | Haute | ADR 013, étapes L2-L3 | REFACTOR | Les règles dépendent du code, pas de la phrase ; traduction sans réécriture des données. |
| Internationalisation français / anglais (dates, nombres, pluriels, fuseau du site) | ✅ Fait (L4) — API, web et mobile ; fuseau IANA par site ; autres langues : un fichier de plus | Standard chez les grands éditeurs | Unicode CLDR, BCP 47, IANA tz | Haute | ADR 013, étape L4 | ADD | Coût faible aujourd'hui, élevé après la multiplication des écrans. |
| Taxonomie des signalements (nature, gravité, condition, acquittement, traitement) | ✅ Fait (L3) — quatre gravités définies, condition / acquittement / traitement séparés, retour à la normale automatique | Gestion d'alarmes des GTB (Siemens Desigo CC, Honeywell, Johnson Controls) | ISA-18.2 / IEC 62682 | Haute | ADR 013, étape L3 | REFACTOR | Indispensable pour les alarmes de GTB en M3 (retour à la normale non acquitté). |
| Niveau de certitude des résultats d'analyse | ✅ Fait (L3) — confirmation humaine seulement, jamais pour une prédiction (contraintes en base) | Rarement explicite sur le marché | — | Haute | ADR 013, section 4.4 (L3) | ADD | Ne jamais présenter une hypothèse ou une prédiction comme un fait. |
| État de fonctionnement et état de communication distincts | ✅ Fait (L6) — calculés depuis les points d'état, dernier état connu daté quand hors ligne, actualité jamais supposée. Depuis le 24/09/2026 (`app/monitoring.py`), une transition vers « hors ligne » lue via `GET /functional-locations/{id}/status` devient une vraie alerte acquittable (et se referme au retour en ligne) — plus un simple affichage | Courant en GTB, souvent confondus (« hors ligne » = « arrêté ») | Brick (points d'état) | Moyenne | ADR 013, section 4.5 (L6) | ADD | « Hors ligne » affiche le dernier état connu et sa date, jamais un état supposé. |
| Nomenclature des équipements (type universel, désignation constructeur, alias) | ✅ Fait (L5) — type universel obligatoire, appellation du fabricant conservée, proposition par alias, code d'inventaire client | Bibliothèques d'équipements chez les grands éditeurs | Brick (classes d'équipement) | Moyenne | ADR 013, étape L5 | REFACTOR | Condition de la recherche, des statistiques de flotte et de l'IA. |
| Présentation selon le profil (métier / technique) | ⚠️ Actions calculées par rôle dans le passeport | Vues par profil chez les grands éditeurs | — | Basse | ADR 013 (libellé métier + technique par terme) | KEEP + DEFER | L'information technique n'est jamais retirée, seulement présentée autrement. |
| Cycle de vie des commandes (demandée → envoyée → vérifiée/échouée/non confirmée) | ✅ Implémenté (24/09/2026, `app/commands.py`), strictement limité à un appareil explicitement simulé — exception scopée à la règle non négociable 1 (CLAUDE.md, décision de Mohamed). Jamais un équipement réel, y compris le SDM120. Chaque étape produit un événement persistant (`app/events.py`) ; une commande sans accusé de réception dans le délai devient « timed_out » (état durable, pas un simple survol) et lève une alerte | Chez les éditeurs de GTB, « envoyée » est souvent affiché comme « exécutée » | ISA-18.2 (acquittement distinct) | — | Glossaire, section 8 ; ADR 013, section 4.6 ; CLAUDE.md, exception §1bis | ADD (simulé uniquement) ; DEFER cycle de vie complet (AUTHORIZED/REJECTED/EXPIRED/CANCELLED) et appareil physique | Une commande acceptée par l'API n'est jamais considérée exécutée tant qu'elle n'est pas vérifiée. |
| Modèle État → Événement → Politique → Alerte, incident (préparation) | ✅ Les trois conditions V1 de la directive sont câblées (24/09/2026, directive de Mohamed) — `app/events.py` (journal persistant, séparé de l'audit et des alertes), `app/monitoring.py` (politique simple : la durée minimale avant alerte est déjà intégrée au calcul de l'état lui-même — `STALE_AFTER_INTERVALS`, `UNCONFIRMED_AFTER`). Détectée à la fois par les points de lecture dédiés (`GET /functional-locations/{id}/status`, `GET /commands`, `GET /points/{id}/trust`) **et**, depuis un complément du 24/09/2026, par un balayage périodique indépendant de tout utilisateur connecté (`app/supervision_sweep.py`, `scripts/supervision_sweep.py`) : la supervision fonctionne même si personne ne consulte l'application. **Grille produit (ADR 014)** : Backend DONE, API DONE, Web DONE (**02/10/2026** : `GET /graph/nodes/{id}/impact` consommé — section « Analyse d'impact » sur la fiche équipement, `apps/web/src/app/registre/[id]/page.tsx` — endpoint enrichi avec code/nom pour chaque équipement impacté (`app/impact_analysis.py`, `get_functional_location`), un équipement non résolvable affiche son type traduit plutôt qu'un lien mort ; **même date** : le journal `app/events.py`, jusqu'ici sans aucun consommateur en dehors des tests malgré la mention « API seulement » ci-dessus (écart déjà signalé en commentaire dans `app/timeline.py`), raccordé à la chronologie fusionnée (`app/timeline.py::_events`/`_portfolio_events`, nouveau catalogue `shared/i18n/*/events.json`) — hors ligne/en ligne de l'équipement, donnée périmée/rétablie, cycle de vie d'une commande, visibles sur la fiche équipement et sur le bloc « Activité récente » du tableau de bord, jamais le code brut affiché (titre déjà traduit avec ses paramètres, ADR 013)), Mobile PARTIAL (chronologie de l'écran passeport enrichie des mêmes événements système depuis le 02/10/2026 ; l'analyse d'impact par dependsOn n'a pas d'écran mobile — geste de bureau, pas terrain), Edge N/A, Tests DONE (3 tests API sur l'enrichissement code/nom de l'analyse d'impact ; 2 nouveaux tests sur le raccordement du journal à la chronologie et à l'activité récente portefeuille ; 1 test web sur le non-affichage du code brut d'un événement ; 838 tests backend, 163 tests web et 91 tests mobile au vert sans régression), Documentation DONE. Jamais le passeport, qui reste une vue pure sans effet de bord. Corrélation (27/09/2026) : `GET /graph/nodes/{id}/impact` parcourt le prédicat « dependsOn » (existait dans le vocabulaire depuis F1, jamais utilisé jusqu'ici — même écart que « maintainedBy » avant les prestataires) pour regrouper, sous un nœud en panne, tout ce qui en dépend transitivement et son nombre de constats ouverts : une avalanche d'alarmes qui partage une cause commune devient visible, jamais affirmée automatiquement (une personne vérifie). Pas de nouvelle table ni de nouveau concept stocké : un parcours des relations existantes, comme la chronologie. Un vrai concept « Incident » (avec son propre cycle de vie), politiques par criticité, escalade : non faits | Concept répandu dans l'observabilité IT (Prometheus Alertmanager, PagerDuty), rare tel quel en GTB/GMAO | — | Haute | `app/events.py`, `app/monitoring.py`, `app/supervision_sweep.py`, `app/impact_analysis.py` ; portée long terme : bâtiment/industrie/énergie/eau (directive, point 17) | ADD état→événement→alerte (24/09/2026, hors ligne + commande + donnée périmée) ; ADD balayage périodique (24/09/2026, complément) ; ADD corrélation par dependsOn (27/09/2026) ; ADD raccordement du journal `events` à la chronologie (02/10/2026) ; DEFER concept Incident à part entière/politiques par criticité/escalade | **Décision signalée avant de coder** : pas de nouvelle infrastructure distribuée — `sweep_once()` réutilise exactement les mêmes fonctions de politique que les points de lecture, tenant par tenant, un tenant en échec n'empêchant jamais les suivants. En production (Railway), exécuté via un service Cron Jobs (`--once`), pas un processus permanent de plus ; en local, une boucle (`--interval`) suffit. Une lecture reste par ailleurs sans effet de bord attendu par un utilisateur : le balayage est désormais le mécanisme principal de détection, les points de lecture restant une détection immédiate en complément. |

### Interfaces, Command Center et expérience produit (ADR 014, 27/09/2026)

Voir `docs/spec/command-center-ux-directive.md` pour le texte de référence et l'audit
initial. Les lignes ci-dessous couvrent les briques de la directive qui ne sont pas
déjà traitées dans une ligne existante ci-dessus (vue Portfolio : ligne « Console web
responsable d'exploitation » ; chronologie : ligne « Mémoire opérationnelle » ;
corrélation : ligne « Modèle État → Événement → Politique → Alerte »).

**Directive complémentaire du 30/09/2026** (architecture UI, Global Command Center,
dashboard) : voir `docs/spec/dashboard-ui-directive.md` pour le texte intégral (40
sections) et son propre audit KEEP/REFACTOR/REPLACE/ADD/DEFER. Corrections
immédiates déjà faites (30/09/2026) : composant de logo découplé du nom de marque
(`BrandMark.tsx`, remplace `EnoryxMark.tsx`), rôles techniques jamais affichés bruts
(catalogue `role.*`, web et mobile), sous-titre de la page de connexion neutre (plus
de rôle nommé avant authentification). Global Command Center (section 36, point 1)
commencé : langage d'état universel fait (`StatusBadge` partagé, branché sur la
cellule de statut de la vue Portfolio) ; bloc « Alarmes prioritaires » fait (section
11) — alarmes triées par gravité puis ancienneté (`prioritizeAlarms`, testé), jamais
une liste chronologique brute, limitées à 8 pour éviter la surcharge visuelle
(section 18), chaque ligne cliquable vers la fiche équipement ; bloc « Maintenance »
fait (section 12) — interventions en cours, ordres de travail urgents ouverts,
équipements à pannes répétitives (≥ 2 correctifs, `repeatingFailures`, testé),
dernières clôtures réelles (`GET /interventions`, une intervention dont `ended_at`
est renseigné — jamais déduites du statut de l'ordre de travail). « Interventions en
retard » explicitement non calculé et annoncé comme tel (`maintenance_overdue_
unavailable`) : aucune date d'échéance n'existe aujourd'hui sur un ordre de travail,
jamais une donnée inventée pour remplir une case (section 37). Bloc « Énergie » fait
(section 13) — consommation brute du jour de référence (hier, jour calendaire UTC
complet le plus récent) et tendance vs la veille de ce jour, pour chaque compteur
d'énergie validé (`point_class = energy_meter_reading`, jamais un point encore
proposé), groupée par unité (`summarizeEnergyByUnit`, testé) pour ne jamais additionner
deux unités différentes. Contrairement au bloc « Santé des actifs » (voir ci-dessous),
ceci ne demandait pas de nouvel endpoint bloquant au sens de la section 29 : le nombre
de compteurs d'énergie par tenant reste faible (un par point de comptage physique), et
`aggregate_portfolio_daily_energy` (nouveau, `app/energy/aggregation.py`) fait ses
requêtes en interne sur une connexion déjà ouverte, jamais un appel HTTP par compteur
depuis le navigateur — nouvel endpoint `GET /energy/portfolio-summary` ajouté en
conséquence (additif, non cassant, aucune dépendance nouvelle). N'affiche et ne calcule
jamais : économies, CO2 évité, ROI, conformité, KPI réglementaires (interdit par la
section 13) ; production, batterie et groupe électrogène n'apparaissent pas du tout,
faute de classe de point correspondante aujourd'hui — DEFER, jamais une case
« indisponible » permanente pour une fonctionnalité qui n'existe pas encore dans le
système. La « comparaison à une baseline réelle » listée par la section 13 est aussi
DEFER pour ce bloc : elle existe déjà à la fiche équipement (`app/energy/normalization.py`,
GET /energy/normalized-results`), mais dépend d'une référence énergétique configurée
à la main par équipement — l'intégrer au résumé portefeuille demanderait de déclencher
un calcul de normalisation depuis un simple widget de synthèse, une responsabilité
que ce bloc ne doit pas porter. Bloc « Santé des actifs » fait (section 15) —
répartition Normal/Attention/Critique/Hors ligne/Donnée ancienne/Inconnu/Maintenance
sur tout le portefeuille (équipements non archivés), chaque catégorie cliquable
(`<details>/<summary>`, même motif zéro-JS déjà utilisé pour les sections archivées de
`/registre`) et ouvrant la liste filtrée des équipements concernés, chacun lien direct
vers sa fiche. Ce bloc était bloqué au tour précédent faute d'endpoint de statut groupé
(l'endpoint existant, `GET /functional-locations/{id}/status`, est par équipement — un
appel par équipement depuis le portefeuille n'aurait pas passé à l'échelle, section 29).
Résolu par un vrai calcul en masse, pas un contournement : nouvel endpoint `GET
/functional-locations/status-summary` et `compute_portfolio_equipment_status`
(`app/equipment_status.py`) qui récupère tous les points d'état validés du tenant et
leur dernier relevé exploitable en une poignée de requêtes (`DISTINCT ON`), jamais une
requête par équipement — y compris pour les équipements sans aucun point d'état, comptés
comme « Inconnu » plutôt qu'omis (l'absence d'instrumentation fait partie de la vérité du
portefeuille). `compute_equipment_status` (l'endpoint par équipement existant) a été
refactoré pour partager cette même logique (`_status_from_points`) : comportement
inchangé (12 tests existants toujours verts), mais lui aussi passé d'une requête par
point à une seule requête groupée. Point de sécurité explicite : ce nouveau calcul
portefeuille reste une lecture pure — il n'appelle jamais `evaluate_communication_status`
(qui reste strictement réservé au point de lecture par équipement et au balayage
périodique, `app/supervision_sweep.py`), pour ne jamais transformer un simple
chargement de tableau de bord en générateur d'alertes. Classement des équipements par
catégorie réutilise exactement `equipmentStatusToAssetStatus` déjà écrit pour la cellule
de statut du portefeuille — aucune seconde logique de classement à maintenir en double.
Bloc « Activité récente » fait (section 16) — dernier bloc du Global Command Center.
Réutilise et généralise `app/timeline.py::node_timeline` (déjà construit pour la fiche
équipement, `GET /graph/nodes/{id}/timeline`) : quatre sources déjà unifiées
(interventions, historique des ordres de travail, historique des alarmes, historique des
constats), fusionnées et triées pour tout le portefeuille plutôt qu'un seul équipement,
via un nouvel endpoint `GET /activity/recent` et quatre fonctions portefeuille dédiées
(`_portfolio_interventions/_work_orders/_alarms/_findings`, dupliquées depuis les
fonctions par équipement plutôt que de risquer un changement de signature sur un module
déjà testé) — chacune bornée par `limit` (directive, section 29), jamais l'historique
complet du tenant chargé pour n'en garder que les derniers. Seule interaction du bloc :
un filtre par catégorie, composant client `RecentActivityFeed.tsx` (troisième composant
client de la console après `LoginError` et `PlacementEditor`), qui ne fait que montrer/
cacher des entrées déjà triées et déjà traduites côté serveur — satisfait « lisible et
filtrable » (section 16) sans bibliothèque de graphique ni logique de tri côté client.
Sur les onze catégories listées par la section 16, quatre sont couvertes honnêtement
aujourd'hui (alarmes, constats, ordres de travail, interventions) ; trois n'ont aucune
trace exploitable dans le système actuel et restent DEFER (changements d'état
d'équipement — calculés à la lecture, jamais journalisés ; événements énergétiques ;
incidents, délibérément distincts des alarmes, section 24, sans entité propre encore) ;
les quatre dernières (événements Edge, changements de connectivité, commandes
autorisées, résultats de commandes) existent déjà comme faits horodatés dans la table
`events` (`app/events.py`, vocabulaire fermé DEVICE_WENT_OFFLINE/CAME_ONLINE,
DATA_BECAME_STALE/RESTORED, COMMAND_REQUESTED/DISPATCHED/VERIFIED/FAILED/TIMED_OUT) mais
n'ont pas encore de fonction de lecture en masse ni de place dans `node_timeline` ou
`portfolio_timeline` — signalé ici plutôt qu'ajouté à la hâte, pour que la future page
dédiée « Unified Timeline » (section 36, point 3) les intègre proprement en même temps
qu'elle consolidera `node_timeline`/`portfolio_timeline` plutôt que de les dupliquer une
troisième fois.

**Unified Timeline (30/09/2026, section 36 point 3)** : la directive ne demande pas une
nouvelle page pour ce point, mais « en faire un composant web partagé plutôt qu'une
section isolée de la fiche équipement » (section 22 : « la timeline doit être un
composant central partagé »). Fait : extraction de la chronologie de `/registre/{id}`
(qui vivait comme du JSX inline dans cette seule page) vers `apps/web/src/components/
Timeline.tsx` — même donnée (`GET /graph/nodes/{id}/timeline`), même comportement, même
pagination par curseur de date, zéro changement fonctionnel, uniquement une frontière de
composant clarifiée pour que toute future page ayant besoin d'un historique fusionné pour
un actif (Alarms & Incidents, Maintenance dédiée...) puisse le réutiliser sans dupliquer
le rendu ni la traduction des statuts par catégorie (`timelineStatusLabel`, maintenant
testée : 5 tests unitaires). Distinct et volontairement non fusionné avec
`RecentActivityFeed.tsx` (bloc « Activité récente » du Global Command Center) : les deux
partagent une même famille de données (interventions/ordres de travail/alarmes/constats
fusionnés) mais servent des usages différents — chronologie d'un seul actif avec
pagination par curseur, contre portefeuille entier avec filtre par catégorie — les forcer
ensemble aurait compliqué les deux pour un bénéfice incertain ; à reconsidérer seulement
si une vraie douleur de maintenance apparaît. **Grille produit (ADR 014)** : Backend
inchangé (DONE de longue date), API inchangée, Web DONE (composant partagé, extrait sans
changement de comportement), Mobile N/A (l'écran passeport mobile a son propre rendu de
chronologie, plus simple, jamais un composant partagé entre les deux plateformes —
React Native et Next.js ne partagent pas leurs composants JSX), Edge N/A, Tests DONE (5
nouveaux tests sur `timelineStatusLabel`, suite complète sans régression : 148 tests web),
Documentation DONE.

Le Global Command Center (section 36, point 1) est maintenant complet dans son
périmètre honnête : carte/portefeuille (déjà là), alarmes prioritaires, maintenance,
énergie, santé des actifs, activité récente.

**Alarms & Incidents (30/09/2026, section 36 point 4)** : nouvelle page `/alarmes`,
portefeuille complet des alarmes et constats ouverts — pas seulement les 8 premières déjà
montrées par le bloc « Alarmes prioritaires » du Global Command Center, et avec les
constats en plus (absents de ce bloc). Deux tables séparées (Alarmes, Constats), jamais
fondues en une seule notion générique (modèle State/Event/Policy/Alert/Incident, directive
section 24) : chacune garde ses propres actions (acquitter, retour à la normale, faux
positif, clore, confirmer). Deux composants extraits de la fiche équipement pour être
réellement partagés plutôt que copiés : `SignalActions.tsx` (les mêmes boutons/formulaires
qu'utilisait déjà `/registre/{id}`) et `SEVERITY_COLOR` (déplacé de `page.tsx` vers
`lib/portfolio.ts`, exporté). Actions serveur propres à `/alarmes` (`app/alarmes/actions.ts`)
plutôt que réutilisation de celles de la fiche équipement : mêmes appels API, mais
redirection et revalidation vers `/alarmes` en cas d'échec, jamais vers la mauvaise page.
Aucun nouvel endpoint : réutilise `GET /alarms`, `GET /findings` (déjà filtrables par
`handling_status`) et les endpoints d'action déjà existants. **Grille produit (ADR 014)** :
Backend inchangé (DONE de longue date), API inchangée, Web DONE (nouvelle page + deux
composants partagés), Mobile N/A (l'écran passeport mobile gère déjà ses propres
signalements pour l'équipement affiché — pas un usage de supervision portefeuille), Edge
N/A, Tests N/A pour la page elle-même (lecture pure comme `/ordres-de-travail`, sans
logique propre à tester séparément — même précédent), Documentation DONE. Un bug a été
trouvé et corrigé en construisant cette page, avant tout commit : le champ `kind` d'un
constat (nécessaire pour ne jamais permettre de confirmer une prédiction, voir
`app/findings.py::confirm_finding`) avait été omis du type de la nouvelle page — aurait
laissé confirmer une prédiction depuis `/alarmes`, alors que la fiche équipement l'interdit
déjà correctement.

**Maintenance, page dédiée (30/09/2026, section 36 point 5)** : `/ordres-de-travail`
(gardé, jamais réécrit) devient la page Maintenance à part entière — même table d'ordres
de travail et même formulaire de création qu'avant, enrichis des deux listes que le bloc
« Maintenance » du Global Command Center ne montre qu'en aperçu plafonné (pannes
répétitives, dernières clôtures) : ici sans plafond, complément « tout voir » du bloc
résumé, exactement comme `/alarmes` l'est pour « Alarmes prioritaires ». Mêmes fonctions
pures que le tableau de bord (`repeatingFailures`, `recentClosures` de
`apps/web/src/lib/maintenance.ts`), aucune deuxième logique de calcul ni nouvel endpoint
(réutilise `GET /work-orders`, `GET /interventions`, déjà appelés ailleurs). Migré vers le
socle de style partagé (`pageContainerStyle`/`cardStyle`) comme `/alarmes` et `/edge`.
Lien de navigation du tableau de bord renommé « Ordres de travail » → « Maintenance »
(même URL, `work_orders_link` → `maintenance_link`), reflet honnête du nouveau contenu de
la page. **Grille produit (ADR 014)** : Backend inchangé, API inchangée, Web DONE, Mobile
N/A, Edge N/A, Tests N/A pour la page (lecture pure, même précédent que `/alarmes` et
`/ordres-de-travail` d'origine — les fonctions qu'elle appelle sont déjà testées dans
`maintenance.test.ts`), Documentation DONE.

**Energy, page dédiée (30/09/2026, section 36 point 6)** : nouvelle page `/energie`,
détail par compteur que le bloc « Énergie » du Global Command Center résume sans jamais
lister (total par unité, tendance) — ici chaque compteur individuellement, avec un lien
direct vers la fiche équipement où vivent déjà la comparaison à une baseline et
l'historique complet (`app/energy/normalization.py`). Aucun nouvel endpoint : réutilise
`GET /energy/portfolio-summary`, déjà construit pour le tableau de bord
(`app/energy/aggregation.py`) — même honnêteté que le bloc résumé (jamais d'économies, de
CO2, de ROI ni de KPI réglementaire ; compteur sans donnée affiché « Indisponible », jamais
zéro). **Grille produit (ADR 014)** : Backend inchangé, API inchangée, Web DONE, Mobile
N/A, Edge N/A, Tests N/A pour la page (lecture pure ; les fonctions qu'elle appelle —
`summarizeEnergyByUnit`, `countMetersWithoutData` — sont déjà testées dans
`energy.test.ts`), Documentation DONE.

**Edge & Connectivity (30/09/2026, section 36 point 7, arrêt partiel — voir plus bas)** :
audit de `/edge` contre les 15 éléments listés par la section 25. Trois étaient déjà
couverts (identité Edge, statut, dernière communication). Deux ajoutés dans ce lot, déjà
renvoyés par `GET /devices` (`DeviceOut`) mais jamais affichés : empreinte de clé
(provenance de l'authentification) et date de provisionnement. **Dix des quinze éléments
restent honnêtement hors d'atteinte aujourd'hui, faute de toute donnée exploitable, pas
faute de temps** : version de l'agent Edge, dernière synchronisation (distincte de la
dernière communication — aucun champ ne la distingue), connecteurs actifs et protocoles
par passerelle (les configurations Modbus/BACnet/OPC UA sont indexées par équipement, pas
par passerelle Edge — aucune table ne relie une ligne `edge_devices` à ses connecteurs),
équipements découverts (la découverte BACnet est indexée par équipement, même limite),
qualité et erreurs (aucun compteur par passerelle), reconnexions (les événements
`DEVICE_WENT_OFFLINE`/`DEVICE_CAME_ONLINE` existants concernent la communication d'un
équipement au sens GTB, pas la passerelle Edge elle-même — `communication_status` d'une
passerelle est un calcul à la lecture, sans historique, voir
`app/devices.py::communication_status`), offline queue, backlog, diagnostics.

Construire ces dix éléments demanderait un vrai modèle de télémétrie Edge (une passerelle
sait quels connecteurs elle exécute, avec quels compteurs d'erreur et de file d'attente) —
un changement architectural, pas un ajustement d'écran, et donc un arrêt explicite au sens
de la section 38 (« changement architectural majeur »), pas une case à cocher improvisée
avec une donnée inventée. Signalé ici pour décision plutôt que construit à la hâte : la
disposition la plus solide demanderait probablement que le client Edge lui-même rapporte
ces compteurs (`app/routers/devices.py`, à côté de `last_seen_at`), plutôt qu'un calcul
reconstruit après coup côté cloud. **Grille produit (ADR 014)** : Backend PARTIAL
(identité/statut/communication déjà là ; aucune télémétrie de connecteur), API PARTIAL,
Web DONE pour les deux champs ajoutés, PARTIAL pour le reste de la section 25, Mobile N/A,
Edge N/A (rien n'est encore demandé à l'agent lui-même), Tests N/A pour la page (lecture
pure), Documentation DONE (cet écart, précis, plutôt qu'un silence).

Reste de la feuille de route active (sections 5 à 37, DEFER explicite) : composants
d'architecture UI restants (AppShell, Navigation, AssetCard, MetricCard, AlarmCard,
DataQualityIndicator, ConnectivityIndicator, EmptyState, SkeletonState, PermissionGuard),
fil d'Ariane, dashboards par rôle, carte géographique, graphiques avec downsampling, table
`events` non encore lue par API, télémétrie Edge par connecteur (ci-dessus, décision
requise) — puis la suite de l'ordre de construction (section 36).

**Sites & Buildings (30/09/2026, section 36 point 8)** : audit plutôt que construction.
`/registre` couvre déjà ce périmètre — sites (nom, fuseau, archivage), hiérarchie
bâtiments/zones (espaces), plans de site et import IFC, prestataires de maintenance,
équipements — et le drill-down par site de la vue Portfolio (`/?site=`, ADR 014 §2) en
donne déjà la vue opérationnelle (KPI, alarmes/constats par gravité, passerelles Edge).
Aucun écart trouvé qui justifierait une nouvelle page : KEEP, sans ajout, pour ne jamais
ajouter une fonctionnalité uniquement pour cocher une case de la feuille de route.

**Telemetry (30/09/2026, section 36 point 9)** : nouvelle page `/telemetrie`, la dernière
valeur de chaque point validé du portefeuille en une seule vue plutôt que d'ouvrir chaque
fiche équipement une à une. Nouvel endpoint bulk `GET /telemetry/portfolio-latest`
(`app/telemetry_overview.py`) plutôt qu'un appel par point depuis le navigateur (section
29) : réutilise `latest_usable_bulk`, rendue publique dans `app/equipment_status.py` où
elle avait été écrite pour le bloc « Santé des actifs » — troisième usage de ce même motif
bulk (`DISTINCT ON`) après la santé des actifs et la chronologie portefeuille, jamais
dupliqué une quatrième fois sans réutiliser l'existant. Ne recalcule jamais le score de
confiance complet (`GET /points/{id}/trust`, plusieurs requêtes par point) : seulement la
fraîcheur simple (périmé ou non selon l'intervalle attendu du point) — le détail complet
d'un point reste sur la fiche équipement. Un point sans mesure encore reçue est rapporté
comme tel (« Indisponible »/« Jamais mesuré »), jamais omis. **Grille produit (ADR 014)** :
Backend DONE (nouveau module, réutilise l'existant), API DONE (nouvel endpoint additif),
Web DONE, Mobile N/A, Edge N/A, Tests DONE (6 tests : valeur et fraîcheur, absence de
mesure, péremption, exclusion des points non validés, isolation des tenants, endpoint
API), Documentation DONE.

**Documents (30/09/2026, section 36 point 10)** : nouvelle table `documents`
(migration `b1d4f2a9c7e3`) — manuel, certificat, garantie, fiche technique, contrat,
rapport de conformité, rattachés à une position fonctionnelle (équipement). Comblait
l'écart identifié lors de l'audit Equipment Passport (« documents » était le seul des 19
éléments de la section 21 réellement absent). Distinct des plans 2D (`floor_plans`, ADR
011 — un plan d'étage) et des photos d'intervention (ADR 006) : un document ici est une
pièce administrative ou technique de l'équipement, pas un plan spatial ni une preuve
d'intervention. Même mécanique d'envoi que les plans (URL présignée puis confirmation,
RLS, `forbid_update`/`forbid_delete`), mais sans numéro de version partagé : un
certificat renouvelé est un nouveau document, jamais une nouvelle version du précédent
(rien n'est jamais écrasé, mais deux documents restent deux faits distincts, contrairement
à un plan qui remplace fonctionnellement le précédent). Nouveaux endpoints
`POST/GET /functional-locations/{id}/documents(/upload-url)`, `GET /documents/{id}`,
`GET /documents/portfolio` (bibliothèque de tout le portefeuille, avec l'équipement visé
— évite de devoir connaître l'équipement à l'avance). Nouvelle page `/documents` :
tableau portefeuille (équipement, catégorie, fichier, date d'envoi, téléchargement) plus
un formulaire d'envoi (équipement, catégorie, fichier) réutilisant le patron déjà établi
pour les plans 2D (`uploadFloorPlan` → `uploadDocument`, même dance en deux temps, aucune
donnée binaire ne transite par le serveur applicatif au-delà du calcul de l'empreinte
SHA-256). **Grille produit (ADR 014)** : Backend DONE, API DONE, Web DONE, Mobile N/A
(pas demandé par la section 36 ; l'envoi depuis le terrain resterait à concevoir
séparément si le besoin apparaît), Edge N/A, Tests DONE (10 tests : envoi puis lecture,
deux envois indépendants sans écrasement, bibliothèque portefeuille avec équipement visé,
rôle technicien lecture seule, catégorie inconnue refusée, type de fichier non pris en
charge refusé, clé de stockage étrangère refusée, équipement/document inconnu → 404,
isolation tenant), Documentation DONE.

**Users & Access (30/09/2026 signalé, 01/10/2026 résolu sans secret, section 36 point 11).**
Les rôles viennent uniquement de Keycloak (`realm_access.roles` du jeton, voir
`app/auth.py::require_role`/`require_any_role`) — il n'existe aucune table locale
d'utilisateurs ni de rôles à afficher ou éditer (ligne « Autorisations fines » : rôles
Keycloak globaux par tenant, ReBAC en DEFER tant qu'aucun cas réel de délégation
n'existe). Gérer les comptes d'un tenant (créer, retirer, changer un rôle) exigerait
d'appeler l'API d'administration Keycloak depuis le backend — un compte de service avec
droits d'administration sur le realm, donc un nouveau secret et une nouvelle intégration
externe structurante : signalé le 30/09/2026 comme arrêt explicite de la section 38
(« nouveau compte externe », « secrets »), pas construit sans décision de Mohamed.

Ce qui restait possible sans rien de tout cela, construit le 01/10/2026 à sa demande
(« fais tout si possible ») : nouvelle page `/acces` montrant (1) l'identité et les rôles
de la personne connectée, déjà disponibles sans nouvel appel via `GET /me` ; (2) le
catalogue des trois rôles du produit et ce que chacun permet (texte explicatif, pas une
donnée du système) ; (3) un lien direct vers la console d'administration Keycloak pour
gérer les comptes, son adresse dérivée de `OIDC_ISSUER` (déjà configuré, forme
`<base>/realms/<realm>`) par la fonction pure `keycloakAdminConsoleUrl`
(`apps/web/src/lib/keycloak.ts`) — jamais un nouveau secret ni un appel à l'API
d'administration elle-même. La gestion réelle des comptes reste entièrement dans
Keycloak ; cette page ne duplique aucune donnée d'utilisateur. **Grille produit
(ADR 014)** : Backend N/A (aucun nouvel endpoint, réutilise `/me`), API N/A, Web DONE,
Mobile N/A (pas une tâche terrain), Edge N/A, Tests DONE (3 tests purs sur
`keycloakAdminConsoleUrl` : dérivation standard, barre oblique finale, adresse non
conforme → `null`), Documentation DONE. La gestion effective des comptes (créer,
retirer, changer un rôle) reste BLOCKED pour les mêmes raisons qu'au 30/09/2026 — ce
n'est pas ce point qui a été construit, seulement ce qui tenait sans nouveau secret.

**Spatial/BIM (30/09/2026, section 36 point 12)** : nouvelle page `/plans`, la dernière
version de chaque plan 2D du portefeuille (site, espace, nombre de placements validés)
en une seule vue plutôt que d'ouvrir chaque espace une à une depuis `/registre`. Nouvel
endpoint bulk `GET /floor-plans/portfolio` (`app/floor_plans.py::list_portfolio_floor_plans`),
même motif `DISTINCT ON` que la santé des actifs, la chronologie, la télémétrie et les
documents — cinquième réutilisation de ce motif, jamais dupliqué sans y penser d'abord.
L'envoi d'un plan et l'import IFC restent sur `/registre` (ADR 011) : cette page
complète la vue portefeuille, elle ne duplique pas le formulaire d'envoi ni ne déplace
l'éditeur de placements existant (`/registre/plans/[floorPlanId]`), seulement lié depuis
la nouvelle page. **Grille produit (ADR 014)** : Backend DONE (nouvelle fonction, réutilise
l'existant), API DONE (nouvel endpoint additif, enregistré avant la route paramétrée pour
éviter toute collision), Web DONE, Mobile N/A, Edge N/A, Tests DONE (1 nouveau test :
seule la dernière version par espace est montrée, avec site et espace corrects — les 8
tests existants du module plans 2D restent verts), Documentation DONE.

**Automation (30/09/2026, section 36 point 13)** : pas entièrement bloqué, contrairement
à l'attente initiale — audit d'abord, comme pour chaque écran de cette liste. La règle
non négociable 1 interdit toute commande vers un équipement réel, mais l'état souhaité
(`app/desired_states.py`) est par conception une attente déclarée par un humain, comparée
à l'état réel pour détecter une dérive, **jamais une commande** — documenté comme tel dans
le module depuis son origine (ADR 012, section 2.4) et déjà utilisable sur n'importe quel
point, pas seulement le relais simulé. Seule la capacité d'écriture (`app/commands.py`,
`app/connectors/simulated_actuator.py`) reste strictement réservée au `device_type`
"simulated_relay" ; l'état souhaité, lui, ne commande jamais rien et n'a donc pas besoin
de cette restriction. Nouvelle page `/automation` : toutes les attentes actives du
portefeuille (point, équipement, valeur attendue, plage horaire, motif, depuis quand),
avec un rappel explicite dans l'introduction de la page que ceci n'agit jamais sur un
équipement. Nouvel endpoint bulk `GET /desired-states/portfolio-active`
(`app/desired_states.py::list_portfolio_active_desired_states`), sixième réutilisation du
motif de jointure bulk introduit pour la santé des actifs. Ne construit ni ne modifie la
capacité de commande elle-même. **Grille produit (ADR 014)** : Backend DONE (nouvelle
fonction, réutilise l'existant), API DONE (nouvel endpoint additif), Web DONE, Mobile N/A,
Edge N/A, Tests DONE (2 tests : les attentes actives sont listées avec le point visé et
excluent celles déjà terminées ; isolation tenant), Documentation DONE.

Section 36 (« pages à finaliser dans cet ordre ») : les 13 écrans ont maintenant chacun
une page, un audit KEEP, ou une réponse explicite. Un seul point reste partiellement en
attente : la gestion effective des comptes dans Users & Access (créer, retirer, changer
un rôle), qui exigerait une nouvelle intégration à l'API d'administration Keycloak
(compte de service, secret) — un arrêt explicite demandé par la section 38, toujours pas
une décision que ce travail peut prendre seul.

**Equipment Passport (30/09/2026, section 36 point 2)** : audit plutôt que reconstruction,
comme demandé (« à consolider selon la liste de la section 21, pas à recréer »). Sur les 19
éléments listés par la section 21, 18 étaient déjà présents sur `/registre/{id}` avant ce
tour (identité, type, fabricant, modèle, numéro interne, statut, connectivité, dernière
donnée, mesures importantes, alarmes, maintenance, énergie, QR, historique/timeline —
celle-ci déjà branchée sur `GET /graph/nodes/{id}/timeline` avec pagination). Seul
« documents » manque réellement (aucun stockage de document par équipement aujourd'hui,
contrairement aux photos d'intervention ou aux plans de site qui existent déjà) — DEFER
volontaire : la directive place « Documents » comme sa propre page plus tard dans l'ordre
de construction (section 36, point 10), pas comme un ajout à la hâte ici. Deux vrais
défauts trouvés et corrigés : (1) le statut universel (`StatusBadge`, langage commun
depuis le 30/09/2026) n'était branché nulle part sur la fiche équipement — la page la plus
critique pour le statut ne portait pas encore le vocabulaire censé unifier toute la
console ; (2) l'objectif « comprendre l'état d'un équipement en quelques secondes »
n'était pas atteint : identité, statut et localisation étaient dispersés entre un `<h1>`
nu et une section « statut » isolée, avant une quinzaine de sections techniques
(Modbus/BACnet/commande/énergie/règles). Corrigé par un nouveau bloc `IdentityHeader`
(un seul, en haut de page) qui réunit `StatusBadge` + le texte détaillé déjà existant
(`StatusLine`, conservé tel quel), l'identité de l'exemplaire (fabricant, référence, type,
numéro de série) et un fil site › zone › système — ce dernier fil (`space_path`) était déjà
renvoyé par `build_passport` mais jamais affiché côté web (uniquement sur mobile) : ajouté
au type `Passport` et affiché aux deux endroits pour la première fois. Le conteneur de
page passe de 720px à `pageContainerStyle` (1080px, même gabarit que le reste de la
console) pour la cohérence visuelle (section 1) ; les ~15 sections techniques plus bas
gardent leurs styles locaux d'origine (`sectionStyle`/`mutedStyle` propres à ce fichier) —
migration complète DEFER, comme déjà noté pour cette page dans la ligne « Design System
commun » ci-dessous, jamais une réécriture générale d'un fichier de 2000 lignes en un
seul passage.

| Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification |
|---|---|---|---|---|---|---|---|
| Navigation universelle (Organisation → Portfolio → Site → Facility → Building/Plant → Zone → System → Equipment → Component → Sensor/Actuator), fil d'Ariane, changement rapide de site | ⚠️ **02/10/2026 : deuxième écran équipé** — composants partagés `apps/web/src/components/Breadcrumb.tsx` (fil d'Ariane cliquable) et `SiteSwitcher.tsx` (liste déroulante pure HTML `<details>`, sans JavaScript, vers la vue Portfolio déjà filtrable par site, `/?site={id}` — mécanisme existant, réutilisé tel quel), déployés sans aucune modification sur un deuxième écran : l'éditeur de plan (`/registre/plans/[floorPlanId]`), fil Accueil → Site → Espace → Plan (le fichier du plan). Aucune nouvelle donnée : réutilise `GET /sites` et les espaces déjà chargés par la page pour résoudre le site du plan. Premier déployé sur la fiche équipement (`/registre/[id]`), fil Accueil → Site → Espaces → Équipement. Un segment sans destination connue (un espace, qui n'a pas encore de fiche dédiée) reste du texte, jamais un lien mort | Standard chez les grands éditeurs (arborescence de site persistante) | — | Haute | `apps/web/src/components/Breadcrumb.tsx`, `SiteSwitcher.tsx` ; déployé sur `apps/web/src/app/registre/[id]/` et `apps/web/src/app/registre/plans/[floorPlanId]/` | ADD composants partagés + premier écran (02/10/2026) ; ADD deuxième écran (02/10/2026) ; DEFER le déploiement sur les onze écrans restants (même composant, un écran à la fois) | **Grille produit (ADR 014)** : Backend N/A, API N/A (aucune donnée nouvelle, uniquement de la navigation), Web PARTIAL (deux écrans sur treize équipés, composant prêt pour les autres), Mobile N/A, Edge N/A, Tests DONE (vérifié par le typage, le lint et la suite complète — 163 tests web au vert ; composant non testé isolément — pure présentation sans logique propre), Documentation DONE (ce document). La hiérarchie reste exploitable même quand un niveau n'existe pas (ex. pas d'espace entre le site et l'équipement) — chaque segment est optionnel. |
| Recherche globale (site, espace, équipement, identifiant, QR, incident, alarme, intervention, ordre de travail) | ⚠️ **02/10/2026 : première version** — `GET /search?q=` (`app/search.py`, `app/routers/search.py`) interroge en une requête sites, espaces, équipements, étiquettes/QR (résolues vers le nœud qu'elles désignent) et ordres de travail, filtré par tenant (RLS) et par rôle entièrement côté serveur, jamais une liste complète renvoyée puis filtrée dans le navigateur. Alarmes, constats et interventions volontairement hors de cette première version : leur texte affiché est produit à l'affichage depuis un code et des paramètres (ADR 013), jamais stocké comme une phrase — rien à chercher par motif texte côté base sans reconstruire la traduction à chaque recherche ; une recherche par code reste possible dans un incrément séparé. Web fait (même jour) : barre de recherche sur la vue Portfolio (`apps/web/src/app/page.tsx`), formulaire GET sans JavaScript, résultats en dessous avec lien quand une destination existe (site, équipement, étiquette) — un espace ou un ordre de travail restent du texte, pas de fiche dédiée à ce jour (même principe que Breadcrumb.tsx : jamais un lien mort) | Standard chez les grands éditeurs et les GMAO matures | — | Moyenne | `app/search.py`, `app/routers/search.py` ; `apps/web/src/app/page.tsx` | ADD endpoint + barre de recherche (02/10/2026) ; DEFER alarmes/constats/interventions (recherche par code, incrément séparé) ; DEFER lien direct pour un espace ou un ordre de travail (pas de fiche dédiée) | **Grille produit (ADR 014)** : Backend DONE (sites, espaces, équipements, étiquettes, ordres de travail), API DONE, Web DONE (portfolio), Mobile N/A, Edge N/A, Tests DONE (11 tests : une catégorie par type de résultat, sensibilité à la casse, requête vide, isolation entre tenants, rôle requis, validation de la requête), Documentation DONE. Le filtrage par tenant (RLS) et par rôle reste entièrement côté serveur, jamais une liste complète renvoyée puis filtrée dans le navigateur. |
| Dashboards spécialisés (Operations/Fleet, Maintenance, Energy & Sustainability, Building/GTB-GTC, Automation & Control, Edge & Connectivity, Spatial/BIM) | ✅ **02/10/2026 : audit complet, les sept domaines couverts** — cette ligne était périmée : elle ne mentionnait que Edge & Connectivity comme écran dédié alors que quatre autres écrans portefeuille existaient déjà depuis le 30/09/2026 (section 36, points 6/9/12/13), jamais reportés ici. État réel : **Energy & Sustainability** → `/energie` (point 6, KPI de consommation par unité + table complète des compteurs, graphique brut/normalisé sur chaque équipement) ; **Building/GTB-GTC** → `/telemetrie` (point 9, dernière valeur de chaque point validé du portefeuille, fraîcheur simple, un appel groupé) ; **Spatial/BIM** → `/plans` (point 12, dernière version de chaque plan 2D du portefeuille avec site/espace visés ; complète sans dupliquer `/registre/plans/{id}`, qui reste l'éditeur de placements et l'import IFC) ; **Automation & Control** → `/automation` (point 13, attentes déclarées actives — Desired State — comparées à l'état réel pour détecter une dérive ; ne pilote rien, la seule capacité d'écriture du dépôt reste réservée au `simulated_relay`, règle non négociable 1 respectée) ; **Edge & Connectivity** → `/edge` (30/09/2026, passerelles groupées par site/compte/communication) ; **Operations/Fleet** → `/registre` + drill-down par site de la vue Portfolio, audité le 30/09/2026 (« Sites & Buildings ») et jugé suffisant : aucun écart trouvé, KEEP sans ajout ; **Maintenance** → `/ordres-de-travail` (liste complète, planification, changement de statut, lien vers l'équipement). Chaque écran lit un endpoint bulk dédié (`GET /telemetry/portfolio-latest`, `GET /floor-plans/portfolio`, `GET /desired-states/portfolio-active`…) plutôt qu'un appel par équipement depuis le navigateur | Chacun de ces domaines existe séparément chez les grands éditeurs (rarement unifiés sans verrouillage fournisseur) | — | Haute | `apps/web/src/app/{energie,telemetrie,plans,automation,edge,registre,ordres-de-travail}/` | KEEP tous les écrans existants (aucun écart trouvé à l'audit) ; correction de cette ligne, aucun nouveau code nécessaire | **Grille produit (ADR 014)** : Backend DONE pour les sept domaines, API DONE (un endpoint bulk par écran, jamais un format taillé sur mesure au-delà du nécessaire), Web DONE pour les sept domaines (un écran portefeuille ou une vue existante auditée comme suffisante, par domaine), Mobile N/A (le mobile reste un usage terrain, pas une supervision par domaine — ADR 014 §11), Edge N/A, Tests DONE côté données (suites existantes par domaine ; les écrans eux-mêmes sont des lectures pures, sans logique propre à tester séparément), Documentation DONE (cette correction). Ne jamais dupliquer les données pour construire un dashboard : chaque vue spécialisée lit les mêmes endpoints que la fiche équipement, jamais un format de réponse taillé pour un seul écran (ADR 014 §5). |
| Dashboards adaptés au rôle (dirigeant, responsable multi-sites, facility manager, responsable maintenance, energy manager, opérateur, technicien, intégrateur, administrateur) | ❌ Absent — un seul écran pour tous les rôles web, différencié seulement par les actions autorisées (déjà correct : ligne « Présentation selon le profil ») | Vues par profil chez les grands éditeurs | — | Moyenne | Aucune donnée par écran taillée pour un seul rôle (déjà respecté) ; widgets configurables à prévoir sans les construire maintenant | DEFER (pas de moteur de personnalisation avant un besoin réel) | **Grille produit (ADR 014)** : Backend N/A, API N/A, Web PARTIAL (un seul écran, mais aucune décision ne bloque un futur découpage par rôle), Mobile N/A, Edge N/A, Tests N/A, Documentation PARTIAL. Le mobile a déjà son propre écran distinct pour le technicien terrain (ADR 014 §11) — c'est la seule différenciation par rôle qui existe à ce jour, et elle est délibérée. |
| Design System commun (typographie, grille, cards, tableaux, formulaires, graphiques, badges, niveaux de criticité, empty/loading/error states, mode clair/sombre) | ⚠️ Partiel — `apps/web/src/lib/formStyles.ts` porte un petit socle de jetons partagés (couleurs, conteneur de page, en-tête de page, carte, titre de section, badge générique), appliqué à l'accueil et à Edge & Connectivity. **Langage d'état universel (30/09/2026, directive de Mohamed, section 5)** : nouveau composant `apps/web/src/components/StatusBadge.tsx` — vocabulaire unique Normal/Attention/Critique/Hors ligne/Donnée ancienne/Inconnu/Maintenance, un jeton couleur par état (`ASSET_STATUS_COLOR`), jamais une couleur codée en dur dans une page ; `equipmentStatusToAssetStatus()` traduit la réponse déjà existante de `GET /functional-locations/{id}/status` sans jamais deviner un état que la donnée ne porte pas (« attention » et « maintenance » restent hors d'atteinte de cette fonction tant qu'aucune donnée réelle ne les distingue) ; branché sur la cellule de statut de la vue Portfolio (`StatusCell`), badge + texte détaillé conservé côte à côte. **Fiche équipement (30/09/2026)** : `StatusBadge` branché aussi ici (nouveau bloc `IdentityHeader`), conteneur de page migré vers `pageContainerStyle` — les ~15 sections techniques plus bas (Modbus/BACnet/commande/énergie/règles) gardent encore leurs styles locaux d'origine, migration progressive, pas d'un coup. Distinct de la gravité des alarmes/constats (`severity.*`), qui reste son propre axe (directive, section 24) — même s'ils partagent la même charte de couleurs pour la cohérence visuelle. **02/10/2026 : première passe de déduplication des couleurs codées en dur** — `colors.danger` ajouté à `formStyles.ts` (cinq pages répétaient `"#c0392b"` indépendamment : `/registre` liste et fiche, `/alarmes`, `/ordres-de-travail`, l'éditeur de plan) ; les variantes de gris/bleu d'accentuation codées en dur (`#666`, `#2563eb` en bordure) remplacées par `colors.textMuted`/`colors.accent` sur ces mêmes écrans plus `PlacementEditor.tsx`, y compris la définition locale `mutedStyle` de la fiche équipement (un seul point à corriger, pas ses ~10 usages). La palette volontairement distincte de `/login` (thème sombre de la page de connexion) n'a pas été touchée : une valeur hexadécimale identique par coïncidence à un jeton ne veut pas dire même usage. Les ~15 sections techniques de la fiche équipement et les styles structurels de `/registre`/`/ordres-de-travail` (tableaux, formulaires, cards) restent en styles locaux, migration progressive à poursuivre | Systèmes de conception matures chez les grands éditeurs | — | Moyenne | `apps/web/src/lib/formStyles.ts`, `apps/web/src/components/StatusBadge.tsx` ; pas de bibliothèque de composants externe pour l'instant (dépendance structurante à évaluer séparément si le besoin devient réel) | KEEP le socle existant + ADD langage d'état universel (30/09/2026) + ADD `colors.danger` + REFACTOR couleurs codées en dur → jetons (02/10/2026) ; DEFER la migration structurelle restante (cards/tableaux/formulaires des ~15 sections techniques), jamais une réécriture générale | **Grille produit (ADR 014)** : Backend N/A, API N/A, Web PARTIAL (le socle, le `StatusBadge` et désormais une palette de couleurs unifiée couvrent une partie de la console, pas encore un système complet), Mobile PARTIAL (mêmes principes, catalogue de styles séparé, pas encore le `StatusBadge`), Edge N/A, Tests DONE (7 tests unitaires sur `equipmentStatusToAssetStatus`, suite vitest complète 158 tests + build Next.js + typage + lint sans régression après la déduplication), Documentation DONE (ce document, `docs/spec/dashboard-ui-directive.md`). Aucun mode sombre (hors `/login`, déjà sombre par construction), aucune vérification d'accessibilité formelle à ce jour — signalé, pas bloquant. |
| Visualisation de données orientée décision (séries temporelles, comparaison de périodes, baseline vs réel, distributions, comparaison entre sites/équipements) | ⚠️ **02/10/2026 : premier graphique** — `apps/web/src/components/EnergyBarChart.tsx`, un graphique à barres groupées (consommation brute et normalisée, jusqu'à 12 périodes, la plus ancienne d'abord) sur la section « Performance énergétique » de la fiche équipement. SVG construit à la main, **aucune bibliothèque de graphiques ajoutée** : le besoin d'un graphique à barres restait simple à construire directement, la question d'une dépendance externe reste ouverte pour des visualisations plus complexes (distributions, comparaison entre sites) quand le besoin deviendra réel. Conserve l'unité, la période (étiquette de date par barre) et le statut de normalisation (une période non normalisable n'affiche que sa barre brute) | Standard chez les outils d'analytique et les grands éditeurs | — | Moyenne | `apps/web/src/components/EnergyBarChart.tsx` ; déployé sur `apps/web/src/app/registre/[id]/` | ADD premier graphique, sans nouvelle dépendance (02/10/2026) ; DEFER une bibliothèque de graphiques pour les visualisations plus riches (distributions, comparaison entre sites), si le besoin devient réel | **Grille produit (ADR 014)** : Backend DONE (les séries existent), API DONE, Web PARTIAL (un graphique sur une section, pas encore de courbe temporelle ni de comparaison entre sites/équipements), Mobile N/A, Edge N/A, Tests DONE côté données et par le typage/lint/suite complète (composant pure présentation, voir Breadcrumb/SiteSwitcher), Documentation DONE. Chaque graphique conserve unité, période, fuseau horaire, provenance et qualité de la donnée (ADR 014 §8) — jamais un KPI fabriqué pour remplir un écran. |



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

Risque ajouté au choix du fournisseur de stockage photo pour le staging (ADR 006,
25/09/2026) : la configuration de stockage est aujourd'hui unique pour toute la
plateforme (un seul panier, un seul fournisseur). À faire évoluer vers une résolution
par tenant avant qu'un client n'exige un hébergeur précis pour des raisons de
conformité — non bloquant aujourd'hui, signalé pour ne pas le découvrir sous la
pression d'un contrat signé.

Risque ajouté par le connecteur BACnet (25/09/2026) : la bibliothèque `bacpypes3`
utilisée est encore en version 0.0.x (pas de garantie de stabilité d'API entre deux
versions mineures). Le contrat exposé par `app/connectors/bacnet.py` (`BacnetPoint`,
`read_bacnet_points`, `BacnetReadError`) isole déjà le reste du noyau de cette
bibliothèque précise (règle non négociable 8) : une montée de version ou un
changement de bibliothèque ne devrait toucher que ce seul fichier. À vérifier avant
toute mise à jour de `bacpypes3` en production : rejouer `tests/test_bacnet_connector.py`
et `tests/test_bacnet_daemon.py`, qui parlent à un vrai serveur BACnet simulé et
détecteraient un changement de comportement.

Ré-évaluation de `bacpypes3` à l'occasion de la découverte BACnet V1 (27/09/2026,
ADR 015) : le risque de version 0.0.x signalé ci-dessus se confirme (pas de garantie de
stabilité d'API), mais aucune alternative Python mature n'existe pour BACnet/IP lecture
seule ; décision : garder `bacpypes3`, isolation renforcée (tout le savoir bacpypes3 reste
dans `app/connectors/bacnet.py`, jamais dans `app/bacnet_discovery.py` qui n'en connaît que
des structures simples). Détail dans l'ADR 015.

Connecteur OPC UA (27/09/2026) : la bibliothèque `asyncua` (LGPL-3.0-or-later, v2.0.1,
pure Python) est en version majeure 2.x, avec une garantie de stabilité d'API plus
forte que `bacpypes3` — risque moindre, signalé pour mémoire seulement. Même isolation :
le contrat exposé par `app/connectors/opcua.py` (`OpcuaPoint`, `read_opcua_points`,
`OpcuaReadError`) est le seul point de dépendance à la bibliothèque (règle non
négociable 8). À vérifier avant toute mise à jour d'`asyncua` en production : rejouer
`tests/test_opcua_connector.py` et `tests/test_opcua_daemon.py`, qui parlent à un vrai
serveur OPC UA simulé (le serveur de la même bibliothèque, jamais un mock).

## V1 Software Freeze — 02/10/2026

Directive de Mohamed du 02/10/2026 : audit complet de la chaîne V1 (Asset →
Edge/Simulation → Telemetry → Asset Model → State → FDD → Alarm → Timeline →
Intervention → Energy → Impact Analysis → Command Center), passe sécurité,
finition UX/UI des 13 écrans, puis gel logiciel si tout passe. Trois audits
indépendants menés en parallèle (sécurité, UX/UI, chaîne de bout en bout),
chacun en lecture seule, puis corrections appliquées une par une avec
vérification réelle (tests, typecheck, lint, build) à chaque étape — jamais
un correctif groupé non vérifié.

**Sécurité** (0 CRITIQUE trouvé ; l'exception de commande règle non
négociable 1 strictement respectée, vérifiée fichier par fichier) :
- ADD limitation de débit (`app/rate_limit.py`, dépendance `slowapi`) :
  défaut global 120/minute, 10/minute sur `/devices/auth` (surface la plus
  exposée à un essai de secrets en force brute) — défense en profondeur en
  plus de la comparaison en temps constant déjà en place.
- ADD test d'isolation tenant pour `commands` (`tests/test_commands_api.py`),
  seule table sensible qui n'en avait pas encore un dédié malgré la policy
  RLS déjà correcte.
- ADD commentaire expliquant l'absence volontaire de `CORSMiddleware`
  (architecture BFF, `app/main.py`) pour éviter qu'un futur développeur
  l'ajoute trop permissif sans réfléchir.
- ADD sauvegarde/restauration réelle (`scripts/backup_database.sh`,
  `scripts/restore_database.sh`) : cycle complet testé manuellement le
  02/10/2026 (sauvegarde → base vierge → restauration → données et
  politiques RLS intactes). Rôle PostgreSQL dédié obligatoire
  (`paios_backup`, `BYPASSRLS`, lecture seule) — le rôle applicatif est
  bloqué par `FORCE ROW LEVEL SECURITY`, volontairement.

**Chaîne de bout en bout** : 10 des 12 maillons vérifiés complets avec
preuve directe (fichier:ligne + test nommé). Deux corrections réelles :
- ADD lien Timeline → Intervention (`work_order_id`) : le modèle serveur
  l'acceptait déjà (`InterventionCreate.work_order_id`) mais aucun écran ne
  le proposait — un technicien perdait le fil entre l'alarme/l'ordre de
  travail qui l'amène sur site et l'intervention qu'il enregistre. Ajouté
  côté mobile (`nouvelle-intervention.tsx`, `passeport.tsx` — chaque ordre
  de travail du passeport devient un lien qui pré-remplit la nouvelle
  intervention), stocké hors ligne (migration locale SQLite n°4) et envoyé
  au serveur comme les autres champs.
- ADD test d'intégration mesure→règle→alarme→chronologie
  (`tests/test_rules.py::test_une_mesure_anormale_apparait_dans_la_chronologie_de_l_equipement`) :
  les deux maillons existaient et étaient prouvés séparément (même fonction
  des deux côtés), mais aucun test ne partait d'une vraie mesure jusqu'à la
  chronologie visible à l'écran.
- Clarification doc (`app/energy/`) : Intervention→Energy et Energy→Impact
  Analysis ne sont pas des transitions automatiques — deux consommateurs
  indépendants de la télémétrie, par choix d'architecture documenté, pas un
  oubli. Impact Analysis n'apparaît pas sur le tableau de bord portefeuille
  (seulement par équipement) — amélioration UX possible, non bloquante.

**UX/UI** (audit des 13 écrans web + mobile) : aucune donnée fictive,
aucune page qui ressemble à du développement, responsive déjà complet sur
12/13 écrans. Corrections réelles :
- ADD `loading.tsx` sur les 15 segments de route (convention Next.js, voir
  `src/components/LoadingScreen.tsx`) : jusqu'ici, un chargement lent
  n'affichait rien du tout — le point à plus fort effet de levier de
  l'audit, un seul composant partagé pour les 13 écrans.
- REFACTOR `registre/page.tsx` et `registre/[id]/page.tsx` sur le design
  system existant (`cardStyle`, `sectionTitleStyle`, `badgeStyle`) : les
  deux seuls écrans qui redéfinissaient leurs propres styles au lieu de
  réutiliser `formStyles.ts`/`StatusBadge.tsx` — la fiche équipement
  (`registre/[id]`) est la page la plus consultée du produit, ses alarmes
  et constats affichaient du texte brut au lieu d'un badge coloré par
  gravité, désormais cohérent avec `alarmes/page.tsx`.
- ADD centralisation de `COMMUNICATION_COLOR` (dupliqué à l'identique entre
  l'accueil et `/edge`) dans `formStyles.ts`.
- ADD nom lisible du client sur `GET /me` (`tenant_name`) : l'accueil
  mobile affichait l'UUID technique du tenant brut à chaque connexion.
- ADD explication du bouton de transmission OPERAT désactivé tant que la
  déclaration n'est pas « Prête » ; ADD `formatNumber` sur les pages OPERAT
  (chiffres jusque-là affichés bruts, incohérent avec `energie`/`telemetrie`).
- ADD état de chargement manquant sur `historique.tsx` (mobile) : la liste
  vide s'affichait avant même la réponse du serveur.

**02/10/2026 (suite) : flake BACnet corrigé à la racine.**
`test_groupe_electrogene_tension_reste_a_revoir` partageait le même port
UDP (`127.0.0.1:47846`) que le simulateur à portée module de
`tests/test_bacnet_field_comparison_e2e.py` — sur la suite complète,
selon l'ordre de collecte, le second pouvait démarrer avant que l'OS
n'ait vraiment libéré le port fermé par le premier (fermeture asynchrone
d'un socket UDP, jamais garantie instantanée), d'où le délai dépassé
observé uniquement sous charge. Un commentaire affirmait déjà un « port
dédié », mais seulement dédié au sein de son propre fichier, pas de toute
la suite. Corrigé en lui donnant un port réellement unique (`47847`,
vérifié par recherche sur l'ensemble des tests) ; suite complète rejouée
deux fois de suite, 896/896 à chaque fois.

**Vérification finale** : 896/896 tests backend, 182 tests web, 114 tests mobile ; TS/ESLint/
build web propres ; TS mobile propre ; migrations rejouées en aller-retour
(`alembic downgrade -1` / `upgrade head`) ; cycle sauvegarde/restauration
testé manuellement. Aucune suite E2E pilotée par navigateur (Playwright/
Cypress) n'existe dans ce dépôt — seule la suite d'intégration backend
(API réelle, base réelle, via `TestClient`) en tient lieu ; à considérer
pour V2 si le besoin devient réel.

## Mise à jour de ce document

- À réviser à chaque jalon (M1 → M5) et chaque fois qu'une fonctionnalité concurrente
  significative est identifiée (nouvelle recherche, démo, retour client).
- Toute nouvelle ligne suit le processus d'évaluation en 6 étapes ci-dessus et reçoit
  une décision KEEP / REFACTOR / REPLACE / ADD / DEFER explicite et justifiée.
- Ne jamais ajouter une ligne juste pour « faire aussi bien » sur le nombre de
  fonctionnalités : seule la valeur réelle pour la vision Physical Asset Intelligence &
  Automation OS compte.
