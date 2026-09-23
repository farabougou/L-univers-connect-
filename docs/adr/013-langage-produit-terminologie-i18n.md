# ADR 013 — Langage produit, terminologie, codes et internationalisation

## Statut

Acceptée (23 septembre 2026), avec l'accord de Mohamed (« continuons »). Les quatre
questions terminologiques de la section 5 sont tranchées selon les propositions par
défaut ; elles restent révisables à faible coût, puisque seuls les libellés des
catalogues changeraient, jamais les codes.

## Contexte

Le 23 septembre 2026, Mohamed a formulé une directive transversale sur le langage
produit (texte complet, mot pour mot :
[`docs/spec/product-language-directive.md`](../spec/product-language-directive.md)) : la
qualité du langage devient un critère d'acceptation et une composante de l'architecture.
Consignes explicites : auditer l'existant (KEEP / REFACTOR / REPLACE / ADD / DEFER), ne
pas surarchitecturer, mais concevoir tôt les décisions structurantes (i18n, codes d'état,
gravité, unités, identifiants, taxonomie des actifs, messages de commande, terminologie).

## Décision en bref

1. **Un seul référentiel terminologique** : [`docs/product/glossaire.md`](../product/glossaire.md)
   (termes officiels français et anglais, définition, terme proscrit, norme de
   référence). Il fait foi pour l'interface, la documentation, l'API et le support.
2. **Le code, pas la phrase.** Tout ce que le système produit lui-même (erreurs,
   constats, états, événements) est enregistré et transmis sous forme de **code stable +
   paramètres**. La phrase est fabriquée au moment de l'affichage, dans la langue de la
   personne. Aucune phrase générée n'est plus stockée en base.
