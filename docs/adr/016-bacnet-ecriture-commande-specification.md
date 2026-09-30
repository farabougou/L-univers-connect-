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

## Conséquences

- `docs/spec/feature-benchmark-matrix.md` : la ligne « Arbitrage des commandes »
  (déjà DEFER) et une éventuelle future ligne « Commande BACnet » citeront cette ADR.
- Prochaine étape réelle (non déclenchée par cette ADR) : une fois la lecture seule
  validée sur le terrain, revenir sur ce document, obtenir la décision explicite
  séparée exigée par CLAUDE.md, puis seulement écrire le code.
