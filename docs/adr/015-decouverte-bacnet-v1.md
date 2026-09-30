# ADR 015 — Découverte BACnet V1 (lecture seule) et correspondance sémantique

## Statut

Acceptée (27 septembre 2026), directive autonome de Mohamed (« Ne m'interromps pas
pour chaque décision réversible et sans coût »). Aucune décision de cette ADR ne touche
un achat, un secret, une dépendance structurelle nouvelle, une rupture de contrat/API,
une baisse de sécurité, ou du matériel réel : elle relève donc de l'autonomie accordée.
La validation terrain (section 6) reste **BLOCKED_EXTERNAL_VALIDATION** jusqu'aux
essais réels autorisés sur une installation GTB.

## Contexte

Le 27 septembre 2026, Mohamed a demandé de construire un module BACnet V1 complet,
remplaçant le statut antérieur « auto-détection BACnet BLOCKED » (voir
`docs/spec/feature-benchmark-matrix.md`, décision du même jour, avant cette ADR) par
une capacité réelle et livrable, en vue d'essais terrain prochains sur des installations
CVC, groupes électrogènes, VRV/DRV, production/distribution thermique, comptage et
divers environnements GTB. Consignes explicites, reprises ici :

- BACnet V1 **strictement en lecture seule** : configurer une connexion, découvrir les
  équipements/contrôleurs accessibles, inventorier les objets exposés, lire les
  identifiants/métadonnées/valeurs/unités/états, horodater correctement, détecter
  périmé/hors ligne/inconnu, gérer proprement délais/erreurs/reconnexion. Aucune
  écriture, aucun changement de consigne, aucune commande dans cette version.
- **Découverte sémantique / auto-mapping** : proposer progressivement des
  correspondances vers le modèle universel, sans jamais inventer une correspondance
  pour « obtenir une démonstration impressionnante » — une correspondance incertaine
  reste explicitement à revoir, avec un niveau de confiance et une provenance.
- **Préparation aux essais terrain** : ne jamais supposer qu'un équipement donné parle
  BACnet directement ; préparer une méthode de comparaison entre ce que voit la GTB
  existante, ce que découvre notre Edge, ce que comprend notre modèle sémantique et ce
  que présente notre jumeau numérique.
- **BACnet Lab** : un simulateur automatisé pour le développement et la CI, avec une
  distinction explicite UNIT_TESTED / SIMULATOR_TESTED / FIELD_TESTED — jamais une
  validation simulateur présentée comme une validation terrain.
- **Réévaluation de `bacpypes3`** (section 3) et documentation de la décision ici.
- **Interface produit** : la découverte doit apparaître dans « Édition & Connectivité »
  (voir ADR 014), jamais rester backend-only.
- Sécurité et production sans raccourci : multi-tenant, RLS, RBAC, audit, aucune fuite
  de secret, provenance, idempotence — l'existence technique d'un point BACnet n'implique
  jamais le droit de le voir (et plus tard de le commander).

## Décision en bref

1. **Étendre le connecteur existant, jamais le remplacer.** `app/connectors/bacnet.py`
   (lecture seule, en place depuis le 25 septembre 2026) gagne deux fonctions de
   découverte (`discover_device`, `read_device_objects`) ; aucune fonction d'écriture
   n'est ajoutée nulle part dans ce module.
2. **BACnet reste un protocole d'intégration parmi d'autres.** Toute la connaissance de
   `bacpypes3` reste dans `app/connectors/bacnet.py` ; le domaine de découverte
   (`app/bacnet_discovery.py`) et le devineur sémantique
   (`app/connectors/bacnet_semantics.py`) ne connaissent que des structures simples
   (`BacnetObjectInfo`, chaînes, nombres) — un changement de bibliothèque BACnet,
   y compris majeur, ne touche jamais ces deux modules (règle non négociable 8).
3. **Réutiliser le patron « proposition → décision humaine » de l'import IFC**, jamais
   un second modèle parallèle : un scan produit des lots (`bacnet_discovery_batches`) et
   des propositions (`bacnet_discovery_proposals`), qu'une personne accepte (créant le
   point réel par `app/points.py::create_point`, le même chemin que la saisie manuelle)
   ou refuse (motif obligatoire).
4. **Le vocabulaire universel des points existait déjà pour la découverte** :
   `point_class` nullable, `mapping_confidence`, cycle `proposed` → `validated` séparé
   (`app/points.py`, `app/point_vocabulary.py`). Aucune structure nouvelle n'a été créée
   pour « accueillir » une découverte : les mêmes points, avec les mêmes garanties.
