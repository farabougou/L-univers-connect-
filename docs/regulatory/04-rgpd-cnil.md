# RGPD / CNIL — Registre des traitements

## Référence officielle

- CNIL, registre des traitements : <https://www.cnil.fr/fr/RGPD-le-registre-des-activites-de-traitement>
- Obligation : tout responsable de traitement (ou sous-traitant) doit tenir
  un registre de ses activités de traitement de données personnelles
  (RGPD, article 30).

Qui est responsable de traitement, pour quelles données : à déterminer selon
le modèle commercial réel (ENORYX éditeur du logiciel vs. le client tenant,
exploitant du bâtiment, responsable des données de ses propres techniciens)
— voir la section « À finaliser » en bas de page.

## Ce qu'ENORYX doit prévoir

Registre des traitements, finalités, catégories de données, accès,
conservation, sécurité, sous-traitants et transferts éventuels.

## Ce que la plateforme traite réellement (02/10/2026)

Le noyau du produit (actifs physiques, CVC, télémétrie) traite très peu de
données personnelles directement : l'essentiel de ce qui circule concerne
des équipements, pas des personnes. Les données personnelles réelles sont
concentrées dans un petit nombre de traitements, listés ici tels qu'ils
existent dans le code aujourd'hui.

| # | Traitement | Finalité | Catégories de données | Personnes concernées | Base légale | Conservation | Système |
|---|---|---|---|---|---|---|---|
| 1 | Comptes et authentification | Identifier une personne, limiter ses actions à son rôle et à son tenant | Identifiant, nom, rôle(s), tenant d'appartenance | Employés du client (techniciens, responsables, administrateurs) | Exécution du contrat (accès au service souscrit par le client) | Durée du compte actif ; Keycloak (identité), pas de duplication dans le noyau métier | Keycloak (OIDC), `app/auth.py` |
| 2 | Journal d'audit | Preuve de qui a fait quoi, quand, sur quelle donnée sensible (sécurité, litiges, obligations légales type CERFA) | Identifiant de la personne ou de l'appareil ayant agi, horodatage, nature de l'action | Employés du client, appareils Edge | Obligation légale (traçabilité réglementaire) + intérêt légitime (sécurité) | Jamais supprimé (`audit_log`, append-only) — durée à documenter dans la politique de conservation réelle de l'exploitant | `app/audit.py` |
| 3 | Interventions, clôtures, fiches F-Gas | Historique de maintenance, preuve réglementaire (F-Gas) | Nom du technicien (texte libre saisi par le client), nature de l'intervention | Techniciens du client ou de ses prestataires | Obligation légale (F-Gas, CERFA 15497*04) + exécution du contrat | Jamais supprimé (preuve réglementaire, 5 ans minimum imposés par le code de l'environnement pour le CERFA) | `app/maintenance.py`, `app/closures.py`, `app/fgas.py` |
| 4 | Photos d'intervention | Preuve visuelle d'une intervention | Image (peut incidemment montrer une personne) | Techniciens du client, tiers présents sur site | Exécution du contrat | Comme les autres preuves d'intervention, jamais supprimée | ADR 006 |
| 5 | Prestataires (`providers`) | Répertorier qui assure la maintenance d'un équipement | Nom, contact d'un prestataire (personne morale ou physique) | Prestataires du client | Exécution du contrat | Tant que la relation existe ; pas de purge automatique aujourd'hui | `app/routers/providers.py` |

**Explicitement hors champ aujourd'hui** (aucune collecte dans le code) :
données de santé, données biométriques, données de géolocalisation
individuelle en continu, données de paiement (la facturation de
l'hébergement Railway est hors plateforme), profilage automatisé de
personnes.

## Mesures de sécurité déjà en place (à citer dans le registre)

- Isolation stricte par client : Row Level Security PostgreSQL sur chaque
  table métier, prouvée par un test dédié à chaque nouvelle table (règle non
  négociable du dépôt).
- Chiffrement en transit : HTTPS obligatoire (hébergement et API) ; identité
  des appareils Edge par preuve cryptographique (JWT ES256), jamais un
  secret partagé en clair pour les nouveaux appareils.
- Journalisation append-only, chaînée par hachage pour les actions sensibles.
- Aucun secret dans le dépôt de code (variables d'environnement seulement).
- Principe de minimisation déjà appliqué par construction : le noyau
  technique (actifs, points, mesures) ne porte aucune donnée personnelle ;
  les noms de personnes n'apparaissent que là où une preuve réglementaire ou
  contractuelle l'exige (intervention, clôture, fiche F-Gas, audit).

## Lacune identifiée (à corriger, pas seulement à documenter)

**Aucun mécanisme d'exercice des droits RGPD (accès, rectification,
effacement, portabilité) n'existe aujourd'hui dans le produit** : un
administrateur Keycloak peut modifier ou supprimer un compte via la console
Keycloak elle-même, mais aucun endpoint applicatif ne permet d'exporter ou
d'anonymiser les données personnelles qu'une personne a laissées dans le
noyau métier (champs texte libre `technician`, `closed_by`, `created_by`…).
Signalé ici plutôt qu'ignoré — à ajouter à la feature-benchmark-matrix
comme futur chantier (DEFER, pas bloquant pour V1-V4, mais à ne pas oublier
avant un premier client réel traitant des données de salariés).

## À finaliser (`TO_FINALIZE`) — dépend de l'entreprise exploitante

- Identité du responsable de traitement (raison sociale, adresse, SIRET) et
  contact DPO ou référent RGPD, le cas échéant.
- Liste réelle des sous-traitants (hébergeur, Keycloak le cas échéant géré
  par un tiers, tout service de messagerie ou de support) et leurs garanties
  contractuelles (clauses RGPD, localisation des données).
- Durées de conservation précises par catégorie de donnée, au-delà du
  minimum légal déjà respecté par construction (jamais de suppression
  précoce) — une durée maximale documentée reste à fixer avec un conseil
  juridique.
- Transferts hors Union européenne, le cas échéant (dépend de l'hébergeur
  choisi au moment de la commercialisation réelle).
- Analyse d'impact relative à la protection des données (AIPD), si le volume
  ou la nature des traitements l'exige une fois le nombre de clients connu.
