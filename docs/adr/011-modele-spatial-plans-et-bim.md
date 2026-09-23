# ADR 011 — Modèle spatial, plans 2D et BIM/IFC (Spatial & BIM Engine)

## Statut

Proposée (23 septembre 2026). Aucune ligne de code n'est écrite avant l'accord de
Mohamed sur ce document.

## Contexte

Le 23 septembre 2026, Mohamed a ajouté au cahier des charges une exigence **Spatial &
BIM Engine** (texte complet, mot pour mot :
[`docs/spec/spatial-bim-engine.md`](../spec/spatial-bim-engine.md)). En résumé :
représenter les bâtiments dans l'espace (Portfolio → Site → Building → Floor →
Zone/Room → System → Equipment → Component → Sensor/Actuator), importer des plans 2D
et, quand ils existent, des modèles BIM/IFC, afficher à terme les données temps réel sur
le plan, puis passer à la 3D, **sans jamais créer un second modèle d'actifs** : le plan
ne fait que référencer les actifs existants.

Le cahier des charges prévoyait déjà cette direction : hiérarchie universelle
(Partie I, section 3), relations `contains` / `located_in` / `monitored_by` dans le
graphe d'actifs, Brick Schema comme vocabulaire et IFC pour la structure du bâtiment
(ADR 001).

## Ce qui existe déjà (audit)