5. **`bacpypes3` conservé** (section 3), avec une isolation renforcée plutôt qu'un
   remplacement — jamais OPC UA à la place de BACnet, ce sont deux protocoles distincts
   avec des parcs installés différents.
6. **Validation à trois paliers explicites** (section 5) : UNIT_TESTED, SIMULATOR_TESTED,
   FIELD_TESTED — ce document et le code ne présentent jamais l'un pour l'autre.
7. **Interface web** : section « Découverte BACnet » sur la fiche équipement (scan,
   lots, propositions avec confiance et raison traduite, acceptation avec correction
   possible, refus motivé) — voir ADR 014 pour la grille produit complète.

## 1. Audit de l'existant (avant d'écrire le nouveau code)

| Élément existant | Constat | Verdict |
|---|---|---|
| `app/connectors/bacnet.py` (`BacnetPoint`, `read_bacnet_points`, `BacnetReadError`) | Lecture cyclique d'une carte de points fixe (`bacnet_device_mapping`), déjà en lecture seule, déjà isolé du noyau | **KEEP**, **ADD** deux fonctions de découverte dans le même fichier |
| `app/connectors/device_mapping.py` (`BACNET_DEVICE_MAPPING`) | Carte de points validée manuellement, indépendante de toute découverte | **KEEP** — la découverte alimente des points, jamais directement une carte de relève ; les deux restent séparés |
| `scripts/bacnet_daemon.py` | Relève cyclique via la carte de points active | **KEEP**, aucun changement : la découverte est un flux séparé, ponctuel, jamais rejoué automatiquement |
| `app/points.py` (`create_point`, `point_class` nullable, `mapping_confidence`, `mapping_status`) | Modèle déjà pensé pour un point « découvert, pas encore identifié » (voir commentaires existants) | **KEEP**, réutilisé tel quel — aucune colonne ajoutée aux points pour la découverte |
| `app/point_vocabulary.py` (`POINT_CLASSES`, « règle des trois ») | Classes alignées Brick, ajoutées seulement sur cas réel | **KEEP** ; aucune classe ajoutée pour BACnet spécifiquement — les classes existantes (température, pression, marche, défaut…) couvrent déjà les points CVC rencontrés |
| `app/ifc_import.py` (lots, propositions, `accept`/`reject`, doublons) | Patron déjà résolu pour « détection automatique → proposition → décision humaine » | **KEEP** le patron, **ADD** son application à BACnet (tables et module dédiés, jamais une fusion des deux domaines) |
| `shared/i18n/*/findings.json`, `app/findings.py::displayed()` | Patron déjà résolu pour code stable + paramètres → phrase traduite à l'affichage | **KEEP** le patron, **ADD** son application aux raisons de correspondance sémantique (`bacnet_discovery.json`) |
| Grille produit ADR 014 (Backend/API/Web/Mobile/Edge/Tests/Documentation) | Déjà appliquée à Modbus/OPC UA | **KEEP**, appliquée à la découverte BACnet (voir matrice) |

Aucune fonctionnalité existante n'a été jugée insuffisamment robuste au point de
nécessiter un REFACTOR ou un REPLACE : le point de départ était déjà sain.

## 2. Architecture : BACnet Point → Digital Twin

```
BACnet Point (objet + instance, ReadProperty)
  │  app/connectors/bacnet.py (discover_device, read_device_objects)
  ▼
BacnetObjectInfo (structure simple, plus aucune trace de bacpypes3)
  │  app/connectors/bacnet_semantics.py (guess_point_class)
  ▼
SemanticGuess (point_class | None, unit | None, confidence | None, reason_code)
  │  app/bacnet_discovery.py (run_discovery → bacnet_discovery_proposals)
  ▼
Proposition (statut proposed/accepted/rejected/duplicate, révisable par une personne)
  │  accept_proposal() → app/points.py::create_point (même chemin que la saisie manuelle)
  ▼
Point réel (Universal Asset Model, mapping_status='proposed', mapping_confidence conservée)
  │  déjà branché : app/telemetry.py, passeport, jumeau numérique (ADR 004)
  ▼
Digital Twin
```

Points de conception :

- **Aucune valeur de télémétrie n'entre par la découverte.** `read_device_objects` ne lit
  qu'un aperçu de la valeur courante (`present_value_preview`, une chaîne, jamais stockée
  comme mesure) pour aider la décision humaine ; la relève régulière
  (`read_bacnet_points`, déjà existante) reste le seul chemin vers `app/telemetry.py`,
  une fois le point accepté et une carte de relève configurée séparément.
