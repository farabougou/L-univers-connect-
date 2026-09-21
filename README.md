# Physical Asset Intelligence OS

Plateforme de gestion et d'intelligence des actifs physiques (multi-clients, edge-first).

Premier produit (wedge) : maintenance et suivi des installations CVC, froid et chaud du
tertiaire. Le cahier des charges complet est dans `docs/spec/`.

## Structure du dépôt

```
/docs/spec/       cahier des charges et notes de conception
/docs/adr/        décisions d'architecture (une par fichier)
/services/api/    backend FastAPI (monolithe modulaire)
/apps/web/        application web (à partir de M1)
/apps/mobile/     application technicien (à partir de M1)
/infra/           docker compose, scripts, configuration
```

## Démarrer en local

1. Démarrer la base de données PostgreSQL et le serveur d'authentification (Keycloak) :

   ```bash
   cd infra
   docker compose up -d
   ```

   Détails et identifiants de démonstration dans `infra/README.md`.

2. Copier les variables d'environnement et installer l'API :

   ```bash
   cd services/api
   cp ../../.env.example ../../.env   # à adapter si besoin
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt -r requirements-dev.txt
   ```

3. Appliquer les migrations de base de données :

   ```bash
   alembic upgrade head
   ```

4. Démarrer l'API :

   ```bash
   uvicorn app.main:app --reload
   ```

L'API est alors disponible sur http://localhost:8000 :
- `/health` : l'API répond.
- `/health/db` : l'API répond ET arrive à parler à la base de données.
- `/me` : nécessite un jeton d'authentification valide (voir `infra/README.md` pour en
  obtenir un de test).
- `/admin/ping` : nécessite en plus le rôle `admin_tenant`.

## Tests et qualité de code

Depuis `/services/api` (avec l'environnement virtuel activé, et la base de données
démarrée) :

```bash
pytest
ruff check .
ruff format .
```

## Migrations de base de données (Alembic)

Après avoir modifié les modèles de données, créer une nouvelle migration :

```bash
cd services/api
alembic revision --autogenerate -m "description du changement"
alembic upgrade head
```

Toujours relire une migration générée automatiquement avant de l'appliquer.

## Variables d'environnement

Copier `.env.example` en `.env` et adapter les valeurs. Aucun secret ne doit être commité
dans ce dépôt.
