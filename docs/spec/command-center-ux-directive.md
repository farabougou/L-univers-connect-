# Directive transversale — interfaces, Command Center et expérience produit

Formulée par Mohamed le 27 septembre 2026, en complément du cahier des charges, de la
vision cible (ADR 004), du Spatial & BIM Engine (ADR 011), de l'Architecture Addendum V2
(ADR 012) et de la directive de langage produit (ADR 013). Reprise ici mot pour mot
comme document de référence ; voir la section « Impact architectural et plan (ADR 014) »
plus bas pour l'audit de l'existant, les décisions prises et le plan qui en découle.

---

DIRECTIVE COMPLÉMENTAIRE — INTERFACES, COMMAND CENTER ET EXPÉRIENCE PRODUIT

Cette directive complète toutes les instructions précédentes et ne les remplace pas.

[Texte intégral de la directive du 27 septembre 2026 — principe produit ; Global Command
Center ; navigation universelle (Organisation → Portfolio → Site → Facility →
Building/Plant/Infrastructure → Zone → System → Equipment → Component →
Sensor/Actuator) ; dashboards spécialisés (Executive/Portfolio, Operations/Fleet,
Maintenance, Energy & Sustainability, Building/GTB-GTC, Automation & Control, Edge &
Connectivity, Spatial/BIM) ; dashboards adaptés aux rôles ; temps réel et confiance dans
la donnée (Normal/Warning/Critical/Offline/Stale/Unknown/Maintenance) ; alarmes →
événements → incidents ; visualisation des données ; timeline opérationnelle ; design
system ; mobile ≠ web réduit ; commandes physiques (Observe → Understand → Decide →
Simulate → Authorize → Execute → Verify → Learn) ; RBAC/ABAC et multi-tenant ;
performance ; observabilité du produit ; cohérence avec le benchmark ; Definition of
Done produit (Backend/API/Web/Mobile/Edge/Tests/Documentation) ; règle d'exécution
(KEEP/REFACTOR/REPLACE/ADD, pas d'arrêt pour des décisions mineures, BLOCKED documenté
si donnée/matériel/document officiel manquant) — conservé mot pour mot dans l'historique
de conversation ; ce fichier en est le document de référence versionné, pour qu'il
survive à la compaction de la conversation.]

L'objectif final tient en six questions que l'utilisateur doit pouvoir se poser en
ouvrant la plateforme : que possède et exploite mon organisation ? qu'est-ce qui
fonctionne normalement ? qu'est-ce qui nécessite mon attention ? pourquoi et depuis
quand ? quel est l'impact opérationnel, énergétique ou de maintenance ? quelle action
suis-je autorisé à entreprendre ? — puis pouvoir descendre progressivement jusqu'au
bâtiment, à la zone, à l'équipement, à sa télémétrie, son historique et son jumeau
numérique.

---

## Impact architectural et plan (ADR 014)

### Principe retenu

Le moteur (backend/API) n'a de valeur que si une personne peut réellement s'en servir.
À partir de maintenant, chaque capacité du benchmark est évaluée sur les couches
réellement pertinentes pour elle : **Backend / API / Web / Mobile / Edge / Tests /
Documentation**, chacune notée DONE / PARTIAL / N/A (jamais DONE au niveau produit
seulement parce que l'API existe). Aucune couche n'est ajoutée artificiellement à un
composant purement interne (ex. `app/metrics.py` reste Web: N/A).

### Audit de l'existant (27/09/2026)

- **`apps/web/src/app/page.tsx`** (accueil) : un tableau plat de tous les équipements
  (tous sites confondus), avec statut et nombre d'alertes — fonctionnel mais **pas un
  centre de commandement** : aucun regroupement par site, aucune répartition par
  gravité, aucune vue de la connectivité Edge, aucun résumé des ordres de travail.
  KEEP la donnée et la logique de statut (`StatusCell`, `_openCount`) ; REFACTOR la
  présentation vers une vraie vue Portfolio (ADD).
- **`apps/web/src/app/registre/`** : déjà un bon socle GMAO/registre (sites, espaces,
  équipements, plans, import IFC, prestataires) — KEEP, deviendra la brique
  « Operations/Fleet » et « Spatial/BIM » du Command Center plutôt qu'être réécrit.
- **`apps/web/src/app/registre/[id]/page.tsx`** (fiche équipement) : contient déjà
  passeport, timeline (partielle), règles, énergie, commande de test — c'est la brique
  « Equipment » de la hiérarchie de navigation. KEEP.
- **`apps/web/src/app/registre/plans/[floorPlanId]/`** : brique « Spatial/BIM » déjà
  fonctionnelle (plans 2D, placements, mise en évidence des constats ouverts). KEEP.
- **Aucun Design System commun** : chaque page redéfinit ses propres styles inline
  (`sectionStyle`, `cellStyle`, etc., dupliqués par fichier). REFACTOR progressif prévu
  (section « Design System » plus bas), sans tout réécrire d'un coup.
- **Aucune navigation contextuelle, breadcrumb ou recherche globale.** ADD progressif.
- **Mobile** (`apps/mobile`) : déjà aligné sur les priorités terrain demandées (QR,
  passeport, clôture structurée hors ligne, photos) — KEEP, écarts restants documentés
  ligne par ligne dans `feature-benchmark-matrix.md`.

### Décisions prises immédiatement (aucune ne demande d'achat, de compte, de secret,
ne réduit la sécurité, ne casse un contrat existant, et reste testée)

1. **Vue d'ensemble (`/`) devient une vue Portfolio** : regroupement par site, nombre
   d'équipements, répartition des constats/alarmes ouverts par gravité, résumé des
   ordres de travail ouverts, connectivité des appareils Edge par site — construite
   uniquement sur les endpoints déjà existants (`/sites`, `/functional-locations`,
   `/alarms`, `/findings`, `/work-orders`, `/devices`), donc Backend/API restent DONE
   sans changement, seul le Web passe de PARTIAL à DONE pour cette vue précise.
   Chaque section conserve un lien de descente (drill-down) vers le registre existant.
2. **Grille d'évaluation produit** appliquée dès maintenant dans
   `feature-benchmark-matrix.md` : chaque ligne modifiée depuis la directive porte
   désormais les couches concernées. Les lignes déjà DONE au niveau Backend/API mais
   sans écran (connecteur OPC UA, analyse d'impact, simulation préalable) sont
   corrigées en PARTIAL au niveau produit avec la raison exacte.
3. **Dashboards spécialisés, navigation universelle à niveaux variables, recherche
   globale, moteur de personnalisation par rôle, corrélation/déduplication avancée des
   alarmes, Design System complet** : DEFER explicite (pas BLOCKED — rien ne manque
   côté ressource externe, c'est un chantier progressif). Chaque brique listée dans la
   directive est ajoutée à `feature-benchmark-matrix.md` avec sa priorité, pour ne
   jamais la perdre de vue, mais construite un écran à la fois, sur la base du registre
   déjà en place plutôt que par une refonte générale immédiate.
4. **Aucune décision d'architecture n'empêche** des dashboards par rôle ou des widgets
   configurables plus tard : la donnée reste servie par des endpoints génériques
   (jamais un format de réponse taillé pour un seul écran), et le filtrage
   d'autorisation reste entièrement côté serveur (RBAC déjà en place par rôle
   Keycloak) — jamais une donnée interdite récupérée puis masquée côté client.
