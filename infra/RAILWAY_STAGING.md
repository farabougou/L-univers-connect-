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

**À relever dans le tableau de bord Railway** (service API) : le nombre de réplicas, la présence
de `CLIENT_IP_HEADER` et de `RATE_LIMIT_STORAGE_URI`, et la ligne `capacity.checked` du journal
de démarrage (elle indique le nombre de réplicas attendu et l'en-tête configuré). Conséquence
pratique : **la protection contre l'essai de secrets sur `POST /devices/auth` n'est pas
effective sur le staging aujourd'hui.** Les secrets d'appareil sont aléatoires et comparés en
temps constant, et le mode par clé publique n'a pas de secret à deviner, mais la défense en
profondeur annoncée manque. `CLIENT_IP_HEADER` reste vide : l'activer ne règle pas ce point et
l'essai ne pourrait pas conclure.

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
| Désactiver `demo.technicien` et `demo.admin` (mot de passe public dans `infra/README.md`) | Console Keycloak, ou `scripts/staging_account.py disable-demo-users --yes` | à confirmer |
| Révoquer le jeton R2 `paios-staging-photos` et en créer un nouveau | Cloudflare, puis variables `STORAGE_*` | à confirmer |
| Renouveler `DEVICE_TOKEN_SECRET` (`openssl rand -hex 32`, 64 caractères) | Variable Railway, puis redéploiement ; les appareils redemandent un jeton | à confirmer |
| Renouveler les mots de passe des bases (API et Keycloak) | Railway, puis redéploiement des deux services | à confirmer |
| Vérifier qu'aucune base n'est exposée par un accès TCP public | Railway | à confirmer |
| Relire les journaux de l'API et les événements d'administration de Keycloak | Railway, console Keycloak | à confirmer |

Tant que le mot de passe administrateur de Keycloak n'est pas changé, ne pas créer le compte
de test (`scripts/staging_account.py`) : il demande ce mot de passe.

## Point qui reste à ta décision

**Exécution** : cette session n'a pas d'accès à ton compte Railway (ni à un
compte Cloudflare). Deux options :

- tu suis ce guide toi-même (chaque étape est un clic ou un copier-coller de
  variable) — c'est l'option suivie jusqu'ici ;
- tu ajoutes un jeton d'accès Railway (et, pour le stockage, un jeton R2)
  aux secrets de cet environnement de développement (jamais collé dans la
  conversation) pour que la session puisse exécuter les étapes elle-même via
  leurs CLI respectives.