- **Provenance.** Chaque point créé par acceptation porte `mapping_confidence` (celle du
  devineur, ou `None` si la classe a été corrigée manuellement) ; l'objet BACnet source
  (type, instance) reste dans la proposition, jamais recopié sur le point lui-même — la
  proposition est l'historique de la découverte, le point est l'entité vivante.
- **Idempotence des scans.** Un objet déjà accepté (même équipement, même adresse, même
  couple type/instance) redevient `duplicate` lors d'un nouveau scan, jamais une
  deuxième proposition ni un deuxième point pour le même objet physique.
- **Multi-tenant.** `bacnet_discovery_batches` et `bacnet_discovery_proposals` portent
  `tenant_id`, RLS forcée dès la migration (`d0252a39b344`), avec un test qui prouve
  qu'un autre tenant ne voit ni le lot ni ses propositions
  (`test_isolation_des_tenants_un_autre_tenant_ne_voit_aucun_lot_ni_proposition`).
- **RBAC.** Lecture : `technicien`, `responsable_exploitation`, `admin_tenant`. Scan et
  décision (accepter/refuser) : `responsable_exploitation`, `admin_tenant` uniquement —
  une découverte crée une entité réelle du registre, au même niveau de droits qu'une
  création manuelle.
- **Audit.** Scan, acceptation et refus écrivent chacun une entrée dans le journal
  append-only (`append_audit_entry`), avec le contenu utile au diagnostic (adresse,
  statut du lot, code d'erreur, identifiant du point créé, motif de refus).
- **Aucun secret exposé.** L'adresse BACnet/IP saisie n'est pas un secret réseau au sens
  de CLAUDE.md (pas d'authentifiant, pas de clé) ; elle apparaît en clair dans
  l'interface et le journal, comme toute autre configuration de connectivité déjà
  affichée (Modbus, OPC UA). Aucune donnée d'identification n'est demandée par ce
  protocole en V1.
- **Diagnostics et observabilité (ajouté le 30/09/2026).** Trois niveaux, jamais
  confondus : (1) l'historique de chaque scan (statut, code d'erreur, compteurs)
  reste dans `bacnet_discovery_batches`, consultable depuis la fiche équipement,
  jamais résumé ni perdu ; (2) l'activité de l'agent Edge de découverte (liste des
  scans en attente, rapport de résultat ou d'échec) met à jour `edge_devices.last_seen_at`
  à chaque appel (`app.devices.touch_last_seen`), pas seulement à l'authentification —
  alimente directement le diagnostic de connectivité déjà affiché au niveau du
  portefeuille (`communication_status`, `apps/web/src/app/page.tsx`) ; (3) chaque
  requête HTTP de découverte est déjà comptée sans travail supplémentaire par les
  métriques génériques existantes (`app.metrics`, `GET /metrics`, format Prometheus :
  `paios_http_requests_total{route="/bacnet-discovery/..."}`), et chaque erreur non
  gérée reste journalisée en structuré (`app.observability`) comme partout ailleurs.
  Aucun tableau de bord dédié BACnet n'a été jugé nécessaire au-delà de ces trois
  niveaux déjà en place, réutilisés tels quels plutôt que dupliqués.

## 3. Réévaluation de `bacpypes3`

| Critère | Constat | Conclusion |
|---|---|---|
| Maintenance | Dépôt actif (JoelBender/bacpypes3), publications régulières en 2025-2026 | Suffisant pour un usage lecture seule |
| Licence | MIT — compatible avec un usage commercial sans obligation de publication | Aucun blocage |
| Compatibilité Python | Pure Python, testé jusqu'à 3.12/3.13, aligné sur la pile du MVP (Python 3.12) | Compatible |
| Ajustement asynchrone | Nativement `asyncio`, comme le reste du connecteur (même pont synchrone déjà en place pour Modbus/OPC UA : `asyncio.run` à chaque relève) | Cohérent avec l'architecture existante |
| Stabilité | Version 0.0.110 : **API non stabilisée** (versionnage 0.0.x), déjà signalé comme risque le 25/09/2026 | Risque confirmé, non résolu par cette réévaluation |
| Testabilité | Le paquet fournit à la fois un client **et** un serveur (`Application`) : le serveur sert de simulateur réel dans les tests (`tests/bacnet_lab.py`), jamais un simulacre — un test qui passe prouve un vrai dialogue BACnet/IP | Excellent point fort, décisif |
| Impact sur l'empaquetage Edge | Pure Python, aucune dépendance native compilée | Aucun impact négatif sur le paquet Edge |
| Évolutivité du SDK connecteur | Tout le savoir de la bibliothèque reste dans un seul fichier (`app/connectors/bacnet.py`) ; le reste du noyau ne connaît que des structures simples | Compatible avec le SDK de connecteur (ADR 012 §2.12) |

**Décision : garder `bacpypes3`**, version épinglée exacte (`requirements.txt`, déjà la
pratique). Aucune alternative Python mature n'existe pour BACnet/IP en lecture seule à
la date de cette ADR ; le risque de version 0.0.x est géré par l'isolation stricte
(un seul fichier connaît la bibliothèque) et par les tests SIMULATOR_TESTED, qui
détecteraient un changement de comportement avant toute mise à jour en production
(procédure déjà décrite dans la matrice : rejouer `tests/test_bacnet_connector.py`,
`tests/test_bacnet_daemon.py` et désormais aussi `tests/test_bacnet_discovery_connector.py`
avant toute montée de version). Ne jamais remplacer BACnet par OPC UA : deux protocoles
avec des parcs installés distincts, tous deux nécessaires au wedge CVC.

## 4. Devineur sémantique : règles et garde-fous

`app/connectors/bacnet_semantics.py` (module pur, aucun réseau, aucune base) propose une
classe de point selon, dans l'ordre de fiabilité :

1. **Unité BACnet reconnue** (confiance 0,8 à 0,9) — le signal le plus fiable : une unité
   physique ne s'invente pas.
2. **Mot-clé du nom ou de la description** (confiance 0,5 à 0,8) — seulement en l'absence
   d'unité utilisable, toujours à une confiance plus basse qu'une unité.
3. **Aucun signal fiable** → `point_class=None`, `confidence=None`, code
   `NO_RELIABLE_SIGNAL` : la proposition reste explicitement à revoir par une personne,
   jamais une classe choisie « par défaut ».
4. **Valeur multi-état** → toujours `MULTISTATE_NOT_YET_MAPPED` : le vocabulaire universel
   n'a encore aucune classe multi-état générique (« règle des trois » : aucune classe
   ajoutée sans cas réel rencontré) ; ajouter une telle classe est un choix futur,
   documenté ici comme **DEFER** jusqu'au premier cas réel qui le justifie.

Chaque code de raison est traduit à l'affichage (`reason_message`, catalogue
`shared/i18n/{fr,en}/bacnet_discovery.json`), jamais stocké en phrase (ADR 013).
14 tests unitaires (`tests/test_bacnet_semantics.py`) couvrent chaque branche, y compris
les trois cas « ne jamais inventer » ci-dessus.

