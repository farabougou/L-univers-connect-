#!/bin/sh
# Audit des dépendances : API (Python), web et mobile (npm). À lancer à chaque jalon et avant
# une livraison (voir docs/security/registre-vulnerabilites.md) : les bases d'avis bougent sans
# que notre code change (un avis sur pypdf est apparu en deux jours, le 23/10/2026).
#
# Utilisation, depuis la racine du dépôt :   sh infra/audit-dependances.sh
#
# Code de sortie :
#   0  aucune vulnérabilité connue en production pour l'API et le web ;
#   1  au moins une : à traiter ou à justifier dans le registre ;
#   2  l'audit n'a pas pu être fait (outil ou réseau indisponible). Un audit impossible n'est
#      jamais présenté comme un audit propre.
# Le mobile est affiché mais ne fait pas échouer le script : ses avis de production viennent de
# l'outillage Expo et sont justifiés un par un dans le registre (rétrogradations proposées par
# `npm audit fix --force` rejetées). Comparer le nombre affiché au registre.
#
# Ne modifie aucun fichier du dépôt : `pip-audit` s'installe, si besoin, dans un dossier
# temporaire supprimé à la fin.

racine=$(cd "$(dirname "$0")/.." && pwd)
temporaire=$(mktemp -d)
trap 'rm -rf "$temporaire"' EXIT
resultat=0

echo "== API (Python) : pip-audit"
if command -v pip-audit >/dev/null 2>&1; then
  pip_audit=pip-audit
else
  echo "pip-audit absent : installation dans un dossier temporaire."
  if python3 -m venv "$temporaire/venv" >/dev/null 2>&1 \
    && "$temporaire/venv/bin/pip" install -q pip-audit >/dev/null 2>&1; then
    pip_audit="$temporaire/venv/bin/pip-audit"
  else
    echo "Impossible d'installer pip-audit (réseau ou Python indisponible)." >&2
    exit 2
  fi
fi
for fichier in requirements.txt requirements-dev.txt; do
  echo "-- services/api/$fichier"
  "$pip_audit" -r "$racine/services/api/$fichier" --progress-spinner off
  statut=$?
  if [ "$statut" -eq 1 ]; then
    resultat=1
  elif [ "$statut" -ne 0 ]; then
    echo "pip-audit n'a pas pu conclure (code $statut)." >&2
    exit 2
  fi
done

audit_npm() {
  dossier=$1
  echo "-- $dossier (dépendances de production)"
  (cd "$racine/$dossier" && npm audit --omit=dev)
}

echo
echo "== Web : npm audit, production seulement"
audit_npm apps/web
statut=$?
if [ "$statut" -eq 1 ]; then
  resultat=1
elif [ "$statut" -ne 0 ]; then
  echo "npm audit n'a pas pu conclure (code $statut)." >&2
  exit 2
fi

echo
echo "== Mobile : npm audit, production seulement (affiché, ne fait pas échouer le script)"
audit_npm apps/mobile
statut=$?
if [ "$statut" -ne 0 ] && [ "$statut" -ne 1 ]; then
  echo "npm audit n'a pas pu conclure pour le mobile (code $statut)." >&2
  exit 2
fi

echo
if [ "$resultat" -eq 0 ]; then
  echo "Résultat : aucune vulnérabilité connue en production (API et web)."
else
  echo "Résultat : des vulnérabilités existent en production (API ou web). Voir ci-dessus." >&2
fi
exit "$resultat"
