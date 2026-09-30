# ADR 016 — BACnet, future capacité d'écriture/commande : spécification, pas d'activation

## Statut

Acceptée (30 septembre 2026), directive autonome de Mohamed du même jour : « La
future capacité d'écriture/commande doit être architecturée et spécifiée, mais ne
doit pas être activée sur une installation réelle tant que la phase de lecture seule
n'a pas été validée et que les mécanismes d'autorisation, sécurité, audit et
vérification ne sont pas prêts. »

**Ce document est une spécification, jamais une implémentation.** Aucune ligne de
code de ce document n'écrit, ni ne prépare une écriture, vers un appareil BACnet réel
ou simulé. `app/connectors/bacnet.py` reste, après cette ADR, strictement sans
fonction d'écriture — comme avant elle. Toute écriture BACnet, même vers un appareil
explicitement simulé (à la manière de `simulated_relay` pour Modbus), reste couverte
par la règle non négociable 1 de `CLAUDE.md` : elle exige une nouvelle décision
explicite séparée de Mohamed, écrite dans `CLAUDE.md`, avant qu'une seule ligne de
code d'écriture BACnet ne soit ajoutée à ce dépôt. Cette ADR ne constitue pas cette
décision.

## Pourquoi spécifier maintenant, sans coder

Objectif énoncé par Mohamed : « quand nous arriverons sur la première GTB réelle,
nous devons avoir le moins de développement possible à faire sur place ». La
découverte, la sémantique et la relève (BACnet V1, ADR 015) couvrent la lecture ;
l'écriture est la suite naturelle une fois la lecture validée sur le terrain. Fixer
l'architecture maintenant évite deux risques : concevoir une commande BACnet dans
l'urgence sous pression d'un client (risque de raccourci de sécurité), et découvrir
tardivement une incompatibilité avec le moteur de commande déjà construit pour Modbus.

## 1. Réutiliser le moteur de commande existant, jamais un second moteur

