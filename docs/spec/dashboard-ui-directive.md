# Directive transversale — architecture UI, Global Command Center et dashboard

Formulée par Mohamed le 30 septembre 2026, en complément du cahier des charges, de la
vision cible (ADR 004), de l'Architecture Addendum V2 (ADR 012), de la directive de
langage produit (ADR 013) et de la directive interfaces/Command Center du 27 septembre
2026 (ADR 014, `docs/spec/command-center-ux-directive.md`). Reprise ici **mot pour
mot, intégralement** (contrairement au résumé entre crochets de la directive du 27
septembre : une directive aussi précise sur le vocabulaire, les noms de composants et
l'ordre des sections perd trop en étant résumée) — voir la section « Impact
architectural et plan » plus bas pour l'audit de l'existant et les décisions prises.

---

DIRECTIVE PRODUIT / ARCHITECTURE UI / DASHBOARD — À APPLIQUER MAINTENANT

Prends la maquette actuelle comme base officielle de direction visuelle du produit. Ne repars pas de zéro.

L'objectif est maintenant de transformer cette direction en une interface produit cohérente, exploitable, industrialisable et réellement utile à l'exploitation terrain.

Nous construisons l'interface opérationnelle d'un système d'exploitation intelligent des actifs physiques.

==================================================
1. DIRECTION VISUELLE À FIGER
==================================================

Page de connexion :
- univers dark premium
- ambiance control room / infrastructure / supervision
- bleu nuit profond
- cyan / bleu électrique
- blanc cassé
- esthétique sobre, industrielle, technologique, internationale

Application après connexion :
- interface principalement claire ou semi-claire
- forte lisibilité pour utilisation quotidienne
- adaptée aux grands écrans de supervision
- cohérence visuelle avec la page de connexion
- éviter toute esthétique "IA générique"

Ne pas tout redessiner.
Partir de l'existant et auditer chaque élément avec :
KEEP / REFACTOR / REPLACE / ADD

==================================================
2. IDENTITÉ DE MARQUE
==================================================

ENORYX reste un nom provisoire pour le moment.

Ne coupler aucune architecture, classe, package, route, API, variable, base de données ou composant au nom de marque.

Le logo actuel en forme d'atome est provisoire.

Prévoir l'interface pour qu'un nouveau logo puisse être remplacé sans refonte.

Le futur symbole devra représenter de façon abstraite :
Physical Asset + Connectivity + Digital Twin + Intelligence

Le symbole doit fonctionner :
- en favicon
- sur mobile
- dans la Web App
- sur une Edge Box
- sur un grand écran de supervision
- en monochrome
- en light/dark

Une inspiration malienne pourra être intégrée plus tard dans la géométrie, de manière subtile, sans drapeau, carte ou folklore explicite.

==================================================
3. NETTOYAGE IMMÉDIAT DE L'UI
==================================================

Supprimer de l'application finale tous les textes de maquette tels que :

PAGE DE CONNEXION (SEULE PAGE PUBLIQUE)
EN-TÊTE DE L'ACCUEIL (INTERFACE CLAIRE)

Ne jamais exposer les identifiants techniques de rôles tels que :

admin_tenant

Les mapper vers des libellés humains :

Administrateur
Responsable d'exploitation
Technicien
Responsable énergie
Observateur

Les permissions réelles restent imposées côté serveur.

==================================================
4. PAGE DE CONNEXION
==================================================

Simplifier la page.

Structure cible :

[logo]

ENORYX

Physical Asset Intelligence OS

Supervisez. Comprenez. Optimisez vos actifs physiques.

[ Se connecter ]

Éviter les informations inutiles avant authentification.

Pas de menus inutiles.
Pas de données internes.
Pas de rôle affiché avant authentification.

==================================================
5. LANGAGE D'ÉTAT UNIVERSEL
==================================================

Créer un composant partagé et centralisé pour tous les états opérationnels.

Vocabulaire cible :

Normal
Attention
Critique
Hors ligne
Donnée ancienne
Inconnu
Maintenance

Ce vocabulaire doit être identique dans :

Dashboard
Sites
Bâtiments
Systèmes
Équipements
Alarmes
Maintenance
Énergie
Edge
Plans/BIM
Mobile

Chaque état doit disposer d'un token partagé :

status
label
severity
icon
color token
accessibility label

Ne jamais coder les couleurs directement dans les pages.

==================================================
6. ARCHITECTURE UI
==================================================

Construire autour de composants réutilisables, pas autour de pages indépendantes.

Composants prioritaires :

AppShell
Navigation
TopBar
StatusBadge
AssetCard
MetricCard
AlarmCard
Timeline
DataQualityIndicator
ConnectivityIndicator
EmptyState
SkeletonState
PermissionGuard

Tous doivent supporter :

responsive
dark/light tokens
accessibilité
FR/EN
loading states
error states
empty states
permission states

==================================================
7. NAVIGATION PRODUIT
==================================================

Conserver cette structure :

Vue globale
Sites & bâtiments
Plans & BIM
Équipements
Télémétrie
Alarmes & incidents
Maintenance
Énergie & durabilité
Automatisation
Edge & connectivité
Analyses & rapports
Documents
Utilisateurs & accès
Paramètres

Ne pas créer de modules isolés.

La navigation doit permettre le drill-down :

Organisation
→ Site
→ Bâtiment
→ Zone
→ Système
→ Équipement
→ Alarme / Télémétrie
→ Timeline
→ Intervention

==================================================
8. DASHBOARD / GLOBAL COMMAND CENTER
==================================================

Le dashboard principal est une priorité produit.

Il doit fonctionner comme une tour de contrôle opérationnelle, pas comme une page marketing.

Il doit permettre de répondre immédiatement à :

Que se passe-t-il ?
Où ?
Depuis quand ?
Quelle gravité ?
Quel impact ?
Quelle action est possible ?
Quelle donnée est fiable ou non ?

==================================================
9. STRUCTURE DU DASHBOARD PRINCIPAL
==================================================

BLOC 1 — ÉTAT GLOBAL

Afficher si les données existent réellement :

- Sites supervisés
- Équipements supervisés
- Équipements critiques
- Équipements hors ligne
- Alarmes actives
- Interventions ouvertes
- Edge connectés
- Edge hors ligne

Chaque KPI doit être cliquable.

Un clic doit ouvrir la vue filtrée correspondante.

==================================================
10. BLOC CARTE / PORTEFEUILLE
==================================================

Prévoir :

- carte géographique des sites si la localisation existe
OU
- vue portefeuille structurée si pas de données géographiques

Pour chaque site :

- statut global
- nombre d'alarmes critiques
- disponibilité
- état Edge
- fraîcheur des données
- accès direct au site

Ne pas afficher de carte vide juste pour faire joli.

==================================================
11. BLOC ALARMES PRIORITAIRES
==================================================

Afficher uniquement les alarmes réellement actives.

Pour chaque alarme :

- criticité
- équipement
- système
- site
- description
- ancienneté
- état acquitté / non acquitté
- date de première détection
- dernière occurrence
- lien vers historique

Prioriser les alarmes par impact et criticité.

Éviter une simple liste chronologique non filtrée.

==================================================
12. BLOC MAINTENANCE
==================================================

Afficher :

- interventions en cours
- interventions en retard
- interventions critiques
- dernières clôtures
- équipements avec pannes répétitives
- équipements sans intervention récente si pertinent

Permettre le drill-down vers la timeline équipement.

==================================================
13. BLOC ÉNERGIE
==================================================

Afficher uniquement si les données sont disponibles :

- consommation actuelle
- consommation journalière
- tendance
- comparaison à une baseline réelle
- anomalie énergétique
- production éventuelle
- batterie éventuelle
- groupe électrogène éventuel

Ne jamais inventer :
- économies
- CO2 évité
- ROI
- conformité
- KPI réglementaires

Si la donnée n'existe pas :

Indisponible
Non mesuré
Non connecté
Pas encore suffisamment de données

==================================================
14. BLOC EDGE & CONNECTIVITÉ
==================================================

Afficher :

- Edge online/offline
- dernière synchronisation
- dernière donnée reçue
- qualité des données
- connecteurs actifs
- connecteurs dégradés
- files d'attente offline
- erreurs
- reconnexions
- équipements découverts
- provenance des données

Cette zone doit permettre à l'exploitant de savoir immédiatement si le problème vient :

- de l'équipement
- du réseau
- du connecteur
- de l'Edge
- du cloud
- de la fraîcheur des données

==================================================
15. BLOC SANTÉ DES ACTIFS
==================================================

Afficher la répartition :

Normal
Attention
Critique
Hors ligne
Donnée ancienne
Inconnu
Maintenance

Le graphique doit être cliquable.

Cliquer sur une catégorie ouvre la liste filtrée.

==================================================
16. BLOC ACTIVITÉ RÉCENTE
==================================================

Créer une timeline unifiée.

Elle doit pouvoir regrouper :

- alarmes
- interventions
- observations
- work orders
- changements d'état
- événements Edge
- changements de connectivité
- événements énergétiques
- commandes autorisées
- résultats de commandes
- incidents

La timeline doit être lisible et filtrable.

==================================================
17. DASHBOARD ADAPTÉ AUX RÔLES
==================================================

Ne pas afficher tous les widgets à tout le monde.

Direction :
- portefeuille
- disponibilité
- incidents majeurs
- énergie
- tendances

Responsable exploitation :
- alarmes
- systèmes
- équipements
- connectivité
- état opérationnel

Maintenance :
- interventions
- équipements problématiques
- historique
- alarmes techniques
- checklist

Responsable énergie :
- consommations
- dérives
- baseline
- anomalies
- production

Technicien :
- alertes
- équipements
- QR
- timeline
- interventions
- documentation

==================================================
18. DASHBOARD MULTI-FORMAT
==================================================

Le dashboard doit être utilisable sur :

desktop
tablette
grand écran de supervision

Sur grand écran :
- priorité aux états critiques
- texte lisible à distance
- pas de détails inutiles
- rafraîchissement maîtrisé
- pas de surcharge visuelle

==================================================
19. RÈGLES DASHBOARD NON NÉGOCIABLES
==================================================

Aucun chiffre fictif.

Aucun graphique décoratif.

Chaque KPI doit avoir :
- source
- période
- unité si applicable
- fraîcheur
- état de qualité si pertinent

Chaque carte doit permettre un drill-down.

Si une donnée est absente :
afficher clairement l'absence de donnée.

Ne jamais masquer une donnée stale derrière un chiffre qui semble normal.

==================================================
20. PRIORITÉ D'AFFICHAGE
==================================================

Ordre de priorité opérationnelle :

Alarmes critiques
→ Équipements hors ligne
→ Données stale
→ Interventions
→ Énergie
→ Edge
→ Tendances

Le dashboard doit raconter une situation opérationnelle cohérente.

Il ne doit pas être une collection de widgets indépendants.

==================================================
21. FICHE ÉQUIPEMENT / EQUIPMENT PASSPORT
==================================================

La fiche équipement doit devenir le centre opérationnel de l'actif.

Elle doit regrouper :

- identité
- type
- fabricant
- modèle
- numéro interne
- localisation
- site
- zone
- système
- statut
- connectivité
- dernière donnée
- mesures importantes
- alarmes
- maintenance
- énergie
- documents
- QR
- historique
- timeline

L'utilisateur doit pouvoir comprendre l'état d'un équipement en quelques secondes.

==================================================
22. TIMELINE
==================================================

La timeline doit être un composant central partagé.

Elle doit permettre de comprendre :

- ce qui s'est passé
- quand
- sur quel actif
- pourquoi si connu
- quelle action a suivi
- quel résultat a été observé

Ne jamais supprimer l'historique utile.

==================================================
23. CONFIANCE DANS LES DONNÉES
==================================================

Chaque donnée terrain importante doit pouvoir exposer :

source
provenance
unité
timestamp
fraîcheur
qualité
dernière mise à jour
connecteur
Edge source si applicable

L'utilisateur doit distinguer visuellement :

valeur observée
état désiré
commande envoyée
commande reçue
commande confirmée
état réellement observé après commande

Ne jamais donner l'impression qu'un équipement a exécuté une action simplement parce qu'une commande a été envoyée.

==================================================
24. MODÈLE ALARMES / INCIDENTS
==================================================

Conserver une séparation claire entre :

State
Event
Policy
Alert
Incident

Éviter de tout appeler "alarme".

Une perte réseau, une anomalie énergétique, un défaut équipement et un incident métier ne sont pas nécessairement la même chose.

==================================================
25. EDGE & OT
==================================================

La page Edge & Connectivity doit devenir une vraie console opérationnelle.

Elle doit afficher :

- identité Edge
- statut
- version
- dernière communication
- dernière synchronisation
- connecteurs
- protocoles
- équipements découverts
- qualité
- erreurs
- reconnexions
- offline queue
- backlog
- provenance
- diagnostics

BACnet doit rester READ ONLY en V1.

Aucun écran UI ne doit permettre une écriture simplement parce que le backend pourrait techniquement l'accepter.

==================================================
26. MOBILE
==================================================

Ne pas reproduire tout le desktop.

Mobile doit être orienté terrain.

Priorités :

- alertes
- recherche équipement
- scan QR
- passeport équipement
- timeline
- interventions
- checklists
- photos
- historique
- documents
- offline
- sync

Prévoir plus tard les commandes autorisées uniquement si les politiques de sécurité sont prêtes.

==================================================
27. AUTOMATISATION / CONTROL
==================================================

Séparer clairement :

OBSERVE
UNDERSTAND
DECIDE
AUTHORIZE
EXECUTE
VERIFY
LEARN

L'IA ne doit jamais contrôler directement un équipement critique.

Toute commande future doit passer par :

Authorization
→ Policy & Safety
→ Command
→ Audit
→ Execution
→ Verification

L'UI doit refléter cette chaîne.

==================================================
28. SÉCURITÉ
==================================================

Contraintes non négociables :

Multi-tenant
RBAC
ABAC
permissions côté serveur
aucun secret dans le frontend
tenant isolation
audit
logs de sécurité
session management
least privilege

Un Platform Owner ou Super Admin ne doit pas automatiquement disposer de droits de contrôle physique.

Les droits de contrôle doivent rester explicitement accordés par site/client.

==================================================
29. PERFORMANCE
==================================================

Prévoir :

pagination
lazy loading
cache
downsampling
aggregation
virtualization si nécessaire
chargement progressif
requêtes bornées
limitation des gros graphiques

Ne jamais charger des millions de points télémétriques directement dans le navigateur.

==================================================
30. GRAPHIQUES
==================================================

Chaque graphique doit afficher clairement :

unité
période
timezone
qualité des données
source
fraîcheur
granularité

Prévoir des vues :

temps réel si disponible
1 h
24 h
7 jours
30 jours
personnalisée

Downsampling obligatoire sur longue période.

==================================================
31. EMPTY / ERROR / OFFLINE STATES
==================================================

Créer des états dédiés pour :

Aucune donnée
Non connecté
Donnée ancienne
Source indisponible
Erreur API
Permission insuffisante
Edge hors ligne
Synchronisation en cours
Historique vide
Équipement non configuré

Ne pas laisser des panneaux vides.

==================================================
32. FR / EN
==================================================

Toutes les chaînes visibles doivent utiliser l'i18n.

Aucun texte métier hardcodé directement dans les composants.

Prévoir :
FR
EN

Architecture extensible plus tard.

==================================================
33. ACCESSIBILITÉ
==================================================

Prévoir :

contraste suffisant
navigation clavier
focus visible
labels accessibles
icônes avec texte ou tooltip
ne jamais dépendre uniquement de la couleur
support zoom
responsive correct

==================================================
34. OBSERVABILITÉ PRODUIT
==================================================

Ajouter une observabilité de l'application elle-même :

- erreurs frontend
- erreurs API
- temps de réponse
- latence
- échecs de chargement
- taux d'erreur
- connectivité
- état Edge
- provenance des incidents techniques

==================================================
35. QUALITÉ PRODUIT
==================================================

Pour chaque fonctionnalité, auditer systématiquement :

Backend
API
Web
Mobile
Edge
Tests
Docs

Une fonctionnalité backend/API sans interface humaine alors qu'elle en nécessite une doit être marquée PARTIAL.

==================================================
36. PAGES À FINALISER DANS CET ORDRE
==================================================

1. Global Command Center
2. Equipment Passport
3. Unified Timeline
4. Alarms & Incidents
5. Maintenance
6. Energy
7. Edge & Connectivity
8. Sites & Buildings
9. Telemetry
10. Documents
11. Users & Access
12. Spatial / BIM
13. Automation

==================================================
37. RÈGLES DE DONNÉES
==================================================

Aucun KPI fictif.

Aucune donnée demo affichée comme réelle.

Aucune baseline inventée.

Aucune prédiction présentée comme vraie sans données historiques suffisantes.

Aucune conformité réglementaire inventée.

Aucun état équipement supposé.

Si une donnée est inconnue :
UNKNOWN

Si elle est trop ancienne :
STALE

Si la source est inaccessible :
OFFLINE

==================================================
38. MODE D'EXÉCUTION
==================================================

Ne me demande pas de validation pour :

- décisions UI réversibles
- refactor local
- renommage interne sans breaking change
- composants réutilisables
- amélioration UX
- accessibilité
- tests
- documentation
- corrections visuelles
- responsive
- i18n

Décide, implémente, teste et documente.

Ne t'arrête que pour :

- achat
- nouveau compte externe
- secrets
- dépendance propriétaire structurante
- changement architectural majeur
- breaking API
- breaking contract
- baisse de sécurité
- données terrain réelles manquantes
- matériel physique manquant
- besoin d'autorisation client/site

Toute dépendance externe doit devenir :

BLOCKED_EXTERNAL

mais le reste du développement continue.

==================================================
39. DÉFINITION DE DONE
==================================================

Pour chaque fonctionnalité importante, vérifier :

Backend ✅
API ✅
Web ✅
Mobile si pertinent ✅
Edge si pertinent ✅
Tests ✅
Docs ✅
Error states ✅
Empty states ✅
Permissions ✅
i18n ✅
Responsive ✅
Observability ✅

Ne pas annoncer DONE si seul le backend est terminé.

==================================================
40. OBJECTIF PRODUIT
==================================================

L'utilisateur doit toujours pouvoir répondre à :

Quels actifs sont supervisés ?
Quel est leur état ?
Qu'est-ce qui demande mon attention ?
Pourquoi ?
Depuis quand ?
Quelle donnée est fiable ?
Quelle donnée est stale ?
Quel système est concerné ?
Quel est l'historique ?
Quelle action est autorisée ?
Qu'est-ce qui s'est réellement passé après l'action ?

La plateforme doit suivre cette logique :

Observe
→ Understand
→ Decide
→ Simulate if needed
→ Authorize
→ Execute
→ Verify
→ Learn

Phrase directrice :

Nous construisons l'interface opérationnelle d'un système d'exploitation des actifs physiques.

Ne construis plus des écrans de démonstration isolés.

Construis un produit cohérent, connecté aux données réelles, exploitable sur le terrain et capable de devenir la couche universelle de supervision, maintenance, énergie, Edge, intelligence et automatisation des actifs physiques.

---

## Impact architectural et plan

### Audit de l'existant (30/09/2026)

Cette directive arrive après plusieurs briques déjà construites ce même jour
(refonte visuelle de l'accueil, écran Edge & Connectivity, identité Enoryx). Elle ne
demande pas de tout recommencer (section 1 : « ne pas tout redessiner ») — l'audit
ci-dessous suit exactement sa propre grille.

**Section 1 (direction visuelle)** — ⚠️ Partiellement conforme. La page de connexion
(`apps/web/src/app/login/page.tsx`) a déjà l'univers dark premium demandé (bleu nuit
`#050b1a`, dégradé cyan/bleu électrique, sobre) — **KEEP**. L'application après
connexion a déjà un fond clair cohérent (`apps/web/src/lib/formStyles.ts`, refonte du
27-30/09) — **KEEP**. Le reste des pages (registre, ordres de travail, fiche
équipement) n'a pas encore reçu ce traitement — **REFACTOR progressif**, déjà noté
dans `feature-benchmark-matrix.md` (ligne « Design System commun »).

**Section 2 (identité de marque)** — ❌ Non conforme, corrigé immédiatement
(30/09/2026) : le composant `EnoryxMark.tsx` couplait le nom de marque au nom du
composant, contrairement à l'exigence explicite de cette section. **REPLACE** →
`BrandMark.tsx`, aucune autre référence au nom « Enoryx » dans un identifiant de
code (route, classe, table). Le nom reste dans les catalogues i18n uniquement
(`common.app_name`), qui sont faits pour changer sans toucher au code.

**Section 3 (nettoyage UI)** — ❌ Deux points trouvés, corrigés immédiatement :
1. Les libellés « PAGE DE CONNEXION (SEULE PAGE PUBLIQUE) » et « EN-TÊTE DE
   L'ACCUEIL (INTERFACE CLAIRE) » cités dans la directive n'existaient que dans
   l'aperçu de maquette envoyé à Mohamed (un artefact de démonstration, jamais du
   code livré) — confirmé qu'aucune trace n'existe dans `apps/web/src`. Rien à
   corriger dans le dépôt, signalé pour mémoire.
