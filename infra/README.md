# Infrastructure locale

Démarrer la base de données PostgreSQL pour le développement local :

```bash
cd infra
docker compose up -d
```

Cela lance un PostgreSQL 16 accessible sur `localhost:5432` avec les identifiants définis
dans `docker-compose.yml` (base `paios`, utilisateur `paios`). Ce sont des identifiants de
développement local uniquement, jamais utilisés en production.

Pour arrêter la base de données : `docker compose down` (les données restent dans le
volume Docker). Pour tout effacer et repartir de zéro : `docker compose down -v`.
