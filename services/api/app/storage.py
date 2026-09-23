"""Adaptateur de stockage des photos, derrière l'interface standard S3.

Voir ADR 006 : aucun code applicatif ne dépend d'un fournisseur particulier.
Changer de fournisseur (MinIO, Cloudflare R2, Backblaze B2, AWS S3...) ne
demande que de changer la configuration (app.config.settings), jamais ce
module.
"""

import uuid
from datetime import timedelta

import boto3
from botocore.client import Config

from app.config import settings

_PRESIGNED_URL_EXPIRY_SECONDS = int(timedelta(minutes=15).total_seconds())


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        region_name=settings.storage_region,
        config=Config(signature_version="s3v4"),
    )


def build_object_key(*, tenant_id: uuid.UUID, intervention_id: uuid.UUID, filename: str) -> str:
    """Construit un chemin de stockage qui isole déjà les photos par tenant.

    Le chemin lui-même ne remplace pas la RLS (qui protège les métadonnées en
    base), mais évite par construction toute collision entre tenants dans le
    panier de stockage partagé.
    """
    safe_filename = filename.replace("/", "_")
    return f"{tenant_id}/{intervention_id}/{uuid.uuid4()}-{safe_filename}"


def key_belongs_to(object_key: str, *, tenant_id: uuid.UUID, intervention_id: uuid.UUID) -> bool:
    """Vrai seulement pour une clé du dossier de cette intervention, chez ce
    tenant, sans sous-dossier. Sans ce contrôle, connaître la clé d'une photo
    d'un autre client suffirait pour obtenir un lien de téléchargement."""
    prefix = f"{tenant_id}/{intervention_id}/"
    if not object_key.startswith(prefix):
        return False
    name = object_key[len(prefix) :]
    return bool(name) and "/" not in name and name not in (".", "..")


def create_presigned_upload_url(object_key: str, *, content_type: str) -> str:
    """URL temporaire à usage unique : le client mobile envoie la photo
    directement au stockage, sans jamais recevoir les identifiants d'accès."""
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.storage_bucket, "Key": object_key, "ContentType": content_type},
        ExpiresIn=_PRESIGNED_URL_EXPIRY_SECONDS,
    )


def create_presigned_download_url(object_key: str) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.storage_bucket, "Key": object_key},
        ExpiresIn=_PRESIGNED_URL_EXPIRY_SECONDS,
    )
