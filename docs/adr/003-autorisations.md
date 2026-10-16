# ADR 003 — Autorisations

## Statut

Acceptée (22 septembre 2026).

## Contexte

Le cahier des charges (section 25.2) recommande à terme un contrôle d'accès fondé sur
les relations (ReBAC, sur un graphe, via un moteur comme OpenFGA ou SpiceDB) combiné à
la sécurité PostgreSQL au niveau ligne (RLS). L'objectif final : les droits suivent la
hiérarchie site / bâtiment / zone / système, avec des délégations possibles à des
prestataires externes (par exemple, un sous-traitant qui n'a accès qu'à un seul site).

Ce modèle fin est complexe à mettre en place et n'a de valeur que face à de vrais cas de
délégation. Les étapes 0.3 et 0.4 de la Phase 0 ont déjà posé deux briques
indépendantes et déjà fonctionnelles :

- **Isolation entre tenants (clients) par RLS PostgreSQL**, forcée au niveau base de
  données (étape 0.3) : un tenant ne peut structurellement pas voir les données d'un
  autre, quel que soit le code applicatif.
- **Rôles globaux par tenant via Keycloak** (étape 0.4) : `technicien`,
  `responsable_exploitation`, `admin_tenant`, portés dans le jeton OpenID Connect et
  vérifiés par l'API (`app/auth.py::require_role`).

## Décision

**Pour le MVP, les autorisations combinent RLS (isolation entre tenants) et RBAC par
rôles globaux (Keycloak) plutôt qu'un ReBAC complet dès le départ.** Un rôle
(`technicien`, `responsable_exploitation`, `admin_tenant`) s'applique à l'ensemble du
tenant de l'utilisateur, sans encore de restriction fine par site, bâtiment ou zone.

**Le ReBAC (OpenFGA, SpiceDB ou équivalent) est différé** jusqu'à ce qu'un vrai besoin
de délégation partielle apparaisse (par exemple : un prestataire multi-sites qui ne
doit voir qu'un sous-ensemble des sites d'un même tenant, ou un technicien limité à
certaines zones). Ce déclencheur est cohérent avec la règle des trois du cahier des
charges (section 26.1) : ne pas généraliser une abstraction avant d'avoir vu plusieurs
cas réels qui la justifient.

**Ce que RLS ne remplace pas.** RLS protège l'isolation entre tenants (rule non
négociable 2), pas les autorisations fines à l'intérieur d'un même tenant. Les deux
mécanismes sont complémentaires et resteront tous les deux en place même après
l'introduction d'un ReBAC : RLS reste le filet de sécurité de dernier recours contre les
fuites entre tenants, le ReBAC gérera la granularité à l'intérieur d'un tenant.

## Conséquences

- Toute nouvelle table métier (à partir de M1) doit reproduire le schéma déjà établi :
  colonne `tenant_id`, RLS activée et forcée, politique fondée sur
  `app.current_tenant_id` (voir `app/tenancy.py`).
- Toute nouvelle route protégée par rôle réutilise `app.auth.require_role`, en
  choisissant parmi les rôles déjà définis dans le realm Keycloak ou en ajoutant un
  nouveau rôle réaliste (jamais un rôle spéculatif « au cas où »).
- Le jour où un ReBAC devient nécessaire, il s'ajoutera comme une couche
  supplémentaire de vérification (probablement une dépendance FastAPI qui interroge le
  moteur ReBAC), sans remettre en cause ni le RLS existant ni les rôles Keycloak actuels.
- Cette ADR devra être révisée (nouveau statut « remplacée » ou « complétée ») le jour
  où le ReBAC sera effectivement introduit.
