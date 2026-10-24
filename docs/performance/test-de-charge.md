# Test de charge progressif et borné de l'API

Document de référence de la consolidation V5 (21 octobre 2026). Il décrit l'outil, la
procédure, les mesures obtenues **en local** et **sur le staging Railway** (séparées,
jamais additionnées) et ce qui reste à mesurer.

## L'outil

- `services/api/app/load_probe.py` : la logique (paliers, critères d'arrêt, bornes, retour à
  la normale). Testée sans réseau par `tests/test_load_probe.py` (32 tests, avec mutation
  vérifiée sur le seuil d'événements).
- `services/api/scripts/load_probe.py` : la ligne de commande. **GET uniquement**, jamais
  d'écriture. Le jeton éventuel est lu dans `LOAD_PROBE_TOKEN` (jamais en argument, donc
  jamais dans l'historique du terminal). Une cible qui n'est pas locale est refusée sans
  `--allow-remote`.

Méthode : pour chaque palier, N clients envoient des requêtes l'une après l'autre (boucle
fermée) pendant une durée fixe. On relève le débit, les latences p50/p95/p99 (rang le plus
proche : une valeur réellement observée) et la répartition des statuts. La montée s'arrête
au premier critère franchi, puis une phase de reprise à **1 client** vérifie le retour à la
normale.

| Critère d'arrêt | Seuil par défaut | Pourquoi |
| --- | --- | --- |
| Erreurs 500/502/504 ou réseau | 1 % | vraie panne |
| Refus 503 (délestage) | 5 % | saturation atteinte : c'est le résultat cherché |
| Limitation 429 | 5 % | la mesure ne porte plus sur la capacité |
| Latence p99 | 5 s | inutilisable pour une personne |
| Nombre minimal d'événements | 3 | un événement isolé (1 sur 80 = 1,25 %) ne prouve rien ; il est quand même compté et nommé |
| Bornes | 5 000 requêtes, 300 s, 200 clients | un essai ne devient jamais un déni de service |

Retour à la normale : aucune erreur ni refus pendant la reprise **et** p95 au plus égal au
double de celui du premier palier (ou +50 ms).

## Mesures locales (machine de développement)

Conditions, à garder en tête pour lire les chiffres :

- Bac à sable de 4 cœurs, Python 3.11, PostgreSQL 16 **sur la même machine** que le serveur
  et que le générateur de charge (ils se partagent les cœurs).
- Serveur `uvicorn` dans un **processus séparé** (un seul), faux fournisseur d'identité
  local, vrai jeton signé RS256 vérifié par l'API.
- Base : 100 000 interventions d'un client d'essai (supprimées ensuite), la route mesurée
  est `GET /sync/interventions?limit=100&since=…` (fenêtre de 30 jours, c'est ce que le
  téléphone appelle), ≈ 12 ms de temps de service par requête (inverse du débit plafond).
- Limitation de débit **désactivée dans le lanceur de mesure uniquement** (hors dépôt) : à
  120 requêtes par minute et par personne, un seul client l'atteint en 1 s. Voir « Limitation
  de débit » ci-dessous.

### Montée complète (file d'admission de 5 s, réglage par défaut), troisième des trois passages

| Clients | Requêtes | Req/s | p50 ms | p95 ms | p99 ms | 2xx | 429 | 5xx | 503 | Réseau |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 276 | 34,4 | 27 | 35 | 38 | 276 | 0 | 0 | 0 | 0 |
| 5 | 645 | 80,4 | 58 | 93 | 168 | 645 | 0 | 0 | 0 | 0 |
| 10 | 680 | 84,5 | 108 | 232 | 323 | 680 | 0 | 0 | 0 | 0 |
| 20 | 714 | 87,9 | 210 | 364 | 394 | 714 | 0 | 0 | 0 | 0 |
| 30 | 659 | 77,2 | 370 | 548 | 686 | 659 | 0 | 0 | 0 | 0 |
| 40 | 655 | 77,9 | 491 | 709 | 793 | 655 | 0 | 0 | 0 | 0 |
| 80 | 649 | 73,1 | 1 040 | 1 369 | 1 540 | 649 | 0 | 0 | 0 | 0 |
| 150 | 733 | 75,8 | 1 668 | 4 997 | 6 578 | 733 | 0 | 0 | 0 | 0 |

Arrêt de la montée : p99 de 6,58 s (> 5 s). Reprise à 1 client : 617 requêtes, p95 29 ms,
aucune erreur. **Retour à la normale : oui.**

Reproductibilité sur 3 passages : débit entre **73 et 100 req/s** de 5 à 150 clients (le
plafond se situe vers 85 req/s) ; à 150 clients, p99 de 6,0 à 6,6 s dans les trois cas ;
**aucune erreur 5xx, aucun 503** ; retour à la normale à chaque fois (p95 de 27 à 29 ms).
Événements réseau côté client au palier de 150 clients : 3 sur 796 requêtes au premier passage
(type non relevé à ce moment-là), 1 `ReadError` sur 736 au deuxième, 0 au troisième ; un essai
isolé à 150 clients pendant 8 s n'en a produit aucun (594 réponses 200). Leur cause n'est
**pas établie** ; elle reste sous le seuil d'arrêt (1 %).

Lecture : le débit plafonne dès 5 clients (~85 req/s) puis la latence croît proportionnellement
au nombre de clients (la file s'allonge, le débit ne monte plus). C'est la signature d'un
processus unique saturé. Mesure du temps processeur du serveur (lue dans `/proc`, pendant l'essai
à file de 0,5 s de 79,5 s au total) : **0,79 cœur en moyenne**, phases légères comprises, soit
un cœur presque entièrement occupé (l'interpréteur Python n'exécute qu'un fil de calcul à la fois). La charge supplémentaire ne devient pas du débit : elle devient
de l'attente.

### Saturation et retour à la normale (file d'admission ramenée à 0,5 s)

Pour exercer le refus 503 (jamais atteint ci-dessus, car la file de 5 s absorbe 150 clients), même
montée avec `ADMISSION_QUEUE_TIMEOUT_SECONDS=0,5` :

| Clients | Req/s | p50 ms | p95 ms | p99 ms | 2xx | 503 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 40 | 82,8 | 462 | 666 | 758 | 691 | 0 |
| 80 | 81,9 | 749 | 2 327 | 3 845 | 674 | 61 (8,3 %) |

Arrêt : saturation (503 à 8,3 %). Aucune erreur 500. Reprise à 1 client : p95 17 à 20 ms, aucune
erreur, **retour à la normale : oui** (deux passages). Les 503 portent `Retry-After` et un code
stable (`SERVICE_BUSY`) ; les clients Edge réessaient déjà.

Observation à ne pas minimiser : les p95/p99 de 2,3 et 3,8 s à 80 clients dépassent largement
la file de 0,5 s. Une requête admise n'attend pas seulement son tour : elle partage le processeur
avec les autres requêtes en cours. **Hypothèse non instrumentée** : la contention de l'interpréteur
sous 30 requêtes simultanées ralentit aussi la boucle d'événements qui décide des refus. La
conséquence pratique est la même : au-delà de ~30 clients simultanés, un seul processus ne tient
pas les latences d'une interface.

### Limitation de débit (mesurée sur le vrai serveur)

Avec la limitation active (réglage de production, 120/minute et par personne), un client qui
enchaîne les requêtes reçoit 121 réponses 200 puis 429 pour 92,5 % des suivantes : la clé est
bien l'identité vérifiée (`user:<sub>`), le dépassement rend `429 RATE_LIMITED`. Pendant la phase
de reprise suivante, les 3 357 requêtes ont toutes été refusées tant que la fenêtre d'une minute
n'était pas écoulée. Ce comportement est voulu ; il rend en revanche **la limitation de débit
incompatible avec la mesure de capacité**, d'où le lanceur dédié.

À retenir pour le mobile : une synchronisation complète ne dépasse jamais 40 pages
(`DEFAULT_MAX_PAGES`), soit moins que le quota de 120 par minute.

## Mesures sur le staging Railway (anonymes, bornées)

Cible : `https://l-univers-connect-staging.up.railway.app` (une réplique, région `ams`), depuis le
bac à sable (p50 d'environ 135 ms sur une route triviale : c'est le réseau). **Ces chiffres sont dominés par le
réseau et ne sont pas comparables aux mesures locales.**

`GET /health` (exempté de la limitation de débit et du contrôle d'admission ; ne touche pas la
base) :

| Clients | Requêtes | Req/s | p50 ms | p95 ms | p99 ms | Erreurs |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 41 | 6,8 | 135 | 154 | 576 | 0 |
| 2 | 83 | 13,5 | 137 | 168 | 646 | 0 |
| 5 | 211 | 34,6 | 136 | 157 | 500 | 0 |
| 10 | 423 | 68,9 | 136 | 156 | 474 | 0 |
| 20 | 820 | 133,7 | 138 | 176 | 629 | 0 |

Montée complète sans critère franchi (1 578 requêtes au total) ; reprise à 1 client : p95 162 ms,
aucune erreur, **retour à la normale : oui**. Le débit croît linéairement avec les clients : la
route n'est pas le facteur limitant à 20 clients.

`GET /health/db` (une requête sur la vraie base, soumise à la limitation de débit anonyme) :
1 client, 77 requêtes, p50 150 ms, p95 168 ms, p99 581 ms, aucune erreur ; reprise p95 171 ms.
Volontairement limité à une trentaine de secondes pour ne pas épuiser le quota anonyme de
120/minute (sur le staging, tous les clients anonymes partagent encore un seul quota, voir
`infra/RAILWAY_STAGING.md`).

Un premier passage sur `/health` s'est arrêté à 2 clients sur **une** erreur réseau
(`RemoteProtocolError`, 1 sur 80). C'est ce qui a conduit au seuil minimal de 3 événements. Le
second passage n'en a eu aucune ; l'événement isolé reste **inexpliqué** (hypothèse non vérifiée :
fermeture d'une connexion persistante inactive par le point d'entrée de Railway).

## Première mesure authentifiée du staging (22/10/2026)

Route `/sync/interventions?limit=50`, jeton réel obtenu auprès de Keycloak par
`scripts/staging_probe.py` (jeton transmis au seul processus de mesure, absent du rapport).
**Compte de démonstration** `demo.technicien`, le compte dédié n'existant pas encore.
Déploiement `8d2c452` (PyJWT). Charge volontairement faible : 1, 2 puis 4 clients, 10 s par
palier.

| Clients | Requêtes | Req/s | p50 | p95 | p99 | Erreurs |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 66 | 6,5 | 146 ms | 165 ms | 491 ms | 0 |
| 2 | 135 | 13,5 | 146 ms | 156 ms | 188 ms | 0 |
| 4 | 269 | 26,6 | 145 ms | 168 ms | 210 ms | 0 |
| Reprise (1) | 69 | 6,8 | 145 ms | 162 ms | 190 ms | 0 |

Retour à la normale : oui. La latence ne monte pas de 1 à 4 clients : la capacité n'est pas
atteinte, ce qui n'est pas une mesure de saturation. **Aucun refus 429 sur 539 requêtes en
environ 40 secondes, alors que le quota annoncé est de 120 par minute** : c'est ce qui a révélé
que le quota par défaut ne couvre pas les routes des sous-routeurs (voir `infra/RAILWAY_STAGING.md`,
correction du 22/10/2026). Les mesures ci-dessus portent donc sur l'API sans plafond de débit (corrigé le 23/10/2026 ; le flux `/sync/*` a depuis son propre plafond de 600 par minute, que cette mesure n'atteignait pas non plus).

Limites : une seule route, un compte de démonstration (peu de données dans son client), latence
mesurée depuis le bac à sable d'exécution, pas depuis Bamako.

## Ce que ces mesures ne démontrent pas

| Limite | État |
| --- | --- |
| Saturation de l'API **authentifiée** sur Railway (route avec base, jeton, 30 requêtes en cours) | **Partiel** : première mesure faite le 22/10/2026 jusqu'à 4 clients avec le compte de démonstration (voir ci-dessus), sans saturation ; la saturation à 30 requêtes simultanées reste à mesurer avec le compte dédié (non créé : mot de passe administrateur de Keycloak inaccessible à l'assistant) et après décision sur le plafond de débit. `/sync/*` est déployé depuis le 22/10/2026. |
| Débit d'un processus **sur la machine Railway** (processeur différent du bac à sable) | non mesuré ; le plafond local de ~85 req/s n'est pas transposable tel quel. |
| Plusieurs processus ou répliques | non mesuré ; chaque processus a son pool, sa file et ses quotas (voir « Configuration de déploiement »). |
| Cause de la montée de latence à 80 clients au-delà de la file d'admission | hypothèse (contention de l'interpréteur), non instrumentée. |
| Événements réseau isolés (1 local, 1 staging) | causes non établies. |
| Tenue sur plusieurs heures, fuite de mémoire, croissance de la base | hors périmètre d'un essai de quelques minutes. |

## Rejouer

```bash
# En local (serveur lancé, limitation de débit désactivée pour l'essai seulement)
LOAD_PROBE_TOKEN=... PYTHONPATH=. python scripts/load_probe.py \
  --base-url http://127.0.0.1:8000 --path "/sync/interventions?limit=100" \
  --levels 1,5,10,20,30,40,80,150 --step-seconds 8 --label "LOCAL" --json-out local.json

# Sur le staging, une fois le compte de test créé (infra/RAILWAY_STAGING.md, « Compte de test
# authentifié ») et le dernier commit déployé. Le lanceur obtient lui-même le jeton et le passe
# au processus enfant par l'environnement : il n'apparaît ni en argument ni dans la sortie.
PYTHONPATH=. python scripts/staging_probe.py \
  --api-url https://l-univers-connect-staging.up.railway.app --allow-remote -- \
  --path "/sync/interventions?limit=50" --levels 1,2,4 --step-seconds 10 \
  --max-total-requests 300 --label "STAGING Railway"
```

Avec un quota de 120 requêtes par minute et par personne, une mesure authentifiée sur le
staging est limitée par le quota avant de l'être par la capacité. Il faut un compte d'essai
dédié, et soit un quota relevé pour la durée de l'essai, soit une mesure réduite à
~100 requêtes par minute (donc non saturante). Cette décision revient à Mohamed.