## 5. Trois paliers de validation, jamais confondus

| Palier | Signifie | Exemple dans ce dépôt |
|---|---|---|
| UNIT_TESTED | Aucun réseau, logique pure | `tests/test_bacnet_semantics.py` |
| SIMULATOR_TESTED | Vrai dialogue BACnet/IP, contre un appareil simulé réel (BACnet Lab, `bacpypes3.app.Application`, jamais un simulacre) | `tests/test_bacnet_discovery_connector.py`, `tests/test_bacnet_discovery.py`, `tests/test_bacnet_discovery_api.py` |
| FIELD_TESTED | Contre un appareil BACnet réel, sur un réseau réel, dans une installation autorisée | **BLOCKED_EXTERNAL_VALIDATION** — aucun essai réalisé à la date de cette ADR |

Aucun texte de ce dépôt (code, tests, documentation) ne présente une validation
SIMULATOR_TESTED comme une validation FIELD_TESTED.

### BACnet Lab (`tests/bacnet_lab.py`)

Simulateur réutilisable : un vrai appareil BACnet/IP (`bacpypes3.app.Application`) dans
un fil dédié avec sa propre boucle `asyncio`, exposant huit objets représentatifs d'une
installation CVC réelle (température avec unité, pression avec unité, valeur sans unité
exploitable, consigne en sortie analogique, défaut et marche en entrée binaire,
autorisation de marche en valeur binaire, mode en valeur multi-état à trois positions).
Démarré/arrêté par test (`BacnetLab.start()`/`stop()`), jamais un processus persistant en
arrière-plan de la suite de tests.

## 6. Méthodologie de comparaison terrain (outil prêt, exécution BLOCKED_EXTERNAL_VALIDATION)

