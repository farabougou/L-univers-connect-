# Infrastructure locale

Démarrer la base de données PostgreSQL pour le développement local :

```bash
cd infra
docker compose up -d
```

Cela lance un PostgreSQL 16 accessible sur `localhost:5432`, avec deux comptes :

- `postgres` : compte d'administration, utilisé uniquement à l'initialisation (voir
  `init-db/01-create-app-role.sql`). L'API ne s'en sert jamais.
- `paios` : rôle applicatif utilisé par l'API, sans privilège superutilisateur, propriétaire
  de la base `paios`. C'est important : PostgreSQL n'applique jamais la sécurité RLS
  (isolation entre clients) à un superutilisateur, donc l'API doit toujours se connecter
  avec ce rôle applicatif, jamais avec le compte d'administration.

Ce sont des identifiants de développement local uniquement, jamais utilisés en production.

Pour arrêter la base de données : `docker compose down` (les données restent dans le
volume Docker). Pour tout effacer et repartir de zéro : `docker compose down -v`.
