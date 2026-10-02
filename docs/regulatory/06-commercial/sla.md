# Accord de niveau de service (SLA) — `TO_FINALIZE`

> **Gabarit, non contractuel.** Les engagements chiffrés ci-dessous sont des
> exemples de structure, pas des valeurs engageantes — à fixer une fois
> l'hébergement de production réel mesuré dans la durée, jamais promis par
> avance sans donnée.

## 1. Disponibilité

`[objectif de disponibilité mensuelle, ex. 99,5 % — à fixer selon la
réalité observée de l'hébergement choisi (Railway ou un hébergeur européen
de repli, voir CLAUDE.md), jamais un chiffre copié d'un concurrent]`

## 2. Fenêtres de maintenance

`[fréquence, préavis, créneaux privilégiés]`

## 3. Support

| Niveau de gravité | Exemple | Délai de première réponse | Délai de résolution visé |
|---|---|---|---|
| Critique | `[ex. plateforme inaccessible pour tous les clients]` | `[à définir]` | `[à définir]` |
| Majeur | `[ex. une fonctionnalité clé indisponible]` | `[à définir]` | `[à définir]` |
| Mineur | `[ex. anomalie d'affichage]` | `[à définir]` | `[à définir]` |

## 4. Sauvegarde et reprise après sinistre

`[fréquence des sauvegardes, durée de rétention, objectif de point de
reprise (RPO) et de délai de reprise (RTO) — cohérent avec la règle du
dépôt « migrations en trois temps, pas de migration destructive sans
sauvegarde vérifiée »]`

## 5. Mesure et reporting

`[comment la disponibilité réelle sera mesurée et communiquée au Client —
à construire avec de vraies données de production, pas une promesse
abstraite]`

## 6. Pénalités

`[le cas échéant, crédits de service en cas de non-respect — à définir avec
l'Éditeur et un avocat]`
