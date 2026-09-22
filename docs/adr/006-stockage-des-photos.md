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
