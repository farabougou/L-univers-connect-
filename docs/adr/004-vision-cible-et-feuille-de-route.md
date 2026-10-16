# ADR 004 — Vision cible et feuille de route d'extension

## Statut

Acceptée (22 septembre 2026).

## Contexte

Le 22 septembre 2026, Mohamed a précisé la vision long terme du produit : un
**Physical Asset Intelligence & Automation OS**, une plateforme SaaS universelle
capable de superviser, maintenir, optimiser, automatiser et, lorsque c'est autorisé et
sûr, commander à distance des équipements physiques — au-delà du seul wedge CVC
tertiaire, avec vocation à couvrir bâtiments publics, logements, industrie, énergie,
eau, data centers et équipements distribués. Le texte complet, mot pour mot, est
conservé dans
[`docs/spec/vision-cible-physical-asset-intelligence-automation-os.md`](../spec/vision-cible-physical-asset-intelligence-automation-os.md).

Cette vision ajoute 14 briques fonctionnelles à terme (modèle d'actifs universel et
jumeaux numériques, GTB/GTC natif, moteur d'automatisation, commande distante
sécurisée, edge runtime, couche de connecteurs multi-protocoles, couche sémantique
universelle, découverte/auto-mapping sémantique, GMAO, énergie et durabilité, IA/ML,
simulation, intelligence de flotte, et zero-trust/sûreté). La consigne explicite de
Mohamed est de ne pas réécrire le projet existant, mais de l'auditer et de le faire
évoluer progressivement.

## Décision

**Audit du code existant, classé KEEP / REFACTOR / ADD** (aucun REPLACE identifié —
rien de ce qui existe ne contredit la vision cible) :

- **KEEP tel quel** : isolation multi-tenant par RLS forcée, authentification et rôles
  Keycloak, journal d'audit chaîné par hachage. Ce sont les fondations de la brique
  Zero-Trust/Sûreté, déjà solides.
- **KEEP le principe, REFACTOR l'étendue** : le modèle à trois niveaux (ProductModel,
  PhysicalUnit, FunctionalLocation, ADR 001) est la bonne base du modèle d'actifs
  universel ; il lui manque un typage explicite des niveaux de hiérarchie
  (Facility/Building/Zone/System) sur FunctionalLocation, à ajouter quand un besoin réel
  l'exigera.
- **ADD** : les 13 autres briques restent entièrement à construire. La plupart
  dépendent d'une couche de connecteurs qui n'existe pas encore.

**Ordre de développement retenu**, du plus proche et moins risqué au plus tardif et
sensible :

1. GMAO minimale (ordres de travail, interventions, alarmes) — construite dans la
   foulée de cette ADR, sans dépendance nouvelle, en s'appuyant sur le registre
   d'actifs existant.
2. Application technicien hors ligne (M1.3 du plan initial).
3. Squelette de bout en bout (M2), formalisation Brick Schema une fois 3 catégories
   réelles observées, typage de la hiérarchie FunctionalLocation si un vrai besoin
   multi-portefeuilles apparaît.
4. Télémétrie en lecture seule et premier connecteur réel (M3), Edge Runtime minimal.
5. Edge durci, découverte/auto-mapping sémantique (M4).
6. **Sous condition explicite** (voir plus bas) : pipeline de sûreté des commandes
   (niveaux C0–C4, séquence Observe → Understand → Decide → Simulate → Authorize →
   Execute → Verify → Learn), puis commande distante sécurisée, puis moteur
   d'automatisation.
7. Au fil de l'eau, une fois assez de données réelles accumulées : IA/ML, simulation,
   intelligence de flotte.

## Point de sûreté : tension avec la règle non négociable 1

La règle non négociable 1 du projet interdit aujourd'hui tout code qui écrit vers un
équipement (niveau C0, lecture seule). La vision cible inclut explicitement la commande
distante. **Cette ADR ne lève pas cette règle.** Elle ne sera modifiée que par une
décision explicite et documentée de Mohamed, au moment où le projet atteindra l'étape
6 ci-dessus — pas silencieusement à l'occasion d'une fonctionnalité qui s'en
approcherait. D'ici là, toute brique construite reste strictement en observation,
recommandation ou planification, jamais en exécution physique.

## Conséquences

- Le développement continue par petites étapes testées, exactement comme pour la
  Phase 0 et M1.1/M1.2 : chaque nouvelle table suit le même schéma (tenant_id, RLS
  forcée, test d'isolation), chaque action sensible passe par le journal d'audit.
- Aucune dépendance à un fabricant ou un protocole n'est ajoutée avant que la couche de
  connecteurs (brique 6) ne soit conçue comme un adaptateur générique (règle non
  négociable 8) ; en attendant, rien n'est codé en dur pour un protocole particulier.
- Le module `app/routers.py`, devenu trop large avec l'arrivée d'un second domaine
  métier, est réorganisé en package `app/routers/` (un fichier par domaine :
  `assets.py`, `maintenance.py`) — pur regroupement, aucun comportement changé.