3. **Quatre axes séparés** pour tout signalement : nature (type d'événement), gravité,
   état de la condition (active / revenue à la normale), état d'acquittement ; plus un
   niveau de certitude pour tout résultat d'analyse.
4. **Deux axes séparés pour l'état d'un équipement** : état de fonctionnement et état de
   communication. « Hors ligne » n'est pas un état de fonctionnement : c'est l'absence
   d'information récente, et l'interface affiche alors le dernier état connu et sa date.
5. **Internationalisation** : catalogues de messages français et anglais partagés par
   l'API, le web et le mobile ; formats de date, nombre et pluriels par les règles
   standard des langues (CLDR, via `Intl`) ; heure affichée dans le fuseau du site.
6. **Erreurs** au format standard « Problem Details » (RFC 9457) : code stable,
   paramètres, identifiant de requête, message traduit ; jamais de détail technique
   (déjà garanti pour les erreurs imprévues depuis F6).
7. **Monolithe inchangé** : aucun nouveau service. Des fichiers de vocabulaire versionnés
   et des catalogues, dans la continuité de ce qui existe.

## 1. Audit de l'existant (état réel du code au 23 septembre 2026)

| Élément existant | Constat | Verdict |
|---|---|---|
| Vocabulaires versionnés en code (`graph_vocabulary`, `point_vocabulary`, `spatial_vocabulary`, `closure_vocabulary`, états du cycle de vie) | Les règles métier dépendent déjà de **codes** stables (`clock_suspect`, `refrigerant_leak`, `in_service`…) | **KEEP** — c'est exactement le principe du point 14 |
| Unités en codes UCUM avec leur grandeur physique ; contrôle de compatibilité classe ↔ grandeur | Une sonde de température ne peut pas être déclarée en bar | **KEEP** + ADD conversion d'affichage (point 10) |
| Origine des mesures (`measured`, `manual`, `derived`, `estimated`, `simulated`) et drapeaux de qualité | Une valeur estimée ou simulée n'est jamais présentée comme mesurée | **KEEP** (point 5) |
| Identifiants : UUID interne immuable, identifiants externes par schéma, code + nom de position, numéro de série, fabricant + référence | Le nom affiché n'est jamais l'identifiant | **KEEP** + ADD code d'inventaire client (point 11) |
| Erreurs imprévues : 500 sans détail interne, avec `request_id` (F6) | Conforme au point 13 | **KEEP** |
| 46 erreurs API en phrases françaises codées en dur (`detail="nœud introuvable"`), une en anglais (`"database unavailable"`) | Pas de code stable, pas de traduction, langue incohérente | **REFACTOR** (étape L2) |
| Constats générés par le système : titre et action recommandée **stockés en base en phrases françaises** (`rules.py`) | Impossible à traduire après coup ; coût qui grandit avec chaque constat | **REFACTOR** (étape L3) — **risque de blocage n° 1** |
| Alarmes et constats : un seul champ `status` (`open`, `acknowledged`, `resolved`) | Mélange acquittement et état de la condition : impossible de représenter « revenue à la normale, non acquittée », état courant des alarmes de GTB | **REFACTOR** (étape L3) — **risque de blocage n° 2**, à corriger avant M3 |
| Gravité `info` / `warning` / `critical` sans définition écrite | Trois niveaux sans critère : tentation d'utiliser « critique » pour attirer l'attention | **REFACTOR** : définitions + niveau `major` ajouté (L3) |
| Constats : nature (`kind`), méthode, confiance | Pas de niveau de certitude explicite (anomalie détectée ≠ défaut confirmé) | **ADD** niveau de certitude (L3) |
| `product_models.category` en texte libre (`"pac"`) | Chaque client écrira « PAC », « pompe à chaleur », « heat pump » : recherche, statistiques de flotte et IA bloquées | **REFACTOR** vers un type universel + alias (L5) — **risque de blocage n° 3** |
| Sites sans fuseau horaire | Impossible d'afficher l'heure locale d'un site distant, ni de raisonner en heures d'exploitation | **ADD** `sites.timezone` (L4) |
| Libellés des vocabulaires en français dans le code Python | Traduction impossible sans toucher au code | **REFACTOR** vers les catalogues (L2-L4) |
| Web et mobile : textes en dur ; tutoiement (« Prends une photo… », « Vérifie que tu as le rôle… ») ; émojis dans le passeport ; « Position » à l'écran pour ce que le code appelle emplacement fonctionnel | Non conforme (ton, cohérence, i18n) | **REFACTOR** (L4) |
| État du cycle de vie `ordered` affiché « Commandé » | Collision avec « Commande » (ordre envoyé à un équipement) | **REFACTOR** libellé « En approvisionnement » (L4) |
| État de fonctionnement / de communication des équipements | N'existe pas dans le modèle | **ADD** (L6) |
| Commandes physiques | Aucune (règle non négociable 1, niveau C0) | **DEFER** : vocabulaire fixé dès maintenant dans le glossaire, aucun code |
| Génération de texte par IA | Aucune | **DEFER** : règles fixées maintenant (section 4.8) |
| Présentation selon le profil | Rôles existants (`technicien`, `responsable_exploitation`, `admin_tenant`) ; actions calculées par rôle dans le passeport | **KEEP** + DEFER : chaque terme a un libellé métier et un libellé technique dès L2 ; le choix d'affichage viendra avec les écrans |

## 2. Risques de blocage signalés avant de coder

1. **Élevé — phrases générées stockées en base (constats).** Chaque constat enregistré
   aujourd'hui en français devra être réécrit pour être traduit. Données de test
   uniquement pour l'instant : correction peu coûteuse maintenant. → **L3**.
2. **Élevé avant M3 — statut unique des alarmes.** Les alarmes de GTB passent par
   « active non acquittée → active acquittée → revenue à la normale » et aussi
   « revenue à la normale sans avoir été acquittée ». Le champ unique actuel ne peut pas
   le représenter ; le connecteur de M3 le rendrait visible. → **L3**.
3. **Moyen — catégories d'équipement en texte libre.** Bloque la Fleet Intelligence, la
   recherche et l'IA ; chaque nouveau client ajoute des variantes à normaliser. → **L5**.
4. **Moyen — contrat d'erreur de l'API.** Les clients (web, mobile, bientôt l'Edge et
   les intégrateurs) vont s'appuyer sur le texte des erreurs s'ils n'ont pas de code. →
   **L2**, avant tout client externe.
5. **Faible — absence de fuseau par site.** Aujourd'hui tous les tests sont en France ;
   devient bloquant au premier site hors fuseau. → **L4**.

## 3. Impact architectural

- **Aucun nouveau service, aucune nouvelle base.** Nouveaux éléments : un dossier de
  catalogues partagés (`shared/i18n/fr.json`, `shared/i18n/en.json`), un module d'erreurs
  de l'API, des colonnes ajoutées en « élargir, migrer, contracter ».
- **Source de vérité unique des textes** : les catalogues. L'API les lit pour ses
  erreurs ; le web et le mobile les importent. Un test vérifie que chaque clé existe
  dans les deux langues avec les mêmes paramètres.
- **Format des messages** : ICU MessageFormat (standard Unicode, gère pluriels et
  genres). Côté API, messages limités aux paramètres simples (sans pluriel), vérifiés par
  un test, pour ne pas ajouter de dépendance Python.
- **Dépendances** : une bibliothèque i18n côté web et mobile (proposition : FormatJS,
  même moteur ICU pour les deux ; compatibilité avec le moteur JavaScript Hermes du
  mobile à vérifier). Soumis à l'accord de Mohamed à l'étape L4 (changement de
  dépendance).
- **API** : `Accept-Language` choisit la langue des messages ; `code` et `params` sont
  toujours présents et font foi. Le champ `detail` reste une chaîne (compatible avec
  les clients actuels).

## 4. Décisions structurantes

### 4.1 Terminologie
Voir le glossaire. Principes : un concept = un terme officiel par langue ; les termes
proscrits sont listés ; les termes anglais standards (BACnet, FDD, Brick) sont conservés
avec leur explication ; normes de référence citées (NF EN 13306 pour la maintenance,
ISA-18.2 / IEC 62682 pour les alarmes, ISO 55000 pour les actifs, IFC / ISO 16739 pour
le spatial, Brick pour la sémantique, UCUM pour les unités).

### 4.2 Signalements : quatre axes (point 3)
| Axe | Codes | Remarque |
|---|---|---|
| Nature (`event_type`) | `information`, `data_quality`, `anomaly`, `fault`, `alarm`, `incident`, `commissioning`, `prediction` | « Action requise » n'est pas une nature : c'est un indicateur `action_required` |
| Gravité (`severity`) | `info`, `warning`, `major`, `critical` | Définie par la réponse attendue (section 4.3), jamais par l'envie d'attirer l'attention |
| Condition (`condition_state`) | `active`, `cleared` | La situation existe-t-elle encore ? |
| Acquittement (`ack_state`) | `unacknowledged`, `acknowledged` | Quelqu'un en a-t-il pris connaissance ? |
| Traitement (`handling_status`) | `open`, `in_progress`, `closed`, `false_positive` | Où en est la prise en charge ? |

### 4.3 Gravité : définitions exploitables
| Code | Français | Réponse attendue |
|---|---|---|
| `info` | Information | Aucune action ; trace utile |
| `warning` | Avertissement | Action à planifier ; pas d'effet immédiat sur le service |
| `major` | Majeur | Action rapide ; service dégradé ou risque de dégradation |
| `critical` | Critique | Action immédiate ; perte de service, risque pour les personnes, les biens ou la conformité réglementaire |

Les délais chiffrés par niveau seront paramétrables par client (configuration
versionnée, F4). Un niveau n'est jamais choisi par défaut à « critique ».

### 4.4 Niveau de certitude (point 5)
Codes `detected` (anomalie détectée), `confirmed` (défaut confirmé), `probable_cause`,
`hypothesis`, `prediction`, `recommendation`, `simulation_result`, `unavailable`.
Règles : seule une personne (ou un essai de vérification enregistré) fait passer à
`confirmed` ; une sortie d'IA ou de modèle statistique ne peut jamais être `confirmed` ;
le niveau est affiché avec le résultat.

### 4.5 État d'un équipement : deux axes (point 2)
| Axe | Codes | Source |
|---|---|---|
| Fonctionnement (`operational_status`) | `running`, `stopped`, `disabled`, `fault`, `unknown` | Points d'état validés (marche, défaut, autorisation) |
| Communication (`communication_status`) | `online`, `offline`, `unreachable` | `offline` : aucune donnée dans le délai attendu (déjà calculé par le score de confiance) ; `unreachable` : échec de communication signalé par l'Edge (à partir de M3) |

Affichage : « Hors ligne depuis 14 h 05 — dernier état connu : en fonctionnement ».
Jamais un état de fonctionnement présenté comme actuel sans donnée récente.

### 4.6 Commandes (point 6) — DEFER, vocabulaire fixé
Cycle : `requested` → `authorized` → `sent` → `acknowledged` → `executed` → `verified`,
avec `failed`, `rejected`, `expired`, `cancelled`. En français, `acknowledged` d'une
commande se dit **« Reçue par l'équipement »** et non « Acquittée », pour ne pas le
confondre avec l'acquittement d'une alarme. « Exécutée » n'est affiché qu'après
vérification de l'état réel (état souhaité ↔ état réel, ADR 012). Aucun code avant la
levée explicite de la règle non négociable 1.

### 4.7 Erreurs (points 13 et 14)
Format RFC 9457 : `{"type", "title", "status", "detail", "code", "params", "request_id"}`.
Codes en majuscules, stables, par domaine (`INTERVENTION_NOT_FOUND`,
`CLIENT_REF_CONFLICT`, `LIFECYCLE_TRANSITION_FORBIDDEN`…). Les tests vérifient le code,
jamais la phrase.

### 4.8 IA (point 15) — DEFER, règles fixées
Toute sortie d'IA destinée à un client passe par le même référentiel (termes,
unités, langue, niveau de certitude) et porte le niveau `hypothesis`, `prediction` ou
`recommendation` ; elle ne crée jamais de constat `confirmed` et ne commande rien.