Un moteur de commande complet existe déjà et fonctionne en production simulée pour
Modbus (ADR 012 §2.5, `app/commands.py`, `app/routers/commands.py`,
`scripts/modbus_daemon.py`) : cycle `pending` → `sent` → `acknowledged` → `verified`
(avec `failed`/`unconfirmed`/`timed_out`), vérification de l'état réel contre l'état
demandé (jamais « exécutée » avant vérification), audit automatique, rôles
(`_COMMAND_ROLES`), et une seule exception nommée à la règle non négociable 1 :
`device_type = "simulated_relay"` (`app/connectors/device_mapping.py`,
`app/connectors/simulated_actuator.py` — la seule fonction d'écriture du dépôt).

**Décision : BACnet n'aura jamais de second moteur de commande.** Le jour où
l'écriture BACnet sera autorisée, elle passera par exactement le même
`app/commands.py`, les mêmes routes `/commands` (humain) et `/edge/commands`
(appareil), le même cycle de statuts. Le seul ajout sera, côté connecteur, une
fonction de écriture BACnet (`write_bacnet_point` ou équivalent, **non écrite par
cette ADR**) et son branchement dans le démon (`scripts/bacnet_daemon.py` ou un futur
`scripts/bacnet_command_daemon.py`, à trancher au moment de l'implémentation réelle).

## 2. Chaîne complète (observer → agir), telle que déjà exigée par la Feature Benchmark
Matrix (« Observe → Understand → Decide → Simulate si nécessaire → Authorize →
Execute → Verify → Learn »)

| Étape | Aujourd'hui (lecture seule) | Demain (écriture BACnet, une fois autorisée) |
|---|---|---|
| Observe | `read_bacnet_points` (relève cyclique) | Inchangé |
| Understand | Découverte + correspondance sémantique (ADR 015) | Inchangé |
| Decide | Une personne (règle de seuil, ADR 012 §2.15) ou manuellement | Inchangé : jamais un LLM, jamais automatique sans politique explicite |
| Simulate | `GET /configs/{id}/simulate` (règles) | Étendre au calcul d'impact d'une commande avant envoi (DEFER, non spécifié ici) |
| Authorize | RBAC (`_COMMAND_ROLES`), tenant (RLS) | Identique + **politique de sécurité spécifique à l'écriture** (section 3) |
| Execute | Aucune (lecture seule) | `POST /commands` (humain) → `app/commands.py` → Edge (`GET /edge/commands`) → écriture BACnet (WriteProperty) |
| Verify | Score de confiance, fraîcheur | ReadProperty après écriture, comparaison à la valeur demandée (`evaluate_command_timeout`, réutilisé) |
| Audit | Déjà systématique | Déjà systématique (`append_audit_entry`), rien à ajouter |
| Learn | DEFER (hors périmètre 12 mois) | DEFER, inchangé |

## 3. Ce qui manque avant une activation, même simulée

Cette liste est la condition d'activation, pas un travail à faire maintenant :

1. **Validation terrain de la lecture seule** (ADR 015, section 6) — condition
   explicite de Mohamed, littérale : rien d'écriture avant que la lecture ait fait ses
   preuves sur au moins une installation réelle.
2. **Décision explicite séparée** (CLAUDE.md, règle 1) nommant precisément le
   `device_type` simulé autorisé (ex. `bacnet_simulated_relay`) — sur le modèle de la
   décision du 24/09/2026 pour Modbus. Cette ADR ne l'est pas.
3. **Politique de sécurité spécifique à BACnet**, au-delà du RBAC déjà en place :
   - BACnet distingue l'écriture directe (`WriteProperty` sur `present-value`) de
     l'écriture arbitrée (`WriteProperty` sur une entrée du tableau de priorités,
     16 niveaux) — l'arbitrage des commandes (ADR 012 §2.5) reste DEFER, mais une
     future commande BACnet devra déclarer laquelle des deux elle utilise ; ne
     jamais écrire sur `present-value` directement une fois l'arbitrage retenu
     (une autre source BACnet du même réseau écraserait silencieusement la valeur).
   - Confirmer par une commande BACnet `ReadPropertyMultiple` de
     `priority-array` que rien d'autre ne détient déjà une priorité plus haute avant
     d'écrire, pour éviter une commande qui semble acceptée mais reste sans effet.
4. **Vérification systématique** : toute commande BACnet doit relire l'état réel
   après écriture (comme Modbus), avec un délai adapté à la volatilité du protocole
   (BACnet ne notifie pas nativement un changement sans abonnement COV — prévoir un
   ré-essai de lecture avec backoff, pas une seule tentative).
5. **Audit renforcé** : consigner, en plus des champs déjà audités (point, valeur
   demandée, valeur réelle, échec), le niveau de priorité BACnet utilisé et l'identité
   de l'agent Edge qui a exécuté l'écriture.
6. **Isolation OT/IT inchangée** : l'agent Edge reste le seul processus qui dialogue
   en BACnet ; l'API ne fait jamais d'écriture réseau elle-même (même principe déjà
   appliqué à la découverte, ADR 015).

## 4. Ce que cette ADR ne fait pas

- Elle n'ajoute aucune fonction d'écriture à `app/connectors/bacnet.py`.
- Elle ne crée aucun `device_type` simulé pour BACnet (`bacnet_simulated_relay` n'existe
  nulle part dans le code — le nom n'est cité ici qu'à titre d'exemple de nommage
  cohérent avec `simulated_relay`, pas comme une déclaration).
- Elle ne modifie aucune règle non négociable.
- Elle ne préjuge pas du calendrier : l'activation dépend de la validation terrain de
  la lecture seule (ADR 015) et d'une décision explicite distincte de Mohamed.

## 5. Détail complémentaire (30 septembre 2026, à la suite de la visite terrain BIVWAK)

Mohamed a demandé d'approfondir la spécification pendant l'attente de l'adaptateur
réseau nécessaire à la validation terrain de la V1 — toujours **sans écrire une seule
ligne de code d'écriture**, pour les mêmes raisons qu'à la section 4. Ce qui suit
précise la section 3 point par point, pour que l'implémentation réelle (le jour venu)
n'ait plus de décision de conception à prendre, seulement du code à écrire.

### 5.1 Niveau de priorité BACnet à utiliser

BACnet définit un tableau de 16 niveaux de priorité par propriété commandable
(`priority-array`), 1 étant le plus fort. Convention déjà répandue chez les grands
éditeurs (Tridium Niagara, Schneider EcoStruxure) et retenue ici :

| Niveau | Usage | Notre future commande |
|---|---|---|
| 1-2 | Sécurité vie humaine (manuelle/automatique) | **Jamais écrit** — hors périmètre produit |
| 3-4 | Disponible | Non utilisé |
| 5 | Contrôle d'équipement critique | Non utilisé |
| 6 | Minimum marche/arrêt | Non utilisé |
| 7 | Disponible | Non utilisé |
| **8** | **Opérateur manuel** | **Niveau retenu** pour toute commande émise par une personne via `/commands` |
| 9-15 | Disponible (automatismes) | Non utilisé |
| 16 | Valeur de repli (« relinquish default ») | Jamais écrit directement — c'est l'état de l'objet en l'absence de toute commande |

Annuler une commande (relâcher la main) signifie un `WriteProperty` avec une valeur
nulle (« relinquish ») au niveau 8, jamais une écriture au niveau 16.

### 5.2 Vérification par relecture (BACnet ne notifie pas nativement un changement)

Sans abonnement COV (hors périmètre), la vérification suit un ré-essai à intervalles
croissants plutôt qu'une seule lecture : **+1 s, +3 s, +7 s** après l'écriture
(fenêtre totale 15 s), en réutilisant le cycle de l'agent Edge déjà en place plutôt
qu'un nouveau processus. Au-delà de cette fenêtre sans correspondance, la commande
suit le chemin déjà existant (`failed` si une valeur différente est lue, `unconfirmed`
puis `timed_out` via `UNCONFIRMED_AFTER` si rien n'est lu — `app/commands.py`,
inchangé).

### 5.3 Détection de conflit de priorité avant écriture

Avant tout `WriteProperty`, un `ReadPropertyMultiple` de `priority-array` vérifie
qu'aucun niveau 1 à 7 n'est déjà actif : si c'en est le cas, la commande échoue
immédiatement (`failed`, motif dédié — proposé : `BACNET_HIGHER_PRIORITY_ACTIVE`)
plutôt que d'être acceptée puis silencieusement sans effet. Un nouvel événement
persistant suivrait le même modèle que les autres (`app/events.py`) — proposé :
`COMMAND_BACNET_PRIORITY_CONFLICT`, nom à confirmer au moment de l'implémentation.

### 5.4 Schéma de données envisagé — aucune nouvelle table

La table `commands` existante (migration 1cb0a1548c63) reste protocole-agnostique :
`point_id`, `requested_value`, `actual_value`, `status`, `edge_device_id`, etc. Le
point BACnet ciblé n'a besoin d'aucun nouveau mécanisme d'adressage : une fois issu
d'une proposition de découverte acceptée (ADR 015), un point porte déjà tout ce qu'il
faut (équipement, mapping actif, type/instance d'objet BACnet) pour que l'Edge sache
où écrire.

Le seul ajout de schéma anticipé — **non créé par cette ADR, à faire au moment de
l'implémentation réelle** — serait une colonne `protocol_metadata` (JSONB, nullable)
sur `commands`, plutôt qu'une colonne par protocole (`bacnet_priority`, etc.) : elle
resterait vide pour Modbus, et porterait `{"bacnet_priority": 8}` pour BACnet. Ce
choix évite d'ajouter une colonne à chaque nouveau protocole doté un jour d'une
capacité de commande (OPC UA, par exemple).

### 5.5 Audit renforcé — champs exacts

En plus des champs déjà consignés par `append_audit_entry` sur chaque transition de
`app/commands.py`, une commande BACnet ajouterait dans son `payload` :
`bacnet_priority` (l'entier utilisé, section 5.1), `object_type` et
`object_instance` (adressage BACnet du point, déjà connus du mapping), et
`edge_device_id` (déjà une colonne de `commands`, dupliqué dans le payload d'audit
comme le reste des colonnes le sont déjà pour les autres protocoles).

### 5.6 Signature de fonction proposée (illustration, jamais ajoutée au dépôt)

Pour mémoire uniquement — ce bloc n'est pas du code de ce dépôt, seulement la forme
que prendrait la fonction le jour de l'implémentation réelle, une fois les deux
conditions de la section 3 réunies :

```
# app/connectors/bacnet.py — À ÉCRIRE UNIQUEMENT APRÈS :
#   1. validation terrain de la lecture seule (ADR 015 §6)
#   2. décision explicite séparée de Mohamed dans CLAUDE.md
#
# def write_bacnet_point(
#     address: str, object_type: str, object_instance: int,
#     value: float, priority: int = 8, timeout: float = 3.0,
# ) -> None: ...
```

### 5.7 Nom de `device_type` simulé — proposition, pas une déclaration

Sur le modèle de `simulated_relay` (Modbus), le nom proposé pour la future décision
de Mohamed serait `bacnet_simulated_relay`, dans `SIMULATED_DEVICE_TYPES`
(`app/connectors/device_mapping.py`). Cette ADR ne l'y ajoute pas : le nom est cité
ici uniquement pour que la décision, le jour venu, n'ait plus qu'à être écrite dans
CLAUDE.md sans nouvelle réflexion de nommage.

## Conséquences

- `docs/spec/feature-benchmark-matrix.md` : la ligne « Arbitrage des commandes »
  (déjà DEFER) et une éventuelle future ligne « Commande BACnet » citeront cette ADR.
- Prochaine étape réelle (non déclenchée par cette ADR) : une fois la lecture seule
  validée sur le terrain, revenir sur ce document, obtenir la décision explicite
  séparée exigée par CLAUDE.md, puis seulement écrire le code — la section 5
  ci-dessus élimine déjà les décisions de conception restantes.
