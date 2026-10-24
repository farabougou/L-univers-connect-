# Staging privé sur Railway

Ce guide couvre le passage LOCAL → STAGING (Mohamed, 24/09/2026). Il donne les
étapes exactes à exécuter dans le tableau de bord Railway (et, pour le
stockage, chez un fournisseur compatible S3) : ce sont des actions sur des
comptes externes, que cette session ne peut pas effectuer elle-même (pas
d'accès à ton compte Railway depuis cet environnement). Tout ce qui pouvait
être préparé sans ces comptes l'a été (Dockerfiles, variables, realm
Keycloak) — voir la liste en fin de document.

## Principe : trois environnements jamais mélangés

Railway a un mécanisme natif pour ça : plusieurs **Environments** dans un même
projet, chacun avec ses propres instances de service (donc sa propre base de
données) et ses propres variables. On l'utilise ainsi :

```
LOCAL (ton poste, docker-compose)
  → STAGING (environnement Railway "staging", ce guide)
    → PRODUCTION (futur environnement Railway "production", pas encore créé)
```

Aucune base de données, aucun secret, aucun realm Keycloak n'est jamais
partagé entre deux environnements.

## Ce qui a déjà été préparé (dans le dépôt)

| Fichier | Rôle |
|---|---|
| `services/api/Dockerfile` | Image de l'API. Construit avec **la racine du dépôt** comme contexte (pas `services/api`), pour pouvoir embarquer `shared/i18n` — voir la section 3. |
| `services/api/scripts/docker-entrypoint.sh` | Vérifie que `shared/i18n` est bien présent, joue les migrations Alembic, puis démarre `uvicorn`. |
| `apps/web/Dockerfile` | Image du web (Next.js en mode `standalone`, construit avec `apps/web` comme contexte). |
| `.env.staging.example`, `apps/web/.env.staging.example`, `apps/mobile/.env.staging.example` | Noms des variables à définir dans Railway pour cet environnement (jamais de vraie valeur dans ces fichiers). |
| `infra/keycloak/realm-staging.json` | Realm Keycloak de staging : mêmes rôles qu'en local, redirections resserrées (plus de `"*"`) — deux jetons `__WEB_STAGING_DOMAIN__` à remplacer une fois le domaine connu (déjà fait pour ce staging : `discerning-delight-staging.up.railway.app`). |
| `railway.json` (racine) et `apps/web/railway.json` | Configuration Railway "as code" par service — chaque service Railway lit le `railway.json` de son propre "Root Directory", donc l'API (Root Directory = racine) et le web (Root Directory = `apps/web`) ont chacun le leur, pour ne jamais dépendre d'un réglage manuel de "Dockerfile Path" dans l'interface. |
| `apps/web/public/.gitkeep` | Git ne suit pas les dossiers vides : sans ce fichier, `apps/web/public/` n'existe pas du tout dans un clone frais (dont celui de Railway), et l'étape `COPY --from=builder /app/public ./public` du Dockerfile web échoue. |
| `apps/web/Dockerfile` (`ENV HOSTNAME=0.0.0.0`) | Sans ça, le serveur Next.js "standalone" écoute sur l'identifiant interne du conteneur (celui que Docker fixe automatiquement) plutôt que sur toutes les adresses réseau : injoignable de l'extérieur (502 systématique, y compris sur un fichier statique). |
| `apps/web/src/app/api/health/route.ts` | Point de contrôle de santé dédié pour Railway, indépendant de `/login` (rendu dynamique, trop fragile pour ce rôle). |
| `apps/web/src/lib/config.ts` | Complète `https://` devant `OIDC_ISSUER`, `API_URL`, `APP_URL` si la variable a été saisie sans schéma — évite un échec silencieux de l'échange OIDC. |

## Étape 1 — Projet et environnement Railway

1. Dans Railway, créer un projet (ou utiliser un projet existant).
2. Renommer l'environnement par défaut en `staging`, ou en créer un nouveau
   nommé `staging` (bouton "New Environment").
3. Connecter le dépôt GitHub `farabougou/L-univers-connect-` au projet
   (Railway le demande à la création du premier service).

## Étape 2 — PostgreSQL

1. Dans l'environnement `staging` : "New" → "Database" → "PostgreSQL".
   Railway le provisionne seul.
2. Rien d'autre à faire ici : la variable `DATABASE_URL` de ce service sera
   référencée par le service API à l'étape suivante
   (`${{Postgres.DATABASE_URL}}`, une référence Railway, jamais une valeur
   recopiée à la main).

## Étape 3 — Service API (`services/api`)