2. Le rôle technique brut (`admin_tenant`, etc.) s'affichait réellement, sans
   traduction, dans l'en-tête web (`page.tsx`, `roles.join(", ")`) et l'accueil
   mobile (`index.tsx`, même motif) — **REFACTOR**, nouveau catalogue de libellés
   humains pour les trois rôles qui existent réellement côté API
   (`admin_tenant`, `responsable_exploitation`, `technicien` — voir
   `app/routers/*.py`). « Responsable énergie » et « Observateur », cités par la
   directive, n'ont pas encore de rôle API correspondant : **DEFER**, jamais un
   libellé pour un rôle qui n'existe pas côté serveur (même principe que le
   vocabulaire d'équipement, « on n'invente jamais »).

**Section 4 (page de connexion)** — ⚠️ Proche de la cible, un écart : le sous-titre
affiché avant authentification (« Console du responsable d'exploitation ») nomme un
rôle avant la connexion, contrairement à l'exigence explicite. **REFACTOR** →
remplacé par l'accroche neutre de la directive elle-même : « Supervisez. Comprenez.
Optimisez vos actifs physiques. »

**Sections 5 à 37 (langage d'état universel, architecture en composants partagés,
navigation avec fil d'Ariane, Global Command Center détaillé bloc par bloc, fiche
équipement enrichie, timeline unifiée, confiance dans la donnée, séparation
State/Event/Policy/Alert/Incident, console Edge complète, mobile terrain,
observabilité produit, etc.)** — ❌ **DEFER, ajouté à la feuille de route active**,
pas construit aujourd'hui. Un composant `StatusBadge` partagé portant le vocabulaire
Normal/Attention/Critique/Hors ligne/Donnée ancienne/Inconnu/Maintenance existe déjà
en germe dans les badges de gravité et de communication de la vue Portfolio
(`apps/web/src/app/page.tsx`, `SEVERITY_COLOR`/`COMMUNICATION_COLOR`) : la prochaine
étape naturelle (pas faite aujourd'hui) est de l'extraire en composant partagé plutôt
que de le garder dupliqué par page — cohérent avec la section 6. Le reste (AppShell,
Navigation, TopBar, AssetCard, MetricCard, AlarmCard, Timeline unifiée,
DataQualityIndicator, ConnectivityIndicator, EmptyState, SkeletonState,
PermissionGuard, dashboards par rôle, carte géographique, graphiques avec
downsampling) suit l'ordre de la section 36 (« Pages à finaliser dans cet ordre »),
construit progressivement, jamais en un seul bloc — exactement le principe « ADD
progressif » déjà en vigueur dans `feature-benchmark-matrix.md`.

**Section 38 (mode d'exécution)** — Appliqué à partir de maintenant pour tout ce qui
relève de cette directive : les décisions UI réversibles, renommages internes,
composants réutilisables, accessibilité, i18n, corrections visuelles ne remontent
plus à Mohamed avant d'être faits. Seuls achat, compte externe, secret, dépendance
structurante, changement architectural majeur, breaking change, baisse de sécurité,
donnée/matériel manquant ou autorisation client restent des points d'arrêt — déjà
la pratique suivie depuis le début de ce projet (voir CLAUDE.md), cette section la
rend explicite pour l'UI en particulier.

### Décisions prises immédiatement (30/09/2026)

1. `EnoryxMark.tsx` → `BrandMark.tsx` (section 2).
2. Catalogue de libellés de rôles humains + suppression de l'affichage brut
   (section 3), web et mobile.
3. Sous-titre de la page de connexion remplacé par l'accroche produit neutre
   (section 4).
4. Cette directive et son audit devient la référence versionnée pour la suite du
   chantier « architecture UI / dashboard », comme `command-center-ux-directive.md`
   l'est pour la directive du 27 septembre. `feature-benchmark-matrix.md` y renvoie.

### Feuille de route active (sections 5 à 37, DEFER explicite, jamais perdue de vue)

Dans l'ordre de la section 36, chaque étape suit KEEP (garder ce qui existe déjà :
données, endpoints) + ADD (l'écran/composant manquant) — jamais une réécriture :

1. **Global Command Center** — étoffer la vue Portfolio existante (blocs alarmes
   prioritaires, maintenance, énergie, santé des actifs, activité récente) plutôt
   que la remplacer.
2. **Equipment Passport** — la fiche équipement (`/registre/{id}`) existe déjà avec
   plusieurs blocs (passeport, timeline partielle, règles, énergie) : à consolider
   selon la liste de la section 21, pas à recréer.
3. **Unified Timeline** — `GET /graph/nodes/{id}/timeline` existe déjà
   (`app/timeline.py`) ; en faire un composant web partagé plutôt qu'une section
   isolée de la fiche équipement.
4. Alarms & Incidents, 5. Maintenance, 6. Energy, 7. Edge & Connectivity (déjà un
   premier écran, à enrichir selon la section 25), 8. Sites & Buildings, 9.
   Telemetry, 10. Documents, 11. Users & Access, 12. Spatial/BIM, 13. Automation —
   dans cet ordre, un écran à la fois.