### 4.9 Unités (point 10)
La valeur de référence reste dans l'unité du point (UCUM). Conversion d'affichage
(°C ↔ °F, bar ↔ psi…) selon la préférence de l'utilisateur ou du client, sans jamais
modifier la valeur stockée (DEFER jusqu'au premier besoin réel). À partir de M3, un
connecteur qui convertit conserve aussi la valeur et l'unité sources.

### 4.10 Identifiants et nomenclature (points 11 et 12)
Existant conservé. Ajouts : code d'inventaire client sur l'exemplaire ; type universel
d'équipement (vocabulaire versionné aligné sur les classes d'équipement Brick), désignation
constructeur, alias (au niveau du vocabulaire, puis par client si besoin).

## 5. Questions terminologiques (tranchées le 23 septembre 2026, propositions par défaut)

1. **Les trois niveaux d'identité** : « Équipement » (la position, ce que le technicien
   voit : « CTA-02 — Bureaux R+1 ») / « Exemplaire » (l'appareil, numéro de série) /
   « Modèle » (fabricant + référence) ; ou la convention SAP « Poste technique » /
   « Équipement » / « Modèle ».
2. **Espace** comme terme général (avec types : pièce, local technique, circulation,
   extérieur) ; « Local » réservé au type « local technique ».
3. **Installation** : non utilisé comme concept (ambigu : un système ou l'action
   d'installer) ; « Système » pour un ensemble technique (réseau d'eau glacée,
   ventilation d'un plateau).
4. **Vouvoiement** partout dans l'interface.

## 6. Plan de migration

Chaque étape est livrée seule, testée, vérifiée en CI, puis soumise à l'accord de
Mohamed avant la suivante.

| Étape | Contenu | Migrations | Impact sur l'existant |
|---|---|---|---|
| **L1 — Référentiel** | Glossaire validé ; critères d'acceptation rédactionnels dans `CLAUDE.md` ; cette ADR acceptée | Aucune | Documentation seulement |
| **L2 — Codes d'erreur et catalogues API** | `shared/i18n/{fr,en}.json` ; module d'erreurs RFC 9457 ; les 46 erreurs converties en codes ; `Accept-Language` ; test de parité des catalogues | Aucune | `detail` reste une chaîne : clients actuels compatibles ; tests mis à jour pour vérifier les codes |
| **L3 — Signalements** | Constats : code de raison + paramètres, niveau de certitude ; alarmes et constats : condition, acquittement, traitement séparés ; gravité `major` et définitions | Élargir (colonnes), migrer (depuis `status` et depuis les titres générés), contracter (retrait de l'ancien `status`) | Routes de statut conservées pendant la transition |
| **L4 — Interfaces** | Bibliothèque i18n web et mobile (accord requis) ; écrans existants passés aux catalogues ; vouvoiement ; émojis remplacés ; formats `Intl` ; `sites.timezone` | Élargir (`sites.timezone`, facultatif puis rempli) | Textes visibles corrigés |
| **L5 — Nomenclature des équipements** | Vocabulaire des types d'équipement + alias ; `product_models.equipment_type` ; code d'inventaire sur l'exemplaire | Élargir, migrer (correspondance des catégories existantes), contracter | `category` conservée jusqu'à la contraction |
| **L6 — État des équipements** | Calcul de l'état de fonctionnement et de communication, affiché dans le passeport avec sa source et sa date | Aucune au départ (valeur calculée) ; historisation avec M3 | Passeport complété |
| **DEFER** | Commandes, textes générés par IA, présentation par profil, conversion d'unités d'affichage, libellés traduits des noms saisis par les clients | — | — |

Ordre justifié par le coût : L2 et L3 d'abord (contrat de l'API et données stockées
qui s'accumulent), L4 avant d'ajouter de nouveaux écrans.

## 8. Avancement

| Étape | État |
|---|---|
| L1 | ✅ ADR acceptée, glossaire en version 1 (23 septembre 2026) |
| L2 | ✅ 121 codes d'erreur en français et en anglais (`shared/i18n/{fr,en}/errors.json`) ; réponses RFC 9457 (`application/problem+json`, `Content-Language`) ; langue choisie par `Accept-Language` ; erreurs de validation sans écho de la valeur saisie ; erreurs imprévues en `INTERNAL_ERROR` avec la référence ; tests : parité des catalogues, typographie française, correspondance exacte entre codes utilisés et codes décrits, aucune erreur en texte libre. Le dossier `shared/` doit accompagner l'API au déploiement (ou `I18N_DIR`). Les paramètres qui sont des codes (états, types) sont encore affichés tels quels dans les messages de l'API ; leurs libellés traduits viendront avec les catalogues d'interface (L4). |
| L3 | ✅ Constats : code de raison + paramètres (catalogue `findings`, titres et actions traduits à l'affichage ; seul le titre écrit par l'auteur d'une règle est stocké), niveau de certitude (`detected` par défaut, `confirmed` seulement par une personne avec une note, jamais pour une prédiction — contraintes en base), `action_required`. Alarmes et constats : `condition_state`, `ack_state`, `handling_status` séparés, historique champ par champ ; retour à la normale détecté automatiquement quand la mesure redevient conforme (constat et alarme liés), réactivation de la même occurrence si le problème revient avant la clôture ; clôture refusée tant que la condition est active ; gravité `major` ; priorité d'ordre de travail dérivée de la gravité. Migrations `411cfe7c1b9a` → `b0125567ecd2` → `ddbfca2ccdde` vérifiées en aller-retour sur des données de l'ancien modèle. Les routes `PATCH …/status` des alarmes et des constats sont remplacées par `…/acknowledge`, `…/handling`, `…/clear` (alarmes) et `…/confirm` (constats) : aucun client ne les utilisait. |
| L4 | ✅ Catalogues d'interface `shared/i18n/{fr,en}/ui.json` et traducteur sans dépendance (`translator.ts` : pluriels CLDR, dates, nombres, fuseaux via `Intl`), copiés dans le web et le mobile par `npm run i18n:sync` (un test échoue si une copie diverge). Tous les écrans web et mobiles traduits ; vouvoiement, émojis retirés, termes du glossaire (« Équipement », « Exemplaire », « En approvisionnement ») ; messages techniques de connexion remplacés par un message du catalogue ; erreurs web affichées depuis leur code ; tests qui refusent tout texte en dur dans un écran. Langue : téléphone (mobile), `Accept-Language` du navigateur (web), transmise à l'API. Libellés de clôture sortis du code Python (`closure.json`). `sites.timezone` (IANA, obligatoire pour un nouveau site, `PUT /sites/{id}/timezone` pour les anciens, jamais deviné) ; le passeport affiche les heures dans le fuseau du site et le dit, sinon dans celui de l'appareil et le dit aussi. Non testé sur un téléphone réel. |
| L5 | ✅ Vocabulaire versionné des types universels d'équipement (`app/equipment_vocabulary.py` : 11 types du wedge CVC, alias, correspondance Brick vérifiée sur Brick 1.3.0 — aucune classe pour la pompe à chaleur ni la sous-station, laissée vide), libellés dans `ui.json`. Modèles : `equipment_type` (obligatoire, validé par l'API) et `manufacturer_designation` (appellation du fabricant, conservée) ; l'ancienne `category` libre est migrée intégralement dans la désignation, le type étant proposé par une copie figée des alias (`other` sans correspondance certaine). `GET /equipment-types` (libellés traduits) et `GET /equipment-types/suggestion` (proposition, jamais imposée). Exemplaires : `asset_code` unique par client, `PUT /physical-units/{id}/asset-code` audité. Migrations `8124d4500034` → `6c1d9fbc55fb` → `4daa35f4dcf1` vérifiées en aller-retour. DEFER : type sur la position (équipement) elle-même, alias propres à un client. |
| L6 | ✅ `app/equipment_status.py` : état de fonctionnement (`running`, `stopped`, `disabled`, `fault`, `unknown`) et état de communication (`online`, `offline`, `unknown` ; `unreachable` réservé à l'Edge en M3) calculés à la lecture depuis les points d'état validés (`run_status`, `fault_status`, nouvelle classe `enable_status` = Brick `Enable_Status`). Priorité : défaut, puis désactivé, puis marche. Hors ligne = aucun point d'état récent (plus de 3 intervalles attendus) : dernier état connu et sa date, `current` faux. Sans intervalle attendu : actualité « non vérifiable », jamais « en ligne » par supposition. Valeurs douteuses ignorées. Motifs explicites quand l'état n'est pas disponible (`NO_STATUS_POINT`, `NO_MEASUREMENT`). `GET /functional-locations/{id}/status` et passeport ; affichage mobile avec la date dans le fuseau du site. Historisation : DEFER M3 (les mesures sources sont déjà historisées). |

## 7. Garde-fous inchangés

- Règle non négociable 1 intacte : le vocabulaire des commandes est défini, aucune
  commande n'est codée.
- Rien n'est écrasé : les anciens statuts et titres sont migrés vers les nouveaux
  champs, jamais effacés sans l'étape de contraction.
- Chaque nouvelle table ou colonne métier : `tenant_id`, RLS forcée, test d'isolation.

## Conséquences

- `CLAUDE.md` : la qualité du langage devient un critère d'acceptation (section 7).
- La Feature Benchmark Matrix reçoit une section « Langage, codes et i18n » et trois
  nouveaux risques de blocage.
- Cette ADR passera au statut « Acceptée » avec l'accord de Mohamed, avant l'étape L2.
