#!/bin/sh
# Démarrage du conteneur API : échoue vite plutôt qu'à moitié.
#
# 1. Le catalogue de textes doit être embarqué (voir app/i18n.py) : sans lui,
#    l'interface afficherait des codes bruts aux utilisateurs au lieu de
#    phrases, une régression silencieuse qu'on préfère détecter ici, au
#    démarrage, plutôt qu'en production.
# 2. Les migrations sont rejouées à chaque démarrage (Alembic est idempotent :
#    une base déjà à jour ne fait rien) — jamais une étape manuelle séparée
#    qu'on pourrait oublier avant un déploiement.
set -e

CATALOG_DIR="${I18N_DIR:-/app/shared/i18n}"
if [ ! -f "$CATALOG_DIR/fr/errors.json" ]; then
  echo "Catalogue i18n introuvable dans $CATALOG_DIR — démarrage interrompu." >&2
  exit 1
fi

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