1. "New" → "GitHub Repo" → sélectionner ce dépôt.
2. Réglages du service :
   - **Root Directory** : `/` (la racine du dépôt — nécessaire pour que le
     Dockerfile puisse copier `shared/i18n`, situé hors de `services/api`).
   - **Dockerfile Path** : `services/api/Dockerfile`.
   - **Healthcheck Path** : `/health` (déjà présent dans l'API).
3. Variables d'environnement (`.env.staging.example` à la racine du dépôt) :
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `OIDC_ISSUER`, `OIDC_AUDIENCE=paios-api`
   - `DEVICE_TOKEN_SECRET` = générer avec `openssl rand -hex 32`
   - `STORAGE_*` = voir étape 5
   - `ENVIRONMENT=staging`, `LOG_LEVEL=INFO`
   - Facultatif : `DB_POOL_SIZE` (10), `DB_MAX_OVERFLOW` (20),
     `DB_POOL_TIMEOUT_SECONDS` (15), `DB_POOL_RECYCLE_SECONDS` (1800) — pool de
     connexions Postgres, valeurs par défaut prudentes (audit V5 du
     20/10/2026) ; à ne changer que si les journaux montrent une attente.
   - Facultatif : `FORWARDED_ALLOW_IPS` — voir « Limitation de débit » ci-dessous.
   - Facultatif : `MAX_IN_FLIGHT_REQUESTS` (0 = capacité du pool) et
     `ADMISSION_QUEUE_TIMEOUT_SECONDS` (5) — voir « Capacité et plusieurs
     processus » ci-dessous.
4. Déployer. Railway assigne un domaine public (`*.up.railway.app`) — c'est
   ton **URL API**.

CORS : rien à configurer. Le web (`apps/web`) n'appelle jamais l'API depuis le
navigateur — uniquement depuis son propre serveur Next.js (vérifié dans le
code : un seul composant client existe, `LoginError.tsx`, et il n'appelle pas
l'API). Le mobile appelle l'API directement depuis l'appareil, hors du cadre
CORS (qui ne concerne que les navigateurs). Si un jour un composant du
navigateur appelle l'API directement, ajouter `CORSMiddleware` dans
`app/main.py` à ce moment-là seulement.

### Limitation de débit (audit V5 du 20/10/2026)

L'API limite le débit **par identité vérifiée** (personne ou appareil Edge),
pas par adresse IP : le serveur Next.js appelle l'API au nom de toutes les
personnes connectées, sans transmettre leur adresse, donc une clé par IP aurait
fait partager un seul quota de 120 requêtes par minute à tous les utilisateurs
de tous les clients. Un jeton non vérifiable (falsifié, expiré, clés de
signature pas encore en cache) retombe sur le quota de l'adresse IP.

Seules les requêtes **sans jeton** (dont `POST /devices/auth`, limité à 10 par
minute, cible possible d'une force brute) dépendent de l'adresse IP du client.

**Correction du 21/10/2026.** La version précédente de ce paragraphe supposait
que le proxy de Railway renseigne `X-Forwarded-For`. La documentation de
Railway (« Specs & Limits », en-têtes de requête) ne garantit que **`X-Real-IP`**
(adresse du client), `X-Forwarded-Proto`, `X-Forwarded-Host`. Et uvicorn ne lit
`X-Forwarded-For` que pour les proxys de `FORWARDED_ALLOW_IPS` (par défaut
`127.0.0.1`). Conséquence tant que rien n'est configuré : **toutes** les requêtes
anonymes de la plateforme partagent l'adresse du proxy, donc un seul quota de 10
authentifications d'appareil par minute pour toute la flotte, qu'une seule
personne peut épuiser. C'est strict, jamais permissif, mais c'est une fragilité de
disponibilité.

Réponse : la variable **`CLIENT_IP_HEADER`** (vide par défaut = comportement
inchangé). Renseignée, l'application lit l'adresse dans cet en-tête, seulement
si c'est **une seule adresse IP valide**, sinon elle retombe sur la connexion.

Activation sur Railway, **dans cet ordre** :

1. `CLIENT_IP_HEADER=X-Real-IP` sur le service API, redéployer.
2. **Essai anti-usurpation** (obligatoire) : depuis un même poste, envoyer 12 fois
   `POST /devices/auth` avec un en-tête `X-Real-IP` différent à chaque envoi
   (`1.1.1.1`, `1.1.1.2`, ...). Si Railway écrase bien l'en-tête par la vraie
   adresse, les envois partagent un seul quota et le 11e répond **429**. Si au
   contraire aucun 429 n'apparaît, Railway laisse passer l'en-tête du client : un
   client peut se fabriquer des quotas à volonté. **Dans ce cas, remettre
   `CLIENT_IP_HEADER` à vide immédiatement.**
3. Essai complémentaire : deux postes (ou deux réseaux) différents doivent chacun
   disposer de leur propre quota de 10 par minute.

**Outil de l'essai.** L'essai est automatisé : `PYTHONPATH=. python scripts/spoof_test.py
--api-url https://<API_STAGING> --allow-remote --json-out preuve-x-real-ip.json` (depuis
`services/api`). Deux phases de 12 envois de `POST /devices/auth` (adresses de la plage de test
198.18.0.0/15, secret bidon, rien n'est créé). Phase témoin : le même `X-Real-IP` partout, le 11e
envoi doit répondre 429, sinon la limite n'est pas observable et l'essai ne conclut pas. Phase
d'usurpation : un `X-Real-IP` différent à chaque envoi. Verdicts : `NOT_SPOOFABLE` (code 0),
`SPOOFABLE` (code 1, **remettre `CLIENT_IP_HEADER` à vide aussitôt**), `INCONCLUSIVE` (code 3).
Preuve JSON sans secret. Testé contre la vraie application avec et sans proxy qui écrase
l'en-tête (`tests/test_spoof_test.py`, 22 tests, mutations détectées).

**Résultat du 22/10/2026 sur le staging : `INCONCLUSIVE`, et ce n'est pas anodin.** La limite de
10 par minute de `POST /devices/auth` n'est pas observable : 60 envois depuis la même source,
avec le même `X-Real-IP`, ont tous été traités (401), sans aucun 429. En local, le même scénario
donne 429 dès le 11e envoi. Le défaut vient donc du déploiement, pas du code. Une première
version de l'outil, sans phase témoin, avait conclu `SPOOFABLE` à tort ; corrigé.

Hypothèses, non tranchées (l'assistant n'a pas accès aux variables ni aux journaux de Railway) :
1. plusieurs instances du service API, chacune avec ses compteurs en mémoire (le quota se
   multiplie par le nombre d'instances) ;
2. l'adresse de connexion vue par l'application change d'une requête à l'autre (plusieurs
   proxys Railway), donc chaque requête tombe dans un compteur différent ;
3. un réglage inattendu (`RATE_LIMIT_STORAGE_URI` ou autre).

**Élément nouveau du 23/10/2026.** Après la correction du quota par défaut, `/me` refuse
exactement à la 121e requête sur le staging (mesure avec un jeton réel). Avec plusieurs
instances, les compteurs en mémoire se seraient additionnés : le service API n'a donc **qu'une
instance** et l'hypothèse 1 est écartée. Il reste l'hypothèse 2 (l'adresse de connexion vue par
l'application change d'une requête à l'autre) ou 3 (réglage inattendu). `/devices/auth` classe
par adresse IP, justement la valeur instable : avec le même `X-Real-IP` fixe et `CLIENT_IP_HEADER`
vide, chaque requête retombe dans un compteur différent.

**Conséquence : activer `CLIENT_IP_HEADER=X-Real-IP` est précisément ce qui peut rendre la limite
effective, et l'essai devient faisable.** Si Railway écrase bien l'en-tête par l'adresse réelle du
client, la clé devient stable : la phase témoin observe le 429 à la 11e requête, puis la phase
d'usurpation conclut. Le risque de la fenêtre d'essai est nul : aujourd'hui, aucune limite n'est
effective sur cette route ; si l'en-tête est usurpable, la situation reste celle d'aujourd'hui, et
le réglage est retiré. Procédure : (1) service API, Variables, ajouter `CLIENT_IP_HEADER` =
`X-Real-IP`, redéployer ; (2) lancer `scripts/spoof_test.py` (voir plus haut) ; (3) conserver le
réglage si le verdict est `NOT_SPOOFABLE`, le retirer sinon, et joindre la preuve JSON ici.

**À relever dans le tableau de bord Railway** (service API) pour confirmer : la présence de
`CLIENT_IP_HEADER` et de `RATE_LIMIT_STORAGE_URI`, et la ligne `capacity.checked` du journal de
démarrage (elle indique le nombre de réplicas attendu et l'en-tête configuré). Conséquence
pratique : **la protection contre l'essai de secrets sur `POST /devices/auth` n'est pas
effective sur le staging aujourd'hui.** Les secrets d'appareil sont aléatoires et comparés en
temps constant, et le mode par clé publique n'a pas de secret à deviner, mais la défense en
profondeur annoncée manque.

Pourquoi ne pas simplement mettre `FORWARDED_ALLOW_IPS` : **ne jamais** mettre
`FORWARDED_ALLOW_IPS=*` (uvicorn retiendrait la première adresse de
`X-Forwarded-For`, que le client contrôle), et la plage d'adresses du proxy n'est
pas documentée par Railway, donc pas vérifiable ici.

**Correction du 22/10/2026 : le quota par défaut ne couvre pas toutes les routes.** Mesuré sur
le staging avec un jeton réel : environ 540 requêtes en moins d'une minute sur
`/sync/interventions`, aucun refus 429. Reproduit en local : seules `/me` (définie sur
l'application) et les routes décorées explicitement (`POST /devices/auth`, 10 par minute et par
adresse) sont limitées ; les routes des sous-routeurs (`/sites`, `/points`, `/sync/*`...) ne
le sont pas. Cause : FastAPI 0.141 range ces routes dans des objets internes sans attribut
`endpoint`, donc l'intergiciel de `slowapi` ne retrouve pas la fonction à contrôler et ne
contrôle rien, sans erreur ni journal. Ce que ce paragraphe affirmait plus haut (« 120 requêtes
par minute et par personne ») ne vaut donc que pour ces deux familles de routes.

Ce qui protège quand même : le contrôle d'admission (`app/admission.py`) borne les requêtes
simultanées, et toutes ces routes exigent un jeton valide. Ce qui manque : un plafond de débit
par personne ou par appareil sur le reste de l'API. Écart documenté par
`tests/test_rate_limit_coverage.py` (témoin `/me` qui passe, trois routes de sous-routeurs en
`xfail` strict : la CI échouera le jour où le mécanisme sera corrigé, pour forcer à retirer la
marque).

**Corrigé le 23/10/2026** (`app/rate_limit.py`) : `find_route_handler` retrouve la fonction de
chaque route par l'aide publique de FastAPI (`iter_route_contexts`), et
`DefaultRateLimitMiddleware` l'utilise à la place de la recherche de `slowapi`. Le quota par
défaut garde sa politique d'origine : 120 requêtes par minute, par personne ou appareil, et
**par route**. `tests/test_rate_limit_coverage.py` parcourt les 177 routes de l'application
(aucune ne peut redevenir exemptée en silence lors d'une mise à jour) et vérifie le refus à la
121e requête sur plusieurs familles de routes ; le `xfail` a été retiré. Exception voulue : le
flux `/sync/*` du mobile a son propre plafond de **600 par minute** (`SYNC_RATE_LIMIT`), car le
premier parcours pagine en masse (500 lignes au plus par page) et l'application ne gère pas le
refus 429 : le quota général l'aurait interrompu à 24 000 lignes. Aucun rafraîchissement
automatique n'existe dans le web ni le mobile, et les démons Edge appellent chaque route 1 à 3
fois par minute : l'usage normal reste très en dessous.

**Ce que cette correction ne règle pas :** la limite de 10 par minute de `POST /devices/auth`
n'est toujours pas observable sur le staging (voir plus bas), cause à relever dans Railway.

### Capacité et plusieurs processus (audit V5 du 20/10/2026)

Mesuré sur un processus `uvicorn` unique, base de 800 000 lignes, requêtes
authentifiées sur des listes de 50 lignes : **environ 85 requêtes par seconde
par processus**, constantes de 10 à 300 clients simultanés, sans aucune erreur.

Le **contrôle d'admission** (`app/admission.py`) borne les requêtes traitées en
même temps à la capacité du pool de connexions (`DB_POOL_SIZE` +
`DB_MAX_OVERFLOW`, soit 30 par défaut). Sans lui, au-delà d'environ 30 requêtes
simultanées, les fils d'exécution se bloquaient tous à attendre une connexion
détenue par une requête qui attendait elle-même un fil : le débit s'effondrait
et les requêtes finissaient en erreur 500 après 15 secondes. Les requêtes en
trop patientent au plus `ADMISSION_QUEUE_TIMEOUT_SECONDS`, puis reçoivent un
`503` (`SERVICE_BUSY`) avec `Retry-After: 2`, que les agents Edge réessayent.
`/health` n'y est jamais soumise.

**Configuration réelle constatée le 21/10/2026** (lecture de l'environnement
`staging` de Railway) : **1 réplique** (région `ams`), **1 processus** (aucune
variable `WEB_CONCURRENCY`), aucune variable de pool ni de requêtes en cours :
donc les valeurs par défaut (pool 10 + 20 = **30 connexions**, **30 requêtes
simultanées**), compteurs de débit **en mémoire**. Avec une seule instance, des
compteurs en mémoire sont exacts : aucun stockage partagé n'est nécessaire
aujourd'hui.

Pour augmenter la capacité, lancer plusieurs processus avec la variable
`WEB_CONCURRENCY` (reconnue par `uvicorn`) et/ou plusieurs répliques. Chaque
processus a son propre pool, sa propre limite d'admission **et son propre
compteur de limitation de débit** :

- Connexions Postgres totales = processus x répliques x (`DB_POOL_SIZE` +
  `DB_MAX_OVERFLOW`). Rester sous `max_connections` de Postgres, **moins 10** de
  réserve (administration, migrations, sauvegardes). Par exemple
  `WEB_CONCURRENCY=2` avec les valeurs par défaut : 60 connexions.
- Railway n'indique pas le nombre de répliques à l'application : le déclarer avec
  **`EXPECTED_REPLICAS`** pour que la vérification ci-dessous les compte.
- `MAX_IN_FLIGHT_REQUESTS` peut être **abaissé**, jamais relevé au-dessus de la
  capacité du pool : une valeur plus haute est ramenée à cette capacité (au-dessus,
  on retrouve l'interblocage décrit plus haut).
- Dès que `WEB_CONCURRENCY` x `EXPECTED_REPLICAS` dépasse 1, les quotas de débit
  en mémoire sont multipliés par ce nombre : passer à un stockage partagé avec
  **`RATE_LIMIT_STORAGE_URI=redis://...`** et ajouter la bibliothèque `redis` aux
  dépendances de l'API (non installée aujourd'hui, car inutile avec une seule
  instance). Le comportement avec un vrai Redis **n'a pas pu être vérifié ici**
  (aucun Redis disponible) : à essayer sur le staging avant de s'y fier.

**Vérification automatique au démarrage** (`app/capacity.py`) : l'API lit
`max_connections` sur la vraie base et écrit une ligne `capacity.checked` dans le
journal (pool, requêtes en cours, processus, répliques, `max_connections`,
stockage des quotas), plus un avertissement par incohérence
(`capacity.connections_over_budget`, `capacity.rate_limit_not_shared`,
`capacity.admission_above_pool`). Elle ne bloque jamais le démarrage. Après chaque
changement de configuration, lire cette ligne dans les journaux Railway.

**Mesure de la capacité** : `services/api/scripts/load_probe.py` monte la charge par
paliers, s'arrête au premier critère franchi (erreurs, refus 503, limitation 429,
latence p99, bornes de requêtes et de durée) et vérifie le retour à la normale. Résultats
locaux et staging, limites et commandes : `docs/performance/test-de-charge.md`. Mesure
locale d'un seul processus : plafond d'environ 85 requêtes par seconde sur
`/sync/interventions`, saturé dès 5 clients simultanés ; pour dépasser ce plafond, il faut
plusieurs processus (donc plus de connexions, voir le calcul ci-dessus), pas un pool plus grand.

### Compte de test authentifié (staging)

Pour mesurer les routes authentifiées (par exemple `/sync/*`) sans utiliser un compte de
démonstration. Aucun secret ne passe par le dépôt, une conversation ou un journal.

1. **Créer le compte** (une fois), par la personne qui détient le mot de passe administrateur de
   Keycloak (variable du service Keycloak sur Railway, masquée pour les assistants) :

   ```bash
   cd services/api
   PYTHONPATH=. python scripts/staging_account.py create \
     --keycloak-url https://virtuous-communication-staging.up.railway.app
   ```

   Le mot de passe administrateur est demandé sans affichage (ou lu dans
   `KEYCLOAK_ADMIN_PASSWORD`). Le script crée `loadtest.staging` avec le seul rôle
   `technicien`, rattaché au client indiqué par `--tenant-id` (**ce client doit exister dans
   la base du staging** ; sinon l'API répondra sans données), et écrit un mot de passe
   aléatoire dans `~/.config/paios/staging-loadtest.env` (droits 0600). Rien n'est affiché.
   `--rotate` renouvelle le mot de passe.
2. **Mesurer** : `scripts/staging_probe.py` lit ce fichier (refusé s'il est lisible par
   d'autres), demande un jeton de courte durée à Keycloak, et le passe à `load_probe.py`
   **uniquement par l'environnement du processus enfant** (jamais en argument, jamais
   enregistré ni affiché) :

   ```bash
   PYTHONPATH=. python scripts/staging_probe.py --api-url https://<API_STAGING> --allow-remote -- \
     --path "/sync/interventions?limit=50" --levels 1,2,4 --step-seconds 10 --label staging
   ```

   Le quota de 120 requêtes par minute et par utilisateur s'applique : la montée s'arrête à la
   première limitation, voulu.
3. **Désactiver les comptes de démonstration** (leur mot de passe est publié dans
   `infra/README.md`, et le staging est sur Internet) :
   `scripts/staging_account.py disable-demo-users --yes --keycloak-url ...` (réversible depuis
   la console Keycloak).

État au 21/10/2026 : outils écrits et testés contre un faux Keycloak (15 tests, mutations
vérifiées) ; **compte non créé** (mot de passe administrateur inaccessible à l'assistant), donc
aucune mesure authentifiée du staging.

### Quand Railway reconstruit (chemins surveillés, 24/10/2026)

Constat : chaque poussée sur la branche relançait une construction pour l'API **et** pour le web,
même pour un commit de documentation. Le 24/10/2026 à 09:27 UTC, la construction de l'image de
l'API a échoué (« Failed to build an image ») pour un commit qui n'avait modifié que deux fichiers
de documentation : les entrées de l'image (`services/api`, `shared/i18n`, `railway.json`) étaient
identiques, octet pour octet, à celles du commit précédent, construit et déployé avec succès.
L'échec n'était donc pas causé par notre code (les journaux de construction ne sont pas lisibles
sans le connecteur Railway ; le service en place a continué de répondre, un déploiement échoué ne
remplaçant pas celui qui tourne). Les 11 exécutions de CI précédentes étaient vertes.

Réponse : `build.watchPatterns` dans chaque `railway.json` (documentation Railway : motifs de style
gitignore, relatifs à la racine du dépôt **même quand un Root Directory est défini**, donc écrits
avec le chemin complet ; un commit qui ne touche aucun fichier correspondant ne crée aucun
déploiement).

| Service | Motifs | Pourquoi |
| --- | --- | --- |
| API (`railway.json`, Root Directory `/`) | `/services/api/**`, `/shared/i18n/**`, `/railway.json` | Tout ce que le Dockerfile copie, plus sa propre configuration |
| Web (`apps/web/railway.json`, Root Directory `apps/web`) | `/apps/web/**` | Le web embarque ses catalogues dans `src/i18n` (copiés par `npm run i18n:sync` et suivis par git) |

À vérifier à la première poussée de ce réglage : le commit modifie `railway.json` et
`apps/web/railway.json`, donc il doit créer **un** déploiement de l'API et **un** du web ; un
commit de documentation seule ne doit plus en créer. Si un changement de code ne déclenchait plus
de déploiement, annuler en retirant la ligne `watchPatterns` (retour au comportement d'avant). Un
fichier lu par l'image doit toujours figurer dans les motifs : l'ajouter ici en même temps qu'au
Dockerfile.

## Étape 4 — Service Web (`apps/web`)

1. "New" → "GitHub Repo" → le même dépôt.
2. Réglages :
   - **Root Directory** : `apps/web`.
   - Railway détecte `Dockerfile` automatiquement.
   - **Healthcheck Path** : `/api/health` (réponse statique immédiate — la
     page `/login` fait un rendu dynamique complet et est trop fragile pour
     ce rôle, elle a provoqué un 502 permanent en pratique).
3. Variables (`apps/web/.env.staging.example`) :
   - `OIDC_ISSUER` = celui de Keycloak (étape 5)
   - `OIDC_CLIENT_ID=paios-api`
   - `API_URL` = l'URL publique du service API (étape 3)
   - `APP_URL` = l'URL publique de ce service (Railway l'affiche après le
     premier déploiement — la reporter ici et redéployer une fois connue)
4. Déployer. C'est ton **URL WEB**.

## Étape 5 — Keycloak

Keycloak se déploie comme une image Docker publique, sans build depuis le
dépôt :

1. "New" → "Empty Service", puis dans ses réglages, "Source" → **"Connect
   Image"** (pas "Root Directory", qui sert au dépôt Git et n'a rien à voir
   avec l'image Docker — piège rencontré en pratique) → renseigner
   `quay.io/keycloak/keycloak:latest`.
2. **Base de données — non optionnel, à faire avant tout le reste.** Sans
   base externe, Keycloak stocke tout (royaume, comptes, mots de passe) dans
   une base intégrée qui vit uniquement dans le système de fichiers du
   conteneur : **le moindre redéploiement ou redémarrage efface tout**, y
   compris le royaume importé à l'étape 5 et le compte administrateur
   (retour à l'écran "Local access required"). Ça s'est produit en pratique
   sur ce staging — à ne plus refaire :
   - Dans l'environnement `staging` : "New" → "Database" → "PostgreSQL",
     puis renommer ce service (par exemple `Postgres-Keycloak`) pour ne pas
     le confondre avec celui de l'API — **jamais la même base que l'API**,
     l'isolation entre services fait partie des règles non négociables du
     projet.
   - Variables du service Keycloak (références à ce nouveau service, jamais
     de valeur recopiée à la main) :
     ```
     KC_DB=postgres
     KC_DB_URL=jdbc:postgresql://${{Postgres-Keycloak.PGHOST}}:${{Postgres-Keycloak.PGPORT}}/${{Postgres-Keycloak.PGDATABASE}}
     KC_DB_USERNAME=${{Postgres-Keycloak.PGUSER}}
     KC_DB_PASSWORD=${{Postgres-Keycloak.PGPASSWORD}}
     ```
     (remplacer `Postgres-Keycloak` par le nom réel donné au service si
     différent).
3. Variables restantes :
   - `KC_BOOTSTRAP_ADMIN_USERNAME` et `KC_BOOTSTRAP_ADMIN_PASSWORD` (noms
     à jour pour Keycloak 26+ ; les anciens noms `KEYCLOAK_ADMIN` /
     `KC_ADMIN` ne sont plus reconnus par cette version et laissent
     Keycloak démarrer sans compte admin, avec un écran "Local access
     required" au lieu du formulaire de connexion). Choisir un mot de passe
     fort, propre à cet environnement (jamais celui du docker-compose
     local).
   - `KC_PROXY_HEADERS=xforwarded` (indispensable derrière le proxy TLS de
     Railway, sinon Keycloak génère des adresses `http://` au lieu de
     `https://` et les redirections échouent).
4. **Start Command** : `/opt/keycloak/bin/kc.sh start --http-enabled=true --hostname-strict=false`
   — chemin complet obligatoire (Railway remplace toute la commande du
   conteneur, `start` seul n'est pas un exécutable), et **sans**
   `--optimized` : ce drapeau suppose une image reconstruite au préalable
   avec `kc.sh build` (via un Dockerfile personnalisé), ce qu'on ne fait
   pas ici — avec l'image stock, il bloque le démarrage en boucle avec un
   avertissement répété. Avec cette commande, `KC_HOSTNAME` n'est pas
   nécessaire : Keycloak déduit l'adresse depuis la requête.
5. **Networking → Generate Domain**, port **8080** (port HTTP par défaut de
   Keycloak). Déployer. C'est ton domaine Keycloak (`OIDC_ISSUER` =
   `https://<ce domaine>/realms/paios` pour l'API et le web).
6. Importer le realm : ouvrir `infra/keycloak/realm-staging.json`, remplacer
   les deux `__WEB_STAGING_DOMAIN__` par le vrai domaine du service web
   (étape 4), puis dans la console d'administration Keycloak
   (`https://<domaine keycloak>/admin`) : "Manage realms" → "Create realm" →
   "Browse" → sélectionner le fichier modifié → "Create". **Cet import ne
   tient que si l'étape 2 (base de données) a été faite d'abord.**
7. Sécurité : la bannière orange "temporary admin user" invite à créer un
   compte admin permanent puis à supprimer le compte temporaire — à faire
   avant d'inviter qui que ce soit d'autre à administrer ce Keycloak (pas
   bloquant pour valider le reste du staging).

Le mot de passe `demo-dev-only` des deux comptes de démonstration
(`demo.technicien`, `demo.admin`) vient du realm tel quel : à changer avant
d'inviter qui que ce soit d'autre à tester, et ce realm n'est jamais réutilisé
pour un client réel.

## Étape 6 — Stockage des photos

**Décidé (Mohamed, 25/09/2026) : Cloudflare R2** — voir `docs/adr/006-stockage-des-photos.md`
pour la justification complète et la condition qui garde ce choix réversible (n'utiliser
que l'API S3 générique, jamais une fonctionnalité propre à Cloudflare).

1. Créer un compte Cloudflare (gratuit) si besoin, puis un panier R2
   (`paios-staging-photos`).
2. Générer un jeton d'accès R2 avec droits lecture/écriture sur ce panier
   uniquement (jamais un jeton "compte entier").
3. `STORAGE_ENDPOINT_URL` = l'URL S3 du compte R2 (affichée dans le tableau
   de bord Cloudflare, sous la forme
   `https://<identifiant compte>.r2.cloudflarestorage.com`).

Les variables à définir sur le service API sont toujours les quatre mêmes
(`app/storage.py` ne change jamais) : `STORAGE_ENDPOINT_URL`,
`STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET`. Ce panier de
staging ne sera jamais partagé avec un futur panier de production.

## Étape 7 — Boucler les adresses

Une fois les trois domaines connus (API, web, Keycloak), reporter :

- Realm Keycloak : redirections avec le domaine web (étape 5, si pas déjà
  fait avant l'import).
- Service API : `OIDC_ISSUER` avec le domaine Keycloak.
- Service Web : `OIDC_ISSUER`, `API_URL`, `APP_URL` — ces adresses doivent
  inclure `https://` ; une adresse sans schéma casse silencieusement
  l'échange OIDC (Keycloak reçoit un `redirect_uri` invalide et affiche une
  page "introuvable" sans message clair). Le code du web s'en protège
  maintenant tout seul (`apps/web/src/lib/config.ts` complète `https://` si
  absent), mais autant les saisir correctement dès le départ.
- Mobile (poste de test, jamais commité) : copier
  `apps/mobile/.env.staging.example` vers `apps/mobile/.env`, avec les
  vraies adresses API et Keycloak, puis `expo start`.

## Étape 8 — Vérifications techniques

- Logs du service API au démarrage : la ligne `alembic upgrade head` doit
  s'exécuter sans erreur, et le service ne doit **jamais** afficher
  "Catalogue i18n introuvable" (sinon `shared/i18n` n'est pas arrivé dans
  l'image — revoir le Root Directory de l'étape 3).
- `GET https://<domaine API>/health` → `200`.
- `GET https://<domaine API>/health/db` → `200`.
- Ouvrir `https://<domaine web>/login` : redirection vers Keycloak.

## Smoke test manuel (obligatoire avant de considérer le staging validé)

Parcours exact demandé, dans l'ordre :

1. Connexion (web, avec `demo.admin` ou `demo.technicien`).
2. Créer un site.
3. Créer un équipement (registre).
4. Ouvrir sa fiche équipement.
5. Générer son QR code.
6. Scanner ce QR avec l'application mobile (pointée sur le staging).
7. Créer une nouvelle intervention sur cet équipement.
8. Remplir la checklist, prendre une photo (obligatoire).
9. Couper le réseau du téléphone **avant** d'envoyer.
10. Faire une clôture (ou une modification) pendant que le téléphone est hors
    connexion — l'intervention doit rester visible localement, marquée en
    attente.
11. Rétablir le réseau : la synchronisation doit partir automatiquement.
12. Vérifier dans l'historique (mobile) que l'intervention apparaît **une
    seule fois** (pas de doublon créé par une éventuelle nouvelle tentative).
13. Vérifier les permissions : se reconnecter avec `demo.technicien` et
    confirmer qu'une action réservée à `admin_tenant`/`responsable_exploitation`
    est bien refusée (403).
14. Vérifier la traçabilité : consulter `audit_log` en base (ou via un accès
    direct psql sur le Postgres de staging) et confirmer qu'une entrée existe
    pour les actions sensibles de ce parcours.
15. **Redémarrer le service API** (redeploy manuel depuis Railway), puis
    rouvrir la fiche de l'intervention créée à l'étape 7 et confirmer que la
    photo s'affiche toujours (le lien de téléchargement est régénéré à la
    demande — voir `app/storage.py` — donc ça doit fonctionner même après un
    redémarrage ou un redéploiement).
16. Changer la langue du navigateur en anglais et vérifier qu'aucun texte
    n'apparaît sous forme de code brut (ex. `ENERGY_BASELINE_NOT_FOUND` au
    lieu d'une phrase) : signe que `shared/i18n` est bien arrivé côté web
    aussi.

Les tests E2E automatisés restent au backlog ; ce parcours manuel est la
condition pour déclarer le staging validé.

## Sauvegardes

Non requis pour valider le staging. Devient obligatoire avant tout client
réel : activer les sauvegardes automatiques du plugin PostgreSQL de Railway
(disponible selon le plan) et tester une restauration au moins une fois.

Procédure testée disponible pour cette vérification manuelle (et comme filet
indépendant de Railway, le dépôt restant portable) :
`services/api/scripts/backup_database.sh` /
`services/api/scripts/restore_database.sh`. Un rôle PostgreSQL dédié,
distinct du rôle applicatif, est nécessaire — le rôle applicatif est
bloqué par `FORCE ROW LEVEL SECURITY` sur chaque table métier (voulu, ne
pas contourner autrement que par ce rôle de sauvegarde) :

```sql
CREATE ROLE paios_backup WITH LOGIN PASSWORD '...' BYPASSRLS;
GRANT CONNECT ON DATABASE paios TO paios_backup;
GRANT USAGE ON SCHEMA public TO paios_backup;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO paios_backup;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO paios_backup;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO paios_backup;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO paios_backup;
```

Cycle complet (sauvegarde → base vierge → restauration → données et
politiques RLS intactes) vérifié manuellement le 02/10/2026. Reste à faire
avant le premier client réel : brancher ce script sur une tâche planifiée
(Railway Cron Jobs, même mécanisme que `scripts/supervision_sweep.py`) et
sur un stockage de sauvegarde durable hors de la base elle-même.

## Rapport à produire à la fin

```
STAGING : ACCESSIBLE / NON ACCESSIBLE

URL WEB :
URL API :

AUTHENTIFICATION : OK / KO
POSTGRES : OK / KO
PHOTOS : OK / KO
WEB : OK / KO
MOBILE → API DISTANTE : OK / KO
I18N : OK / KO
MIGRATIONS : OK / KO
SMOKE TEST : OK / KO
```

## État actuel de ce staging (25/09/2026)

- API et web déployés, actifs et accessibles sur Railway (environnement
  `staging`, projet `virtuous-rebirth`).
- Domaines : API `l-univers-connect-staging.up.railway.app`, web
  `discerning-delight-staging.up.railway.app`, Keycloak
  `virtuous-communication-staging.up.railway.app`.
- Stockage des photos (Cloudflare R2) : configuré (panier
  `paios-staging-photos`, jeton scopé à ce panier, variables `STORAGE_*`
  sur l'API).
- **Keycloak : à refaire.** Le royaume `paios` importé une première fois a
  été perdu (pas de base de données externe — voir étape 5.2, corrigée dans
  ce guide). Reprendre à l'étape 5.2 (créer `Postgres-Keycloak`, ajouter les
  variables `KC_DB*`) avant de réimporter le royaume — une fois cette base
  branchée, l'import ne se perdra plus.
- Reste à faire ensuite : smoke test manuel complet, durcissement du compte
  admin temporaire Keycloak.

## Incident de sécurité Railway du 21/10/2026

Sources : `status.railway.com` et le billet « Security Disclosure: Wednesday October 21st »
(`blog.railway.com`), lus le 21/10/2026.

**Faits annoncés par Railway.** Une activité anormale a été détectée sur les systèmes qui
stockent les variables d'environnement des clients. Un tiers non autorisé a pu accéder à des
variables chiffrées et, pour certaines, en obtenir le contenu en clair. Railway recommande à
tous ses clients, par précaution, de renouveler toutes les variables stockées chez lui (clés
d'API, identifiants de bases de données et de registre) et de relire les journaux de leurs
services. Les déploiements ont été suspendus le 21/10 : constructions rétablies pour
Enterprise le 21/10 au soir, pour Pro le 22/10 à 06:29 UTC, puis pour Hobby ; Free et Trial
n'étaient pas encore rouverts le 22/10 à 21:59 UTC. La suspension des déploiements du staging
(dernier déploiement `301451f`, le 21/10 à 05:57 UTC) venait de cet incident.

**Ce que Railway stocke pour ce staging** (d'après ce guide ; les valeurs ne sont pas
lisibles par l'assistant) : l'adresse de connexion à la base de l'API (`DATABASE_URL`),
`DEVICE_TOKEN_SECRET`, les identifiants administrateur de Keycloak et de sa base, les clés
Cloudflare R2 du stockage des photos (`STORAGE_*`). Aucun secret n'est dans le dépôt
(règle non négociable 5), vérifié par recherche le 21/10/2026.

**Reprise : à confirmer par le propriétaire du compte** (état non connu de l'assistant au
22/10/2026).

| Action | Où | État |
| --- | --- | --- |
| Changer le mot de passe administrateur de Keycloak | Console Keycloak | à confirmer |
| Désactiver `demo.technicien` et `demo.admin` (mot de passe public dans `infra/README.md`) | Console Keycloak, ou `scripts/staging_account.py disable-demo-users --yes` | **fait le 24/10/2026** par le propriétaire dans la console Keycloak, vérifié (jeton refusé, « Account disabled »). Réversible : `enabled` repasse à vrai, aucune donnée supprimée. Voir la conséquence dans le bilan ci-dessous |
| Activer la détection de force brute du royaume (Realm settings → Security defenses → Brute force detection : 5 échecs, attente croissante jusqu'à 15 minutes) | Console Keycloak. `realm-staging.json` contient maintenant ce réglage, mais un fichier d'import ne s'applique qu'à un royaume neuf : le royaume en place doit être réglé à la main | à faire (23/10/2026 : absente du royaume importé, donc aucune limite aux essais de mot de passe) |
| Révoquer le jeton R2 `paios-staging-photos` et en créer un nouveau | Cloudflare, puis variables `STORAGE_*` | à confirmer |
| Renouveler `DEVICE_TOKEN_SECRET` (`openssl rand -hex 32`, 64 caractères) | Variable Railway, puis redéploiement ; les appareils redemandent un jeton | à confirmer |
| Renouveler les mots de passe des bases (API et Keycloak) | Railway, puis redéploiement des deux services | à confirmer |
| Vérifier qu'aucune base n'est exposée par un accès TCP public | Railway | à confirmer |
| Relire les journaux de l'API et les événements d'administration de Keycloak | Railway, console Keycloak | à confirmer |

Tant que le mot de passe administrateur de Keycloak n'est pas changé, ne pas créer le compte
de test (`scripts/staging_account.py`) : il demande ce mot de passe.

## Bilan du 24/10/2026

Établi après la fusion et la validation sur le staging. Ce qui est vérifié sur le staging réel
est séparé de ce qui ne l'est qu'en local.

### Fait

| Sujet | État |
| --- | --- |
| Fusion de la demande n° 1 dans `main` | **Faite** (commit de fusion `96b277d`, 291 commits conservés un par un ; CI de `main` **verte**, exécution n° 534 terminée avec succès à 09:06 UTC). Au moment de la fusion, `main` avait exactement le contenu de la branche. Le projet Railway a bien un environnement `production`, mais il ne contient qu'une base Postgres vide créée le 25/09/2026 : aucun déploiement n'y a suivi la fusion (vérifié le 24/10/2026). Depuis, la branche de travail porte deux commits de plus (origine d'une valeur sur Télémétrie, script de démonstration), à fusionner par une nouvelle demande ; elle est conservée car Railway la déploie. Leur CI est verte (exécutions n° 535 et n° 536). Reconstruire la branche sur `main` par une poussée forcée a été refusé par le contrôle de sécurité de la session : la branche reste donc telle quelle, et la prochaine demande de fusion vers `main` n'embarquera que ces commits (`991b5d2` est déjà un ancêtre de `main`) |
| Archivage d'un site, cascade sur ses équipements | Migrations passées sur le staging (23/10/2026) ; vérifié de bout en bout avec le jeu de démonstration (voir ci-dessous) |
| Origine d'une valeur sur Télémétrie | Déployée sur le staging (API et web) |

### Comptes de démonstration : **désactivés le 24/10/2026**

`demo.admin` (rôle `admin_tenant`) et `demo.technicien` ont été désactivés par le propriétaire du
compte, dans la console Keycloak (royaume `paios`, Utilisateurs, interrupteur « Activé »). La
console française affiche « Handicapé » pour « Disabled » (mauvaise traduction automatique) : les
deux comptes y portent cette mention. Aucune donnée n'a été supprimée ; la désactivation est
réversible (réactiver l'interrupteur).

**Vérifié depuis l'extérieur** : une demande de jeton avec le mot de passe public du dépôt est
refusée pour les deux comptes (HTTP 400, « Account disabled »), aucun jeton délivré.

**Conséquence à connaître** : le royaume `paios` ne contient que ces deux comptes. Plus personne
ne peut donc se connecter à la console web du staging tant qu'un compte personnel n'existe pas.
Étape suivante, par ordre de simplicité :

1. Créer le compte personnel du propriétaire avec l'outil dédié (procédure détaillée juste
   après).
2. Créer le compte de test dédié (`scripts/staging_account.py create`, rôle `technicien`) :
   demande `KEYCLOAK_ADMIN_PASSWORD` dans une nouvelle session.
3. Renouveler les secrets de la liste ci-dessus et vérifier la détection de force brute du royaume
   en place (Realm settings, Security defenses).

Pour mémoire, le blocage de la session précédente : ni le connecteur Railway ni
`KEYCLOAK_ADMIN_PASSWORD` n'étaient disponibles (vérifié le 24/10/2026) ; un connecteur n'est lu
qu'au démarrage d'une session, d'où la nécessité d'ouvrir une nouvelle session après sa
reconnexion.

### Constats Railway du 24/10/2026 (lecture seule, connecteur reconnecté)

Lus avec le connecteur Railway, dans le seul projet `virtuous-rebirth` (le compte Railway compte
onze projets : les dix autres n'ont pas été touchés). Aucune valeur de variable n'a été lue : seuls les noms.

| Sujet | Constat |
| --- | --- |
| Échec de construction de 09:27 UTC | **Panne de l'infrastructure de construction de Railway, pas de notre code.** Journal : « Build Failed: build daemon returned an error < listing workers for Build: failed to list workers: Unavailable: connection error … buildkitd.sock: use of closed network connection > » : le démon de construction est devenu indisponible avant d'exécuter notre Dockerfile. La construction suivante (09:33), avec les mêmes entrées, a réussi |
| Chemins surveillés (`watchPatterns`) | **Validés par l'historique** : le commit de documentation seule de 09:47 donne un déploiement « SKIPPED » ; le commit suivant, qui modifie `services/api`, est déployé avec succès (09:58) |
| Constructeur | Le tableau de bord indique « RAILPACK » pour les trois services ; `railway.json` (DOCKERFILE) l'emporte : les journaux du déploiement réussi montrent les étapes `COPY services/api/…` du Dockerfile |
| Branche suivie | L'API (racine du dépôt) et le web (`/apps/web`) suivent `claude/asset-intelligence-os-setup-h234af`. Keycloak utilise l'image `quay.io/keycloak/keycloak:latest` |
| Environnement `production` | Une base Postgres vide du 25/09/2026, rien d'autre |

**À décider par Mohamed** (rien n'a été modifié) :

1. **Épingler l'image de Keycloak.** `latest` signifie qu'un redémarrage ou un redéploiement peut tirer
   une version plus récente, voire une version majeure, sans que personne l'ait choisi : risque de
   panne du royaume. Lire la version en cours (console Keycloak, informations du serveur), puis
   épingler cette version.
2. **Faire suivre `main` à l'API et au web**, une fois les commits de suivi de la branche de travail
   fusionnés dans `main` par une nouvelle demande de fusion : la branche de travail redeviendrait
   libre, et `main` serait enfin la référence déployée.
3. **Keycloak porte encore `KC_BOOTSTRAP_ADMIN_*`** (compte administrateur temporaire, que la console
   signale elle-même par un bandeau jaune) : créer un administrateur permanent puis supprimer le
   compte temporaire, plus tard.

**`KEYCLOAK_ADMIN_PASSWORD` absente de la session (24/10/2026, 10:13 UTC).** Une session lancée
après l'ajout de la variable ne la voyait pas, et deux sessions-sondes (`Soft` et `Default`,
« réseau de confiance ») non plus : la variable n'existe dans aucun des trois environnements du
compte (dont deux s'appellent « Default »), et aucune variable Keycloak n'y figure. Elle n'a donc pas été
enregistrée comme **variable d'environnement** : la zone « Secrets réseau » (« identifiants API »)
n'en est pas une. Seule une variable d'environnement est lisible par l'outil.

### Compte personnel du propriétaire (outil `staging_owner_account.py`)

**Outil prêt et testé, compte pas encore créé** (état au 24/10/2026). Il n'a pas pu être exécuté
dans la session qui l'a écrit : `KEYCLOAK_ADMIN_PASSWORD` n'y était pas défini et le connecteur
Railway n'y était pas visible (un connecteur et une variable d'environnement ne sont lus qu'au
démarrage d'une session).

**Ce que fait l'outil** (`services/api/scripts/staging_owner_account.py`, 17 tests, 4 régressions
volontaires détectées) :

- refuse `demo.admin`, `demo.technicien` et `loadtest.staging` : un compte personnel est distinct ;
- crée l'utilisateur dans le royaume `paios` avec **le seul rôle `admin_tenant`** (toutes les routes
  de l'API l'acceptent, aucune n'est réservée à un autre rôle : moindre privilège) et le client
  `11111111-1111-1111-1111-111111111111` ;
- lui donne un mot de passe aléatoire de 32 octets, **jamais affiché ni écrit**, pour prouver que
  la connexion marche : un jeton est délivré par Keycloak ; l'API (`GET /me`) voit le rôle, l'identifiant
  et le client ; en option, une commande de contrôle reçoit l'identifiant et le mot de passe par
  l'environnement de son processus seulement (sans le mot de passe administrateur), sa sortie étant
  filtrée ;
- retire ensuite ce mot de passe et impose son changement (`UPDATE_PASSWORD`), **même si une
  vérification a échoué** ;
- si le compte existe déjà, ne touche ni à son mot de passe ni à son état.

**Pourquoi le mot de passe n'est pas donné à la personne** : un mot de passe généré par un
programme et remis par un message ou un fichier passerait par un endroit que la règle du projet
interdit. La personne choisit le sien, dans Keycloak, et Keycloak lui impose de le changer à la
première connexion.

**Procédure :**

1. Avoir changé le mot de passe administrateur de Keycloak depuis l'incident du 21/10 (voir la liste
   de reprise plus haut), puis le placer comme **variable d'environnement** nommée
   `KEYCLOAK_ADMIN_PASSWORD` dans les réglages de l'environnement cloud, **avant** de démarrer la
   session : jamais dans une conversation. Le mot de passe saisi pour ouvrir la console Keycloak
   avec le compte `admin` prouve déjà que ce mot de passe existe et fonctionne côté Railway ; la
   variable de l'environnement cloud en est une copie pour l'outil.
2. Dans une nouvelle session (le connecteur Railway n'y est lu qu'au démarrage) :
   `PYTHONPATH=. python scripts/staging_owner_account.py create --keycloak-url
   https://KEYCLOAK_STAGING --api-url https://API_STAGING --username IDENTIFIANT -- node
   infra/staging-web-login-check.mjs https://CONSOLE_WEB_STAGING` (Playwright :
   `PLAYWRIGHT_NODE_PATH`, éventuellement `PLAYWRIGHT_CHROMIUM_PATH`).
3. Dans la console Keycloak (royaume `paios`, Utilisateurs, le compte, onglet des identifiants) :
   définir son mot de passe en laissant « temporaire » activé, puis se connecter à la console web :
   Keycloak impose d'en choisir un nouveau.
4. Vérifier que `demo.admin` et `demo.technicien` restent refusés (demande de jeton : HTTP 400,
   « Account disabled »), et relire les journaux de Keycloak et de l'API pour s'assurer qu'aucun
   secret n'y figure (recherche du mot de passe administrateur et des mots clés `password`,
   `secret`, `token`).

**Vérifié sans compte réel** : la commande de contrôle `infra/staging-web-login-check.mjs` échoue
proprement (code 1) face à un compte inexistant sur le vrai staging et n'affiche pas le mot de
passe ; elle refuse de tourner sans identifiants (code 2). Son chemin de réussite ne peut être
testé qu'avec le vrai compte.

**Résultat de l'exécution : à compléter** (compte créé, jeton délivré, accès à la console web,
comptes de démonstration toujours désactivés, journaux sans secret).

### Jeu de données de démonstration (staging)

Créé le 24/10/2026 avec `scripts/seed_staging_demo.py`, en tant que `demo.admin` (le seul compte
du royaume en place qui gère le registre ; désactivé depuis, voir plus haut) : 15
éléments créés, 1 archivage, rien de supprimé. Résumé sans secret : sites, équipements, points,
relevés et alarmes tous préfixés « DÉMO — ». Pour relancer (structure idempotente, un relevé
simulé de plus par passage) : `PYTHONPATH=. python scripts/seed_staging_demo.py --api-url ...
--credentials-file ... --yes`. Pour retirer la démonstration des listes : archiver les deux
sites dans la console.

**Vérifié à l'écran sur le staging réel** (comptes `demo.technicien` et `demo.admin`) :

- Alarmes et constats : bande de tuiles (2 alarmes ouvertes, 0 constat, 2 à acquitter, 0 en cours
  de traitement) ; l'alarme de l'équipement archivé est listée, nommée « archivé ».
- Accueil : le total des alarmes ouvertes compte l'alarme de l'équipement archivé (1 majeure,
  1 avertissement), qu'aucune ligne de site ne porte ; la phrase d'explication s'affiche.
- Télémétrie : « 41,2 °C », « 1 284,6 kWh » et « 38,4 °C », chacun suivi de « Valeur simulée » ;
  l'équipement archivé est nommé et marqué « archivé ».
- Registre : phrase de règle de l'archivage ; « Site archivé : désarchivez-le d'abord. » à la place
  du bouton « Désarchiver » ; l'équipement de démonstration a bien été archivé par la cascade
  (jamais archivé directement).

**Non validé sur le staging** : la page Énergie et le bloc Énergie de l'accueil (aucune
consommation journalière dans les données de démonstration), les actions d'acquittement, et
l'application mobile (aucun appareil). Ces points ne sont vérifiés qu'en local ou par les tests.

### Branches du dépôt (vérifié le 24/10/2026, rien supprimé, rien fermé)

| Branche | Contenu par rapport à `main` | Railway | Documentation |
| --- | --- | --- | --- |
| `claude/pyjwt-migration` | **Rien d'unique** : sa tête (`72c74af`, 21/10/2026, « PyJWT remplace python-jose, ADR 019 ») est un ancêtre de `main` ; 24 commits de `main` lui manquent, c'est normal. **La migration vers PyJWT est faite**, pas à faire : `main` porte `PyJWT[crypto]` 2.15.1 et `cryptography` 50.0.1, `app/auth.py` importe `jwt`, plus aucun `python-jose`. CI de la branche verte (exécution n° 499, 1 317 tests). Aucune demande de fusion | Non vérifiable sans le connecteur Railway (aucune demande de fusion, donc aucun statut lisible sur GitHub) | Citée comme origine de la migration dans `docs/adr/019-…` et `docs/security/registre-vulnerabilites.md` : mention historique, aucune dépendance |
| `claude/upbeat-noether-hso8ah` | **Un autre projet** : demande de fusion n° 2 (« Add HyperFrames agent skills »), ouverte contre `main`, 96 commits, 2 711 fichiers, +319 283 lignes, environ 1,3 Go suivis. Dossier `videos/` (1 478 fichiers), vidéos `.mp4` à la racine, outils d'agent (`.agents`, `.claude`) : publicités et vidéos de marque (ENORYX, KOFA, KTF-SHIPPING, SENSEXPRESS, SK-PRINT, Farmasi, Fanta shop). Active : dernier commit le 23/10/2026 à 15:44. Embranchée le 22/09/2026 de l'ancien `main`. Aucun motif de secret détecté | Aucun statut Railway sur sa tête, aucune exécution de CI, et son arbre n'a ni `railway.json`, ni `services/api/Dockerfile`, ni `apps/web` : elle ne peut pas être déployée telle quelle. La configuration des services Railway elle-même n'est pas lisible sans le connecteur | Aucune mention |

**Ne pas fusionner la demande n° 2 dans `main` telle quelle.** Elle est en conflit avec `main`
(`CLAUDE.md` ajouté des deux côtés, et renommé ailleurs puis supprimé de notre côté ;
`.gitignore`) : une fusion forcée remplacerait les instructions de travail de ce projet, et
ajouterait environ 1,3 Go de vidéos à son dépôt. Ce travail gagnerait à vivre dans son propre
dépôt. Décision de Mohamed ; aucune action tant qu'elle n'est pas prise.

**`claude/pyjwt-migration`** pourrait être supprimée sans perte (elle ne contient rien que
`main` n'ait pas), mais elle est conservée, comme demandé. **À vérifier dès que le connecteur
Railway est reconnecté :** quelle branche suit chaque service (staging web, API, Keycloak). Une
fois `main` à jour, la configuration la plus saine est que Railway suive `main`.

## Point qui reste à ta décision

**Exécution** : cette session n'a pas d'accès à ton compte Railway (ni à un
compte Cloudflare). Deux options :

- tu suis ce guide toi-même (chaque étape est un clic ou un copier-coller de
  variable) — c'est l'option suivie jusqu'ici ;
- tu ajoutes un jeton d'accès Railway (et, pour le stockage, un jeton R2)
  aux secrets de cet environnement de développement (jamais collé dans la
  conversation) pour que la session puisse exécuter les étapes elle-même via
  leurs CLI respectives.
