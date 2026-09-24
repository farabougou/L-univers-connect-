# Infrastructure locale

Démarrer la base de données PostgreSQL et le serveur d'authentification pour le
développement local :

```bash
cd infra
docker compose up -d
```

## Base de données (PostgreSQL)

Accessible sur `localhost:5432`, avec deux comptes :

- `postgres` : compte d'administration, utilisé uniquement à l'initialisation (voir
  `init-db/01-create-app-role.sql`). L'API ne s'en sert jamais.
- `paios` : rôle applicatif utilisé par l'API, sans privilège superutilisateur, propriétaire
  de la base `paios`. C'est important : PostgreSQL n'applique jamais la sécurité RLS
  (isolation entre clients) à un superutilisateur, donc l'API doit toujours se connecter
  avec ce rôle applicatif, jamais avec le compte d'administration.

## Authentification (Keycloak)

Accessible sur `localhost:8080`. Au premier démarrage, Keycloak importe automatiquement
le realm `paios` défini dans `keycloak/realm-export.json` : les rôles de base
(`technicien`, `responsable_exploitation`, `admin_tenant`) et deux utilisateurs de
démonstration (`demo.technicien` / `demo.admin`, mot de passe `demo-dev-only`).

- Console d'administration : http://localhost:8080/admin (identifiants `admin` /
  `admin_dev_password`, définis dans `docker-compose.yml`).
- Pour obtenir un vrai jeton et tester l'API à la main :

  ```bash
  curl -s -X POST http://localhost:8080/realms/paios/protocol/openid-connect/token \
    -d "client_id=paios-api" \
    -d "grant_type=password" \
    -d "username=demo.technicien" \
    -d "password=demo-dev-only" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
  ```

  Puis, avec l'API démarrée (`uvicorn app.main:app --reload --no-access-log`) :

  ```bash
  curl -s http://localhost:8000/me -H "Authorization: Bearer <le jeton copié ci-dessus>"
  ```

  Avec `demo.technicien`, `/me` doit répondre et `/admin/ping` doit renvoyer une erreur
  403 (rôle insuffisant). Avec `demo.admin`, les deux routes doivent répondre.

Ce mode de connexion par mot de passe (`grant_type=password`) est pratique pour tester en
local, mais ne doit jamais être utilisé par la future application web ou mobile : elles
utiliseront le flux standard "Authorization Code + PKCE", plus sûr (voir docs/adr/002).

Ce sont des identifiants de développement local uniquement, jamais utilisés en production.

## Stockage des photos (MinIO)

Accessible sur `localhost:9000` (API compatible S3) et `localhost:9001` (console web).
Au démarrage, un panier `paios-photos` est créé automatiquement.

- Console d'administration : http://localhost:9001 (identifiants `paios-storage` /
  `storage_dev_password`, définis dans `docker-compose.yml`).
- Si le panier `paios-photos` n'apparaît pas automatiquement (selon la version de
  MinIO), crée-le à la main depuis la console : bouton "Create Bucket", nom
  `paios-photos`.

Voir `docs/adr/006-stockage-des-photos.md` pour le choix de MinIO en local et la
portabilité vers un vrai fournisseur compatible S3 en production.

Pour arrêter les services : `docker compose down` (les données restent dans le volume
Docker). Pour tout effacer et repartir de zéro : `docker compose down -v`.

## Balayage périodique de supervision

La supervision (équipement hors ligne, donnée périmée) doit fonctionner même si personne ne
consulte l'application. En local, lancer le balayage en boucle à côté de l'API :

```bash
cd services/api
python scripts/supervision_sweep.py --interval 60
```

En production (Railway), ce même script s'exécute avec `--once` sur un service Cron Jobs
plutôt qu'en boucle : voir `app/supervision_sweep.py` pour le détail du mécanisme.
