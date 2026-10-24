#!/bin/sh
# Restauration d'une sauvegarde pg_dump (voir scripts/backup_database.sh).
#
# Opération destructive par nature (écrase la base cible) : exige
# --confirm explicitement, jamais une exécution accidentelle (règle du
# dépôt sur les actions à risque).
#
# Usage :
#   DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname \
#     scripts/restore_database.sh fichier.dump --confirm
set -e

: "${DATABASE_URL:?DATABASE_URL doit être défini (voir app/config.py)}"
DUMP_FILE="$1"
CONFIRM="$2"

if [ -z "$DUMP_FILE" ] || [ ! -f "$DUMP_FILE" ]; then
  echo "Usage : $0 <fichier.dump> --confirm" >&2
  exit 1
fi
if [ "$CONFIRM" != "--confirm" ]; then
  echo "Cette opération écrase la base cible. Relancer avec --confirm pour continuer." >&2
  exit 1
fi

PG_URL=$(echo "$DATABASE_URL" | sed 's#^postgresql+psycopg://#postgresql://#')

pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$PG_URL" "$DUMP_FILE"

echo "Restauration terminée depuis : $DUMP_FILE"
