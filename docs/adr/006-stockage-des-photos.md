# ADR 006 — Stockage des photos

## Statut

Acceptée (22 septembre 2026).

## Contexte

L'application technicien (M1.3) doit permettre de prendre des photos lors d'une
intervention ou d'une ronde — une exigence confirmée par Mohamed comme systématique
("toujours prendre une photo avant"), quel que soit le type d'activité. Une photo pèse
plusieurs centaines de kilo-octets à plusieurs méga-octets : elle ne peut pas être
stockée dans PostgreSQL comme les autres données métier (ça fonctionnerait
techniquement, mais dégraderait les performances et les sauvegardes de la base pour
tout le monde).

Il faut un espace de stockage de fichiers binaires (« object storage »), séparé de la
base de données. Deux familles de solutions existent :

1. Un service cloud propriétaire (AWS S3, Google Cloud Storage) : fiable, mais
   dépendance directe à un fournisseur si on utilise son SDK spécifique.
2. Le **protocole S3**, devenu un standard de fait : de nombreux fournisseurs
   (MinIO auto-hébergé, Cloudflare R2, Backblaze B2, AWS S3 lui-même, etc.) exposent
   tous la même interface. Un client S3 générique fonctionne avec n'importe lequel
   d'entre eux, changeable par configuration.

## Décision

**Le protocole S3 est l'interface retenue**, exactement comme OpenID Connect a été
retenu pour l'authentification (ADR 002) : un standard ouvert plutôt qu'un SDK
propriétaire, conformément à la règle non négociable 8.

- **En développement local** : **MinIO**, auto-hébergé via Docker Compose, aux côtés de
  PostgreSQL et Keycloak. Gratuit, aucune dépendance externe pour développer.
- **En production** : le choix du fournisseur (MinIO auto-hébergé, Cloudflare R2,
  Backblaze B2...) sera fait au moment du déploiement, sans impact sur le code
  applicatif — seule la configuration (URL du service, identifiants, nom du panier de
  stockage) change.
- **Adaptateur** : l'API ne parle jamais directement à un SDK propriétaire. Toute
  interaction passe par `app/storage.py`, qui encapsule la génération d'URLs
  pré-signées (upload et téléchargement temporaires, sans exposer les identifiants
  d'accès au client mobile).
- **Flux retenu** : l'application mobile ne transite pas les photos par notre API
  (trop lourd, surtout en 4G limitée sur certains sites). Elle demande une URL
  temporaire d'upload, envoie la photo directement au stockage, puis confirme à l'API
  que l'upload a réussi pour enregistrer la référence (pas le contenu) en base.

## Conséquences

- Une nouvelle table `intervention_photos` référence chaque photo par sa clé de
  stockage (chemin dans le panier), pas par son contenu binaire.
- Le contenu réel des photos n'est jamais dans PostgreSQL ni dans le dépôt Git.
- Aucun identifiant d'accès au stockage n'est exposé au client mobile : il reçoit une
  URL temporaire à usage unique, jamais les clés d'accès elles-mêmes.
- Cette étape ne force pas encore l'usage : la contrainte « toujours une photo avant »
  reste une règle d'usage côté application mobile (M1.3), pas encore une contrainte
  bloquante côté API — à durcir plus tard si un vrai besoin de conformité l'exige.

## Choix du fournisseur pour le staging (Mohamed, 25/09/2026)

**Cloudflare R2** plutôt que MinIO auto-hébergé sur Railway : compatible S3 sans aucun
changement de code (confirme la décision ci-dessus), pas de frais de sortie de données
(chaque consultation de photo par un technicien ou un exploitant est un
téléchargement — un poste qui peut dominer la facture chez un fournisseur qui facture
la sortie), et des options de localisation des données en Europe qui vont dans le sens
de la contrainte RGPD déjà notée à l'ADR 005. Un MinIO auto-hébergé n'apporterait
aujourd'hui aucun bénéfice technique, seulement une charge d'exploitation
(disponibilité, sauvegardes, mises à jour) que l'équipe n'a pas à porter tant qu'un
vrai besoin de souveraineté ne l'exige pas.

**Condition pour que ce choix reste réversible** : n'utiliser R2 qu'à travers l'API S3
générique (`app/storage.py`), jamais une fonctionnalité propre à Cloudflare (par
exemple un rattachement direct depuis un Worker). C'est cette discipline, pas le choix
du fournisseur lui-même, qui garantit que changer de fournisseur reste un changement de
configuration.

**Risque de blocage futur, signalé maintenant (règle non négociable 8, section 6 du
cahier de collaboration)** : la configuration de stockage est aujourd'hui **unique
pour toute la plateforme** (un seul panier, un seul fournisseur, dans
`app.config.settings`). Le jour où un client exigera un hébergeur précis pour des
raisons de conformité (un client français avec OVHcloud, par exemple), ce choix devra
se faire **par tenant**, pas globalement. Ne pas construire cette granularité
maintenant — aucun besoin réel aujourd'hui — mais la prévoir avant qu'un contrat client
ne l'impose dans l'urgence : le jour venu, `build_object_key` et `_client()`
(`app/storage.py`) devront résoudre le fournisseur et le panier à partir du
`tenant_id`, plutôt que d'une configuration globale.