| Élément existant | Rôle aujourd'hui | Décision | Pourquoi |
|---|---|---|---|
| `tenants` + RLS forcée partout | Isolation entre clients | **KEEP** | Chaque nouvelle table spatiale suit le même schéma (tenant_id, RLS, test d'isolation). |
| `sites` | Racine d'une installation | **KEEP** | Devient la racine de l'arbre spatial. Aucun changement de structure nécessaire. |
| `functional_locations` (arbre `parent_id`, `site_id`, `code`, `name`) | Position technique où un exemplaire est installé | **KEEP le rôle, REFACTOR par ajout** | C'est la bonne notion pour System → Equipment → Component (norme ISO 14224, SAP PM). Il lui manque deux colonnes, ajoutées sans rien casser : `space_id` (dans quelle pièce/zone se trouve cette position) et `kind` (système, équipement, composant). |
| `product_models` / `physical_units` / `functional_location_assignments` | Identité à trois niveaux, historique bitemporel | **KEEP** | Déjà l'« identifiant universel unique » demandé. Le plan référencera ces identifiants, jamais une copie. |
| `measurements` (M2) | Télémétrie en lecture seule | **KEEP, REFACTOR par ajout plus tard** | Ajouter `point_id` (capteur précis) avant le premier connecteur réel (M3). |
| `alarms`, `work_orders`, `interventions` | GMAO | **KEEP** | Déjà rattachés à une position fonctionnelle : ils apparaîtront sur le plan via la pièce de cette position, sans changement. |
| Stockage S3 des photos (ADR 006) | Fichiers hors base | **KEEP, réutilisé** | Les fichiers de plans et IFC suivent le même mécanisme (URL pré-signées, préfixe par tenant). |
| Rôles Keycloak (ADR 003) | Autorisations | **KEEP** | Le futur ReBAC utilisera l'arbre spatial comme périmètre (site, bâtiment, zone) : ce document le prépare sans l'introduire. |
| Modèle spatial (bâtiment, étage, pièce, zone) | **Absent** | **ADD** | Voir la décision ci-dessous. |
| Plans 2D, placements, import IFC, propositions à valider | **Absents** | **ADD** | Voir la décision ci-dessous. |

**Aucun REPLACE.** Rien de l'existant ne contredit l'exigence ; tout s'ajoute autour du
cœur d'actifs actuel.

## Décision

### 1. Séparer « où c'est » et « à quoi ça sert » : deux arbres reliés, un seul modèle d'actifs

Exemple concret CVC : une CTA installée au sous-sol (local technique) alimente les
bureaux des étages 1 à 5. Dans un arbre unique, il faudrait choisir : la CTA est-elle
« sous » le local technique ou « sous » le système de ventilation ? Les deux sont vrais.
C'est pourquoi IFC (structure spatiale d'un côté, systèmes de l'autre) et Brick Schema
(Location d'un côté, Equipment/System de l'autre) séparent ces deux notions.

On fait la même chose :

```
ARBRE SPATIAL (nouveau : spaces)          ARBRE TECHNIQUE (existant : functional_locations)
Site                                       Système CVC « Ventilation bureaux »  (kind=system)
 └─ Bâtiment A          (building)          └─ Position CTA-01              (kind=equipment)
     ├─ Sous-sol        (floor)                  ├─ Position ventilateur    (kind=component)
     │   └─ Local CTA   (room) ◄── space_id ─────┘   (occupée par un exemplaire physique
     └─ Étage 1         (floor)                       avec numéro de série, historique conservé)
         └─ Bureau 104  (room)
```

- **`spaces`** (ADD) : Building, Floor, Room, Zone et, pour les autres secteurs, Outdoor
  Area, Plant, etc. Arbre `parent_id` à l'intérieur d'un `site`. Un espace qui disparaît
  (rénovation, fusion de pièces) est clos par `valid_to`, jamais supprimé.
- **`functional_locations.space_id`** (REFACTOR par ajout, colonne facultative) : où se
  trouve physiquement une position. L'équipement installé hérite de cet emplacement ;
  remplacer l'exemplaire ne change rien à l'emplacement, exactement comme aujourd'hui
  pour l'historique.
- **Changer une position d'emplacement n'écrase rien** (règle non négociable 3) : même
  modèle que les statuts d'ordres de travail, une valeur courante plus une table
  d'historique (`functional_location_space_history`) jamais modifiée.
- **`functional_locations.kind`** (REFACTOR par ajout, facultatif) : `system`,
  `equipment`, `component`, pour distinguer System → Equipment → Component de la
  hiérarchie demandée.

Correspondance avec la hiérarchie demandée :

| Niveau demandé | Où il vit | Statut |
|---|---|---|
| Portfolio | futur `portfolios` + `sites.portfolio_id` | ADD différé (règle des trois : dès qu'un client regroupe ses sites) — ajout sans rupture |
| Site | `sites` | existe |
| Building, Floor, Zone/Room | `spaces` | ADD (étape S1) |
| System, Equipment, Component | `functional_locations` (+ `kind`) + exemplaires physiques | existe, complété en S1 |
| Sensor, Actuator, compteur | futur `points` (vocabulaire Brick), rattachés à une position et/ou un espace | ADD en S5, avant le premier connecteur réel (M3) |

**Zones transverses.** Une zone CVC ou un compartiment incendie peut couvrir plusieurs
pièces : ce n'est pas un nœud de l'arbre mais un regroupement. Il sera ajouté (table de
regroupement, équivalent `IfcZone`) au premier cas réel ; ce n'est pas bloquant, car
c'est une table en plus, pas une modification de `spaces`. En attendant, une zone
simple (subdivision d'un étage, un open space) est un espace de type `zone` dans
l'arbre.

**Vocabulaire ouvert.** `space_type` et `kind` sont du texte contrôlé par une liste
côté application alignée sur Brick Schema, pas une énumération figée en base : ajouter
« Plant » pour l'industrie ou « Station » pour l'eau ne demande pas de migration. C'est
ce qui garde le noyau universel.

### 2. L'identité d'abord, la géométrie ensuite (c'est ce qui permet la 3D plus tard)

Un espace ou une position est identifié par son UUID, jamais par une forme ou des
coordonnées. La géométrie est une **représentation** rattachée à cette identité :

- en 2D, un placement sur **une version précise** d'un plan (coordonnées normalisées
  entre 0 et 1 par rapport au plan, donc indépendantes de la résolution de l'image) ;
- en 3D plus tard, la géométrie vient du fichier IFC lui-même, reliée à nos identifiants
  par la table de correspondance (point 4).

Ajouter la 3D consistera donc à ajouter une vue, pas à modifier `spaces` ni le modèle
d'actifs. Pas de PostGIS pour l'instant : les formes sont stockées en JSON
(style GeoJSON). PostGIS pourra s'ajouter si des requêtes géométriques deviennent
nécessaires, sans changer les identités.

### 3. Le plan référence, il ne copie jamais

- **`floor_plans`** (ADD, étape S3) : un fichier (PDF, PNG ou JPEG au départ) rattaché
  à un espace (un étage, ou un bâtiment pour un plan de masse), stocké comme les photos
  (ADR 006), avec numéro de version et empreinte SHA-256. Un nouveau plan crée une
  nouvelle version, jamais un écrasement. SVG et DWG/DXF refusés au départ : le SVG
  peut contenir du code exécutable (risque de sécurité), le DWG est un format
  propriétaire ; ils seront ajoutés derrière un convertisseur si un vrai besoin apparaît.
- **`plan_placements`** (ADD, étape S4) : « tel espace / telle position / tel point est
  dessiné ici sur telle version de plan ». Trois colonnes de référence facultatives
  (`space_id`, `functional_location_id`, `point_id`) avec une contrainte « exactement une
  renseignée » : de vraies clés étrangères, donc impossible de pointer vers un actif
  inexistant ou d'un autre tenant. **Aucun nom, aucune caractéristique d'équipement
  n'est stocké dans le placement** : tout est lu depuis le registre d'actifs.

### 4. Identifiants externes : une seule table de correspondance

**`external_identifiers`** (ADD, étape S6) : relie un identifiant d'un autre système à
notre UUID (`scheme` = `ifc_global_id`, `customer_code`, et plus tard `bacnet_object`,
`haystack_id`…). Une seule table sert à l'IFC, aux imports de fichiers clients et aux
futurs connecteurs M3 : c'est ce qui évite un « modèle BIM » parallèle. Unicité par
(tenant, scheme, identifiant externe).

### 5. Tout import automatique passe par des propositions validées par un humain

Import IFC, analyse IA d'un plan, import de tableur : tous produisent des
**propositions** (`import_batches` + `import_proposals`, statut proposée / acceptée /
modifiée / rejetée, qui a validé et quand). Seule une proposition acceptée crée une vraie
entité, **par les mêmes fonctions que la saisie manuelle** (mêmes contrôles, même RLS,
même journal d'audit). L'entité garde la trace de son origine. Règle pour le futur :
une automatisation ou une commande ne pourra jamais s'appuyer sur une donnée restée à
l'état de proposition.

La lecture des fichiers IFC (norme ouverte ISO 16739) se fait derrière un adaptateur, en
tâche de fond, jamais pendant une requête web (règle non négociable 8 : la bibliothèque
de lecture, par exemple IfcOpenShell, reste remplaçable). Ordre d'import : d'abord la
structure spatiale (IfcSite, IfcBuilding, IfcBuildingStorey, IfcSpace → `spaces`), puis
les équipements techniques (→ propositions de positions fonctionnelles).

### 6. Sécurité et vie privée

- **Voir n'est pas commander.** Le plan n'affiche que ce que l'utilisateur a le droit de
  lire. Les actions proposées depuis un élément viennent d'un point d'API dédié qui
  calcule les actions autorisées (aujourd'hui : voir l'historique, créer un ordre de
  travail, lever une alarme). L'interface ne déduit jamais une action du simple fait
  qu'un élément est affiché. Aucune action de commande n'existe (règle non négociable
  1, ADR 004) ; le jour où elle existera, elle passera par la chaîne
  Observe → … → Authorize → Execute → Verify, pas par le plan.
- **Droits.** Lecture des plans : mêmes rôles que le registre. Création et modification
  de l'arbre spatial, des plans et des placements : `responsable_exploitation` et
  `admin_tenant` (un rôle `integrateur` s'ajoutera au premier vrai intégrateur).
  Chaque création, modification ou validation écrit une entrée dans le journal d'audit.
- **Les plans sont des documents sensibles** (sûreté des locaux) : préfixe de stockage
  par tenant, URL pré-signées de courte durée, jamais de lien public.
- **Occupation** : uniquement agrégée par zone, jamais individuelle, avec un seuil
  minimal pour empêcher de déduire une personne ; cohérent avec l'ADR 009 et le RGPD.

## Ordre de mise en œuvre

Conforme à la priorité demandée (Spatial Data Model → Floor Plan 2D → Asset Mapping →
Real-Time Overlay → BIM/IFC avancé → 3D), une étape à la fois :

1. **S1 — Modèle spatial (API)** : `spaces`, `functional_locations.space_id` + historique,
   `functional_locations.kind`, routes de création/lecture, tests (isolation entre
   tenants, rien n'est écrasé, un espace enfant reste dans le même site, pas de cycle).
2. **S2 — Construction manuelle dans la console web** : Bâtiment → Étage → Pièce →
   équipement, sans aucun plan (exigence 4).
3. **S3 — Plans 2D** : envoi PDF/PNG/JPEG, versions, affichage (pdf.js côté navigateur,
   aucune bibliothèque cartographique propriétaire).
4. **S4 — Placement des actifs sur le plan** : éditeur (pièces en polygones, équipements
   en points), statut proposé/validé.
5. **S5 — Points (capteurs, actionneurs, compteurs) et affichage temps réel** : aligné sur
   le premier connecteur réel (M3). Les points de commande sont modélisés mais forcés en
   lecture seule par une contrainte en base (`is_writable = false`) tant que la règle
   non négociable 1 s'applique.
6. **S6 — Import IFC** via propositions et `external_identifiers`.
7. **S7 — Assistance IA** (plans et BIM) : produit uniquement des propositions.
8. **S8 — Visualisation 3D** (visionneuse IFC open source reliée à nos identifiants).

Chaque étape est indépendante et livrable seule. L'étape M2 en cours (règle de seuil →
alerte → ordre de travail) n'est pas remise en cause.

## Décisions actuelles signalées comme risques de blocage

1. **Principal : `functional_locations` est aujourd'hui le seul arbre.** Si l'on continue
   à y créer « Bâtiment A » ou « Étage 2 », on mélange le spatial et le technique, et
   l'import IFC ne pourra plus se faire proprement. **Décision à appliquer dès
   maintenant :** les bâtiments, étages, pièces et zones iront dans `spaces`. Les données
   actuelles ne sont que des données de développement (aucun client réel) : aucune
   migration de données n'est nécessaire. Si ce n'était plus le cas, ce serait une
   migration en trois temps (règle non négociable 6), jamais une conversion forcée.
2. **`measurements` n'est pas relié à un capteur précis.** Sans point, le plan ne peut pas
   placer un capteur. Non bloquant aujourd'hui (ajout d'une colonne facultative), mais à
   faire avant le premier connecteur réel (M3).
3. **`sites` n'a ni adresse ni fuseau horaire.** Nécessaire pour l'énergie, les
   plannings et l'affichage « temps réel » correct (le cahier le prévoit). Petit ajout
   non bloquant, à faire au plus tard avec S5.
4. **Le cache hors ligne mobile ne connaît que les positions fonctionnelles.** Le
   technicien ne verra pas encore « Bureau 104, Étage 1 ». Ajout ultérieur non bloquant
   (ADR 010 inchangée).
5. **Pas de PostGIS** : choix volontaire (portabilité, simplicité). Réversible sans
   toucher aux identités.

## Conséquences

- La règle « nouvelle table = tenant_id + RLS forcée + test d'isolation » s'applique à
  `spaces`, `functional_location_space_history`, `floor_plans`, `plan_placements`,
  `external_identifiers`, `import_batches`, `import_proposals` et `points`.
- Aucun modèle d'actifs parallèle : un équipement sur un plan est toujours une position
  fonctionnelle (et l'exemplaire qui l'occupe) du registre existant.
- La Feature Benchmark Matrix est mise à jour en conséquence.
- Cette ADR passera au statut « Acceptée » avec l'accord de Mohamed, avant l'étape S1.
