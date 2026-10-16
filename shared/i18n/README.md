# Textes du produit (français et anglais)

Référence : ADR 013 et `docs/product/glossaire.md`. Aucun texte visible n'est
écrit en dur dans le code : tout passe par ces catalogues.

| Fichier | Utilisé par | Contenu |
|---|---|---|
| `fr/errors.json`, `en/errors.json` | API (et web pour afficher une erreur par son code) | Messages d'erreur, par code stable |
| `fr/findings.json`, `en/findings.json` | API | Titres et actions recommandées des constats, par code de raison |
| `fr/closure.json`, `en/closure.json` | API | Libellés des codes de clôture d'intervention |
| `fr/ui.json`, `en/ui.json` | Web et mobile | Textes des écrans |
| `translator.ts` | Web et mobile | Traduction, pluriels, dates, nombres, fuseaux (sans dépendance) |

## Ajouter ou modifier un texte

1. Vérifier le terme dans `docs/product/glossaire.md` (l'y ajouter s'il manque).
2. Écrire le texte **dans les deux langues**, au même emplacement, avec les
   mêmes paramètres `{nom}`. Pluriel : `{ "one": "…", "other": "…" }` avec le
   paramètre `count`.
3. Français : vouvoiement, apostrophe typographique `’`, espace insécable avant
   `: ; ? !` et à l'intérieur de `« »`.
4. Pour les écrans : `cd apps/web` (ou `apps/mobile`) puis `npm run i18n:sync`
   pour recopier les catalogues dans l'application.
5. Lancer les tests : ils vérifient la parité français/anglais, les
   paramètres, la typographie, l'absence de tutoiement et d'émoji, et que les
   copies des applications sont identiques à ce dossier.
