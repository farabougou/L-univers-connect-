# Construit avec la racine du dépôt comme contexte (voir infra/RAILWAY_STAGING.md) :
# `shared/i18n` vit hors de `services/api` mais doit être livré avec l'API
# (voir app/i18n.py) — jamais deviné, toujours embarqué explicitement ici.
FROM python:3.12-slim

WORKDIR /app

COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api/app ./app
COPY services/api/migrations ./migrations
COPY services/api/alembic.ini .
COPY services/api/scripts ./scripts
COPY shared/i18n ./shared/i18n

ENV I18N_DIR=/app/shared/i18n
ENV PYTHONUNBUFFERED=1

RUN chmod +x scripts/docker-entrypoint.sh

EXPOSE 8000
CMD ["./scripts/docker-entrypoint.sh"]
