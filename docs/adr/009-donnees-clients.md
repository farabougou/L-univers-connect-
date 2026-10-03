# ADR 009 — Données clients

## Statut

Acceptée (22 septembre 2026).

## Contexte

Le cahier des charges (section 34) identifie plusieurs cadres réglementaires que la
plateforme doit respecter par conception, notamment le RGPD (protection des données
personnelles), et évoque d'autres textes sectoriels (CRA, Data Act, F-gas,
OPERAT/BACS) qui deviendront pertinents à mesure que le produit couvre plus de
fonctionnalités. Cette ADR fixe les principes déjà appliqués depuis le début du projet
et ceux qui restent à construire.

Les données que la plateforme traitera relèvent de deux catégories bien distinctes :

1. **Données des clients (tenants)** : informations sur leurs sites, équipements,
   interventions. Sensibles commercialement, mais rarement des données personnelles au
   sens du RGPD.
2. **Données personnelles des utilisateurs** : techniciens, responsables
   d'exploitation, administrateurs — noms, emails, actions effectuées.

## Décision

**Isolation stricte comme première ligne de défense.** Chaque tenant est isolé au
niveau base de données par Row Level Security forcée (étape 0.3), pas seulement par un
filtre applicatif. C'est la protection la plus fondamentale contre une fuite de données
entre clients, et elle existe dès la première table métier du projet.

**Minimisation dès la conception.** Les futurs modèles de données (à partir de M1) ne
porteront que les champs personnels strictement nécessaires (par exemple, un
technicien identifié par son compte Keycloak plutôt que dupliqué dans chaque table
métier). Le stockage centralisé des identités dans Keycloak (ADR 002) limite déjà
la duplication de données personnelles à travers le système.

**Aucune donnée personnelle réelle en dehors de la production.** Tous les jeux de
données de test et de démonstration utilisent des identités fictives, avec des
domaines d'email réservés à cet usage (`@example.invalid`), jamais de vraies
coordonnées de personnes. C'est déjà le cas des utilisateurs de démonstration Keycloak
(`demo.technicien`, `demo.admin`) et de tous les tests automatisés du projet.

**Traçabilité par le journal d'audit.** Le journal chaîné par hachage (étape 0.5)
enregistrera, à mesure que des actions sensibles sur des données personnelles ou
clients seront ajoutées (consultation, export, suppression), qui a fait quoi et quand,
de façon infalsifiable. C'est la brique technique qui permettra de répondre à une
demande d'audit ou de preuve de conformité.

**Ce qui reste à construire, hors périmètre de la Phase 0** :

- Le droit à l'effacement et à la portabilité des données personnelles (RGPD) :
  nécessitera des procédures d'export et de suppression contrôlée, à concevoir quand
  de vraies données personnelles utilisateurs existeront en base (au-delà des comptes
  Keycloak).
- Le chiffrement au repos de champs particulièrement sensibles, au cas par cas, si un
  client ou une réglementation sectorielle l'exige (au-delà du chiffrement standard de
  l'hébergeur).
- Un registre des traitements et une analyse d'impact (AIPD) formels, à produire avant
  la commercialisation, en dehors du périmètre technique de ce dépôt.

## Conséquences

- Toute nouvelle table métier suit le même schéma d'isolation par RLS déjà en place
  (ADR 003), sans exception.
- Toute donnée d'exemple, de test ou de démonstration ajoutée au projet doit rester
  fictive, sous peine de contredire la règle non négociable 9 du projet.
- Cette ADR sera complétée dès que le registre d'actifs (M1) introduira les premières
  vraies données personnelles utilisateur au-delà des comptes Keycloak, notamment pour
  préciser les procédures d'export et de suppression.
