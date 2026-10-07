# Infrastructure locale

Pour le passage en staging privé sur Railway, voir `RAILWAY_STAGING.md`.

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

## Courtier MQTT (quatrième protocole de terrain)

Accessible sur `localhost:1883`, sans authentification (développement local
uniquement, voir `mosquitto/mosquitto.conf`). Utilisé par
`scripts/mqtt_daemon.py` et par les tests du connecteur
(`services/api/app/connectors/mqtt.py`), qui démarrent eux-mêmes leur propre
courtier de test — ce service sert pour un essai manuel ou un équipement
simulé qui publie sur ce courtier.

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

## Balayage périodique des commandes planifiées (V2)

Une commande planifiée (`POST /scheduled-commands`, priorité « planification » de la
feuille de route V2) ne s'exécute jamais toute seule à l'heure dite : un balayage
périodique, même principe que la supervision ci-dessus, la trouve et la déclenche.
En local :

```bash
cd services/api
python scripts/scheduled_commands_sweep.py --interval 30
```

En production (Railway), ce même script s'exécute avec `--once` sur un service Cron Jobs
(toutes les minutes suffit) : voir `app/scheduled_commands_sweep.py` pour le détail du
mécanisme. La commandabilité du point et sa policy active (`app/command_policies.py`)
sont revérifiées à chaque déclenchement, jamais seulement à la planification.

## Balayage périodique du moteur d'automatisation (V2)

Une règle d'automatisation (`config_type = automation_rule`, dernière priorité de la
feuille de route V2 : règle → commande) ne s'évalue jamais sur l'arrivée d'une mesure,
contrairement aux règles FDD/alarme — un balayage périodique, même principe que les deux
balayages ci-dessus, l'évalue. En local :

```bash
cd services/api
python scripts/automation_rules_sweep.py --interval 30
```

En production (Railway), ce même script s'exécute avec `--once` sur un service Cron Jobs
(toutes les minutes suffit) : voir `app/automation_rules_sweep.py` et
`app/automation_rules.py` pour le détail du mécanisme et des garde-fous (mode du point,
commandabilité, policy active, anti-emballement, tous revérifiés à chaque tour).

**État réel (07/10/2026, audit de fermeture V2)** : les trois balayages ci-dessus
(supervision, commandes planifiées, automatisation) sont codés, testés et documentés,
mais **aucun service Cron Jobs n'est aujourd'hui configuré sur le projet Railway** (ni en
staging ni en production) — vérifié directement via l'API Railway, qui ne liste que les
services Postgres, Keycloak, l'API et le web. Une commande planifiée ou une règle
d'automatisation activée sur ce staging reste donc `pending`/jamais évaluée tant
qu'aucune tâche planifiée externe ne tourne. Ce n'est pas un défaut du logiciel — le
mécanisme fonctionne (vérifié par la suite de tests et en local) — mais une tâche
d'infrastructure restant à faire avant un usage réel : créer un service Cron Jobs par
balayage sur Railway, pointant chacun vers le script `--once` correspondant. Signalé
explicitement plutôt que supposé fait.

## Ancrage externe du journal d'audit

Le journal d'audit (`app/audit.py`) est chaîné par hachage à l'intérieur de la base :
modifier une entrée déjà écrite casse la chaîne. Ce balayage ajoute un témoin extérieur
à Postgres, pour qu'un accès direct et complet à la base (pas le fonctionnement normal
de l'application) ne permette pas de réécrire toute la chaîne sans que cela se voie.
Même principe d'exécution que le balayage de supervision ci-dessus :

```bash
cd services/api
python scripts/anchor_audit_log.py --interval 3600
```

En production (Railway), ce même script s'exécute avec `--once` sur un service Cron Jobs
(une fois par heure suffit) : voir `app/audit_anchor.py` pour le détail du mécanisme.
