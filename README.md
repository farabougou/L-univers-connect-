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

## Démarrer en local (API)

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

L'API est alors disponible sur http://localhost:8000, avec une route de santé sur
`/health`.

## Tests et qualité de code

Depuis `/services/api` (avec l'environnement virtuel activé) :

```bash
pytest
ruff check .
ruff format .
```

## Variables d'environnement

Copier `.env.example` en `.env` et adapter les valeurs. Aucun secret ne doit être commité
dans ce dépôt.
