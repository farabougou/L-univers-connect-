#!/bin/sh
# Sauvegarde de la base PostgreSQL (format personnalisé pg_dump, compressé,
# compatible pg_restore en parallèle) — voir docs/architecture/failure-modes.md
# ligne « Perte de la base », marquée « à faire avant le premier client » et
# jamais traitée jusqu'ici.
#
# Railway fournit des sauvegardes automatiques gérées sur son offre
# PostgreSQL (infra/RAILWAY_STAGING.md) : ce script n'est pas un remplacement
# de ce mécanisme en production, mais la procédure testée et reproductible
# que ce dépôt garantit indépendamment de l'hébergeur (règle du dépôt :
# rester portable, sans dépendance propriétaire à Railway).
#
# IMPORTANT — rôle dédié obligatoire : chaque table métier a FORCE ROW LEVEL
# SECURITY (règle non négociable du dépôt), qui s'applique même au
# propriétaire de la table. Le rôle applicatif ("paios") ne peut donc PAS
# servir à une sauvegarde : pg_dump échouerait table par table, ou pire, ne
# sauvegarderait qu'un seul tenant si un contexte était fixé. Il faut un
# rôle séparé, dédié à la sauvegarde, avec l'attribut BYPASSRLS et SELECT
# seul (jamais d'écriture) — jamais le rôle qui sert les requêtes de
# l'application, pour ne pas affaiblir l'isolation en production :
#
#   CREATE ROLE paios_backup WITH LOGIN PASSWORD '...' BYPASSRLS;
#   GRANT CONNECT ON DATABASE paios TO paios_backup;
#   GRANT USAGE ON SCHEMA public TO paios_backup;
#   GRANT SELECT ON ALL TABLES IN SCHEMA public TO paios_backup;
#
# Usage :
#   DATABASE_URL=postgresql+psycopg://paios_backup:...@host:5432/dbname \
#     scripts/backup_database.sh [répertoire_de_sortie]
set -e

: "${DATABASE_URL:?DATABASE_URL doit être défini, avec le rôle paios_backup (voir commentaire ci-dessus)}"
OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"

# pg_dump ne connaît pas le suffixe de pilote SQLAlchemy ("+psycopg").
PG_URL=$(echo "$DATABASE_URL" | sed 's#^postgresql+psycopg://#postgresql://#')

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT_FILE="$OUT_DIR/paios-$TIMESTAMP.dump"

pg_dump --format=custom --no-owner --no-privileges --file="$OUT_FILE" "$PG_URL"

echo "Sauvegarde écrite : $OUT_FILE"
