# ADR 005 — Hébergement

## Statut

Acceptée (22 septembre 2026).

## Contexte

Mohamed dispose déjà d'un abonnement Railway payé, une plateforme d'hébergement simple
qui déploie des conteneurs Docker sans gestion d'infrastructure lourde. C'est un bon
choix pour démarrer vite avec des moyens limités. Mais le cahier des charges impose deux
contraintes qui dépassent ce choix initial :

- Le produit vise des clients dans plusieurs pays, avec des exigences de localisation
  des données parfois strictes (RGPD pour des clients européens, en particulier).
- Le noyau ne doit dépendre d'aucun service propriétaire d'un hébergeur particulier
  (règle non négociable 8), pour rester libre de changer d'hébergeur si un client
  l'exige, sans réécriture du code métier.

## Décision

**Railway héberge le MVP**, mais uniquement comme exécutant de conteneurs Docker
standards : aucune fonctionnalité propriétaire Railway (stockage spécifique, files de
message maison, etc.) n'est appelée depuis le code métier. Toute configuration
dépendante de l'environnement (URL de base de données, émetteur OpenID Connect,
secrets) passe par des variables d'environnement, jamais par une intégration Railway
spécifique dans le code.

Concrètement, ce que ça change dans la pratique :

- Le `docker-compose.yml` de développement local (PostgreSQL, Keycloak) doit pouvoir
  se déployer, avec des adaptations de configuration seulement, sur n'importe quel
  hébergeur qui exécute des conteneurs Docker (un cloud européen inclus).
- Aucune bibliothèque cliente propriétaire Railway n'entre dans les dépendances de
  `services/api`.
- Les migrations, le code d'accès à la base de données (`app/db.py`,
  `app/config.py`) et l'authentification (`app/auth.py`) ne connaissent que des
  standards ouverts (PostgreSQL, OpenID Connect/JWT), jamais un détail propre à
  Railway.

**Aucun déploiement n'a lieu avant l'étape M1**, et jamais sans l'accord explicite de
Mohamed (règle du cahier de collaboration), conformément à la prudence demandée pour
toute action qui affecte un système partagé au-delà de l'environnement local.

## Conséquences

- Migrer vers un hébergeur européen, si un client l'exige un jour, se limite à changer
  les variables d'environnement et à redéployer les mêmes images Docker : pas de
  réécriture de code métier.
- Le choix d'hébergement pourra être révisé (nouvelle ADR) si Railway ne suit pas la
  croissance du produit (montée en charge, conformité) ; cette portabilité, posée dès
  maintenant, rend ce changement possible sans dette technique cachée.
- Cette contrainte ajoute un peu de discipline dès le départ (toujours passer par des
  variables d'environnement, jamais coder en dur une adresse ou un identifiant propre
  à Railway), pour un gain de flexibilité important plus tard.
