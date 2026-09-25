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
4. Déployer. Railway assigne un domaine public (`*.up.railway.app`) — c'est
   ton **URL API**.

CORS : rien à configurer. Le web (`apps/web`) n'appelle jamais l'API depuis le
navigateur — uniquement depuis son propre serveur Next.js (vérifié dans le
code : un seul composant client existe, `LoginError.tsx`, et il n'appelle pas
l'API). Le mobile appelle l'API directement depuis l'appareil, hors du cadre
CORS (qui ne concerne que les navigateurs). Si un jour un composant du
navigateur appelle l'API directement, ajouter `CORSMiddleware` dans
`app/main.py` à ce moment-là seulement.

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

## Point qui reste à ta décision

**Exécution** : cette session n'a pas d'accès à ton compte Railway (ni à un
compte Cloudflare). Deux options :

- tu suis ce guide toi-même (chaque étape est un clic ou un copier-coller de
  variable) — c'est l'option suivie jusqu'ici ;
- tu ajoutes un jeton d'accès Railway (et, pour le stockage, un jeton R2)
  aux secrets de cet environnement de développement (jamais collé dans la
  conversation) pour que la session puisse exécuter les étapes elle-même via
  leurs CLI respectives.
