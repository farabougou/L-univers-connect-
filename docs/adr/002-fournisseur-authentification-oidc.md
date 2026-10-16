# ADR 002 — Fournisseur d'authentification OpenID Connect

## Statut

Acceptée (21 septembre 2026).

## Contexte

L'étape 0.4 de la Phase 0 demande de mettre en place l'authentification via OpenID
Connect (OIDC), un standard ouvert de connexion, en laissant le choix du fournisseur à
trancher par ADR. Le cahier des charges impose deux contraintes non négociables qui
pèsent directement sur ce choix :

- Pas de dépendance à un constructeur ou service tiers dans le noyau du produit ; toute
  intégration externe doit passer par un adaptateur remplaçable.
- Portabilité de l'hébergement : le MVP tourne sur Railway, mais le code doit pouvoir
  migrer vers un hébergeur européen si un client l'exige, sans dépendance propriétaire.

Deux familles de solutions existaient :

1. **Service SaaS tiers** (Auth0, Clerk, etc.) : rapide à démarrer, mais payant au-delà
   d'un certain nombre d'utilisateurs actifs, hébergé par un tiers (souvent américain),
   et créant une dépendance externe difficile à sortir du noyau.
2. **Solution auto-hébergée, open source, standard OIDC** (Keycloak) : plus de
   configuration initiale, mais aucun abonnement, aucune dépendance à un tiers, et
   portable vers n'importe quel hébergeur Docker.

## Décision

Le fournisseur OIDC du MVP est **Keycloak**, auto-hébergé via Docker Compose, au même
titre que PostgreSQL. L'application ne dépend jamais d'un SDK propriétaire Keycloak :
elle communique uniquement via le protocole standard OpenID Connect (JWT signés,
endpoint JWKS de découverte des clés publiques). Ce choix constitue l'adaptateur exigé
par la règle 8 : remplacer Keycloak par un autre fournisseur OIDC (Ory, Auth0, un futur
service géré) ne demandera qu'un changement de configuration (URL de l'émetteur), pas de
réécriture du code métier.

Les rôles applicatifs de base retenus pour le MVP sont : `technicien`,
`responsable_exploitation`, `admin_tenant`. Ils correspondent aux personas identifiés
dans le cahier des charges (section 26.2) et seront affinés à l'étape 0.5 (autorisations
fines, ReBAC).

## Conséquences

- Un nouveau service `keycloak` est ajouté à `infra/docker-compose.yml`, avec un realm
  pré-configuré (`infra/keycloak/realm-export.json`) important les rôles de base.
- L'API valide les jetons JWT reçus en vérifiant leur signature auprès du endpoint JWKS
  de Keycloak (bibliothèque `python-jose`), sans jamais faire confiance à un jeton non
  vérifié.
- Les tests automatiques de la logique de vérification ne démarrent pas un vrai serveur
  Keycloak (trop lent et fragile en intégration continue) : ils utilisent une paire de
  clés de test générée localement pour simuler un jeton signé par un fournisseur OIDC
  conforme au standard.
- Coût d'exploitation : aucun abonnement. Coût d'administration : Mohamed (ou un futur
  collègue) doit apprendre les bases de l'administration Keycloak (création
  d'utilisateurs, réalimentation du realm), documentée dans `infra/README.md`.