Mise à jour du 30/09/2026 : l'outil qui exécute cette méthodologie existe désormais
(`app.bacnet_field_comparison`, UNIT_TESTED ; `scripts/bacnet_field_comparison.py`, le
CLI de terrain). Il rapproche un relevé GTB fait à la main (fichier CSV : nom, unité,
remarques) avec les propositions d'un scan de découverte déjà exécuté, sur une
correspondance stricte de nom normalisé — jamais une correspondance approximative
inventée, pour ne jamais masquer un vrai écart terrain. Le rapport Markdown produit
distingue quatre catégories : correspondances trouvées, points vus par la GTB mais non
découverts (écart à investiguer : adressage, pare-feu, ou protocole différent de BACnet
pour cet équipement), points découverts absents de la liste GTB, et points sans
correspondance sémantique fiable encore à classer. Testé bout en bout contre un vrai
scan BACnet Lab (`tests/test_bacnet_field_comparison_e2e.py`), jamais contre un
appareil réel : la méthodologie elle-même reste **BLOCKED_EXTERNAL_VALIDATION**.

Ne jamais supposer qu'un équipement donné parle BACnet directement : un automate GTB
peut exposer ses points par BACnet, par Modbus, par une passerelle propriétaire, ou ne
rien exposer du tout à un tiers. Avant tout essai terrain, la méthode à suivre (écrite
ici, exécution différée à un accès autorisé) :

1. **Ce que voit la GTB existante** : relever manuellement, depuis la supervision déjà
   en place chez le client, la liste des points visibles pour l'installation concernée
   (nom, unité, type), avec l'accord explicite du client et de son intégrateur.
2. **Ce que découvre notre Edge** : lancer un scan BACnet V1 (`POST
   /bacnet-discovery/scan`) sur l'adresse autorisée, obtenir la liste des objets
   inventoriés (type, instance, nom, unité, aperçu de valeur).
3. **Ce que comprend notre modèle sémantique** : les propositions de classe, confiance et
   raison pour chaque objet (étape 2, sans action supplémentaire — le scan les produit
   déjà).
4. **Ce que présente notre jumeau numérique** : après acceptation des propositions
   pertinentes, la fiche équipement et le passeport correspondants.
5. **Écart documenté** : toute différence entre 1 et 2 (objet vu par la GTB mais absent
   de notre inventaire, ou l'inverse) signale soit un problème d'adressage/réseau, soit
   un point que le protocole BACnet ne remonte pas depuis cet automate — jamais supposé
   sans vérification. Toute différence entre 2 et 3 alimente directement l'amélioration
   du devineur sémantique (nouveau mot-clé, nouvelle unité) ; toute différence entre 3
   et 4 signale un bogue d'acceptation, jamais un cas normal.

Cette méthode ne peut être exécutée que sur une installation autorisée, contrôlée et
strictement en lecture seule ; elle reste **BLOCKED_EXTERNAL_VALIDATION** jusqu'à
l'accès réel annoncé par Mohamed.

## 7. Impact architectural

- **Aucun nouveau service, aucune nouvelle base.** Deux tables dans la base existante,
  deux modules Python dans le monolithe modulaire (ADR 012), un routeur de plus.
- **Aucune dépendance nouvelle.** `bacpypes3` était déjà une dépendance (25/09/2026) ;
  cette ADR étend son usage, ne l'ajoute pas.
- **Aucune migration destructive.** Deux nouvelles tables (expansion pure), aucune
  colonne modifiée sur une table existante.
- **Web.** Nouvelle section « Découverte BACnet » sur la fiche équipement
  (`apps/web/src/app/registre/[id]/page.tsx`), même patron que les sections Modbus et
  import IFC déjà en place — aucune nouvelle dépendance JavaScript, aucun changement
  d'architecture web.
- **Compatible avec un futur protocole.** Le devineur sémantique et le patron
  proposition/décision ne connaissent que des métadonnées génériques (unité, nom,
  type de valeur) ; un connecteur Modbus, OPC UA ou MQTT pourra réutiliser exactement le
  même pipeline de découverte en fournissant ses propres `ObjectInfo`, sans dupliquer la
  logique de correspondance ni le patron de validation humaine.

## Conséquences

- `docs/spec/feature-benchmark-matrix.md` : ligne « Connecteurs protocoles terrain »
  mise à jour (auto-détection BACnet passée de BLOCKED à faite, validation FIELD_TESTED
  toujours BLOCKED_EXTERNAL_VALIDATION) ; nouvelle ligne « Découverte automatique et
  correspondance sémantique (auto-mapping) des points ».
- `docs/product/glossaire.md` : treize classes de points (`point_class`) nommées en
  français et en anglais avant leur premier affichage (section 4.1).
- Aucune règle non négociable modifiée : la règle 1 (aucune commande) reste intacte,
  BACnet V1 est lecture seule de bout en bout, y compris dans ses tests.
- Prochaine étape naturelle (non demandée ici, DEFER) : appliquer le même pipeline de
  découverte à Modbus et OPC UA, une fois qu'un besoin réel l'exige (« règle des trois »).
