"""Identité technique d'un appareil Edge (M4, ADR 012 §2.10).

Deux créances, une seule cible (décision de Mohamed du 24/09/2026) :

- `public_key_assertion` — **modèle cible**. L'appareil génère sa propre
  paire de clés (courbe P-256) ; seule la clé publique est enregistrée ici,
  la clé privée ne quitte jamais l'appareil, jamais transmise, jamais
  journalisée. À chaque authentification, l'appareil prouve qu'il détient
  la clé privée en signant une preuve courte (JWT ES256, RFC 7523) que le
  serveur vérifie avec la clé publique enregistrée — jamais l'inverse.
  HTTPS reste obligatoire (la signature complète TLS, elle ne le remplace
  pas) ; ce n'est pas du mTLS transport, faute de vérification de
  certificat client par l'hébergeur (voir le plan présenté à Mohamed) : la
  preuve se fait au niveau applicatif, avec les mêmes garanties
  d'authenticité et de non-répudiation.
- `shared_secret` — **compatibilité uniquement**, pour les appareils déjà
  provisionnés (ex. le simulateur SDM120). Jamais le modèle pour un
  nouveau matériel. Migré vers `public_key_assertion` via `set_public_key`,
  au rythme de l'exploitant — les deux coexistent tant que la migration
  n'est pas jugée terminée (décision séparée pour retirer `shared_secret`).

Le fondement ne change pas d'un modèle à l'autre : l'authentification d'un
appareil est la seule opération qui a lieu avant de connaître son tenant
avec certitude — l'appareil l'annonce, la connexion est positionnée dessus
(set_tenant_context) puis la recherche se fait sous RLS comme toute autre
requête. Un tenant_id mensonger ne trouve simplement aucune ligne. Jamais
de contournement de l'isolation (règle non négociable 2).

Anti-rejeu : une preuve signée n'est valable qu'une fois et pour une
fenêtre courte (`MAX_ASSERTION_TTL`) — `device_assertion_nonces` retient
les preuves déjà consommées le temps de leur validité, purgée à chaque
authentification (pas de tâche de fond de plus).

Cycle de vie déjà pris en charge par ce modèle, sans nouveau mécanisme :
révocation immédiate (`status`, vérifié à chaque authentification, quelle
que soit la créance), dernière authentification (`last_seen_at`), empreinte
de clé (`key_fingerprint`), rotation et migration (`set_public_key`,
auditées — voir app/routers/devices.py), historique des changements
d'identité (journal d'audit existant, action `device.public_key_set`).

Transition prévue vers PKI/mTLS complet (certificats gérés, autorité de
certification, rotation automatisée) sans changer ce concept d'identité ni
réécrire ce module : `credential_type` accueillera une troisième valeur le
moment venu, la vérification par clé publique enregistrée restant la même
brique de base (une PKI ne fait qu'automatiser la distribution et le
renouvellement des clés, pas leur vérification). Pas de mini-autorité de
certification construite maintenant : la maturité et le nombre d'appareils
ne le justifient pas encore (Mohamed, point 10).

Le statut de communication (online/offline/unknown) se calcule à la lecture
à partir de `last_seen_at`, jamais stocké (même principe que
app/equipment_status.py) : rien à réconcilier en double.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jose import jwt
from jose.exceptions import JOSEError
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.errors import DomainError

_COLUMNS = (
    "id, tenant_id, site_id, device_id, credential_type, status, created_by, created_at, "
    "last_seen_at, revoked_at, revoked_by, revoked_reason, key_fingerprint, key_rotated_at"
)

# Au-delà de ce délai sans relève, un appareil est considéré hors ligne
# plutôt qu'en ligne par supposition : pas de statut positif sans donnée
# récente, même esprit que la communication d'un équipement.
ONLINE_AFTER = timedelta(minutes=5)

# Algorithme de signature des preuves d'identité — fixé explicitement, comme
# pour le jeton d'appareil (app/auth.py) : jamais laisser une preuve dicter
# son propre algorithme de vérification (attaque classique "alg=none").
ASSERTION_ALGORITHM = "ES256"
ASSERTION_CURVE = ec.SECP256R1

# Plafond imposé par le serveur, jamais déduit de ce que l'appareil déclare
# dans sa preuve : une preuve dont l'écart exp - iat dépasse ce plafond est
# refusée, même si sa signature est valide.
MAX_ASSERTION_TTL = timedelta(seconds=60)
# Tolérance de décalage d'horloge entre l'appareil et le serveur.
CLOCK_SKEW = timedelta(seconds=30)


class DeviceConflict(DomainError, ValueError):
    status = 409


class DeviceNotFound(DomainError, LookupError):
    status = 404


class DeviceAuthInvalid(DomainError, ValueError):
    status = 401


class DevicePublicKeyInvalid(DomainError, ValueError):
    status = 422


def generate_secret() -> str:
    """256 bits aléatoires : jamais un mot de passe choisi, un secret émis.
    Compatibilité uniquement (`shared_secret`) — voir le module."""
    return secrets.token_urlsafe(32)


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _load_public_key(pem: str) -> ec.EllipticCurvePublicKey:
    """N'accepte qu'une clé publique EC sur la courbe P-256 : un algorithme
    standard éprouvé, jamais un protocole cryptographique maison."""
    try:
        key = serialization.load_pem_public_key(pem.encode("utf-8"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise DevicePublicKeyInvalid("DEVICE_PUBLIC_KEY_INVALID") from exc
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ASSERTION_CURVE):
        raise DevicePublicKeyInvalid("DEVICE_PUBLIC_KEY_INVALID")
    return key


def _fingerprint(key: ec.EllipticCurvePublicKey) -> str:
    der = key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return hashlib.sha256(der).hexdigest()


def provision_device(
    connection: Connection,
    *,
    tenant_id: uuid.UUID,
    device_id: str,
    created_by: str,
    site_id: uuid.UUID | None = None,
    public_key_pem: str | None = None,
) -> tuple[uuid.UUID, str | None]:
    """Crée un nouvel appareil.

    Avec `public_key_pem` (modèle cible) : la clé publique est enregistrée
    telle quelle, rien d'autre à renvoyer — la clé privée correspondante
    n'a jamais transité par le serveur. Sans `public_key_pem`
    (`shared_secret`, compatibilité) : renvoie (id, secret en clair), le
    secret n'étant jamais recalculable ensuite, à transmettre une seule
    fois."""
    existing = connection.execute(
        text("SELECT 1 FROM edge_devices WHERE tenant_id = :t AND device_id = :d"),
        {"t": tenant_id, "d": device_id},
    ).scalar()
    if existing:
        raise DeviceConflict("DEVICE_ID_ALREADY_USED", device_id=device_id)

    new_id = uuid.uuid4()
    if public_key_pem is not None:
        key = _load_public_key(public_key_pem)
        connection.execute(
            text(
                "INSERT INTO edge_devices (id, tenant_id, site_id, device_id, credential_type, "
                "public_key_pem, key_fingerprint, key_rotated_at, created_by) "
                "VALUES (:id, :tenant_id, :site_id, :device_id, 'public_key_assertion', "
                ":public_key_pem, :key_fingerprint, :at, :created_by)"
            ),
            {
                "id": new_id,
                "tenant_id": tenant_id,
                "site_id": site_id,
                "device_id": device_id,
                "public_key_pem": public_key_pem,
                "key_fingerprint": _fingerprint(key),
                "at": datetime.now(UTC),
                "created_by": created_by,
            },
        )
        return new_id, None

    secret = generate_secret()
    connection.execute(
        text(
            "INSERT INTO edge_devices (id, tenant_id, site_id, device_id, secret_hash, created_by) "
            "VALUES (:id, :tenant_id, :site_id, :device_id, :secret_hash, :created_by)"
        ),
        {
            "id": new_id,
            "tenant_id": tenant_id,
            "site_id": site_id,
            "device_id": device_id,
            "secret_hash": _hash_secret(secret),
            "created_by": created_by,
        },
    )
    return new_id, secret


def set_public_key(
    connection: Connection,
    *,
    device_id: uuid.UUID,
    public_key_pem: str,
    at: datetime,
) -> dict[str, Any]:
    """Installe une nouvelle clé publique pour un appareil déjà provisionné :
    première inscription (migration depuis `shared_secret`) ou rotation d'un
    appareil déjà à clé publique — même opération dans les deux cas.

    Toujours déclenchée par une personne autorisée et auditée (voir
    app/routers/devices.py, jamais par l'appareil lui-même) : la simple
    capacité d'enregistrer une clé publique ne doit pas permettre à un tiers
    de créer une identité d'appareil valide. Renvoie l'ancienne et la
    nouvelle empreinte, pour l'entrée d'audit (historique des changements
    d'identité — le journal d'audit existant suffit, pas de table de plus)."""
    key = _load_public_key(public_key_pem)
    new_fingerprint = _fingerprint(key)
    row = (
        connection.execute(
            text("SELECT key_fingerprint FROM edge_devices WHERE id = :id"), {"id": device_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise DeviceNotFound("DEVICE_NOT_FOUND")
    connection.execute(
        text(
            "UPDATE edge_devices SET credential_type = 'public_key_assertion', "
            "public_key_pem = :public_key_pem, key_fingerprint = :key_fingerprint, "
            "secret_hash = NULL, key_rotated_at = :at WHERE id = :id"
        ),
        {
            "public_key_pem": public_key_pem,
            "key_fingerprint": new_fingerprint,
            "at": at,
            "id": device_id,
        },
    )
    return {"old_fingerprint": row["key_fingerprint"], "new_fingerprint": new_fingerprint}


def authenticate_device(connection: Connection, *, device_id: str, secret: str) -> dict[str, Any]:
    """Vérifie l'appareil sous le tenant déjà positionné sur la connexion,
    par secret partagé (`shared_secret`, compatibilité — voir le module).

    Un tenant_id mensonger, un device_id inconnu ou un secret erroné donnent
    la même erreur générique : rien qui permette de deviner laquelle des
    trois raisons a joué."""
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS}, secret_hash FROM edge_devices WHERE device_id = :d"),
            {"d": device_id},
        )
        .mappings()
        .first()
    )
    if (
        row is None
        or row["secret_hash"] is None
        or not hmac.compare_digest(row["secret_hash"], _hash_secret(secret))
    ):
        raise DeviceAuthInvalid("DEVICE_AUTH_INVALID")
    if row["status"] != "active":
        raise DeviceAuthInvalid("DEVICE_AUTH_INVALID")
    return dict(row)


def authenticate_device_by_assertion(
    connection: Connection, *, device_id: str, assertion: str, at: datetime
) -> dict[str, Any]:
    """Vérifie l'appareil sous le tenant déjà positionné sur la connexion,
    par preuve cryptographique signée (`public_key_assertion`, modèle
    cible — voir le module) : un JWT court signé par la clé privée de
    l'appareil, vérifié ici avec sa clé publique enregistrée.

    Toutes les raisons de refus (appareil inconnu, mauvais type de créance,
    signature invalide, mauvaise clé, appareil révoqué, preuve expirée,
    preuve déjà utilisée) donnent la même erreur générique — même principe
    que `authenticate_device`."""
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS}, public_key_pem FROM edge_devices WHERE device_id = :d"),
            {"d": device_id},
        )
        .mappings()
        .first()
    )
    if (
        row is None
        or row["credential_type"] != "public_key_assertion"
        or row["public_key_pem"] is None
        or row["status"] != "active"
    ):
        raise DeviceAuthInvalid("DEVICE_AUTH_INVALID")

    try:
        # L'expiration est vérifiée nous-mêmes ci-dessous, contre `at` (jamais
        # l'horloge réelle du serveur) : seule la signature est demandée ici,
        # pour un résultat déterministe et testable comme le reste du module.
        claims = jwt.decode(
            assertion,
            row["public_key_pem"],
            algorithms=[ASSERTION_ALGORITHM],
            options={"verify_exp": False},
        )
    except JOSEError:
        raise DeviceAuthInvalid("DEVICE_AUTH_INVALID") from None

    if any(key not in claims for key in ("device_id", "tenant_id", "jti", "iat", "exp")):
        raise DeviceAuthInvalid("DEVICE_AUTH_INVALID")
    if claims["device_id"] != device_id:
        raise DeviceAuthInvalid("DEVICE_AUTH_INVALID")

    issued_at = datetime.fromtimestamp(claims["iat"], tz=UTC)
    expires_at = datetime.fromtimestamp(claims["exp"], tz=UTC)
    # Plafond imposé par le serveur (voir MAX_ASSERTION_TTL) : jamais confiance
    # dans la durée de validité que l'appareil s'attribuerait lui-même.
    if issued_at > at + CLOCK_SKEW or expires_at - issued_at > MAX_ASSERTION_TTL or at > expires_at:
        raise DeviceAuthInvalid("DEVICE_AUTH_INVALID")

    tenant_id = row["tenant_id"]
    # Purge des preuves expirées avant l'insertion : la table reste minuscule,
    # aucune tâche de fond de plus n'est nécessaire pour l'entretenir.
    connection.execute(
        text("DELETE FROM device_assertion_nonces WHERE tenant_id = :t AND expires_at < :now"),
        {"t": tenant_id, "now": at},
    )
    try:
        connection.execute(
            text(
                "INSERT INTO device_assertion_nonces (tenant_id, device_id, jti, expires_at) "
                "VALUES (:tenant_id, :device_id, :jti, :expires_at)"
            ),
            {
                "tenant_id": tenant_id,
                "device_id": row["id"],
                "jti": claims["jti"],
                "expires_at": expires_at,
            },
        )
    except IntegrityError:
        # Une clé (device_id, jti) déjà présente : preuve déjà consommée.
        raise DeviceAuthInvalid("DEVICE_AUTH_INVALID") from None

    return dict(row)


def touch_last_seen(connection: Connection, *, device_id: uuid.UUID, at: datetime) -> None:
    connection.execute(
        text("UPDATE edge_devices SET last_seen_at = :at WHERE id = :id"),
        {"at": at, "id": device_id},
    )


def revoke_device(
    connection: Connection, *, device_id: uuid.UUID, revoked_by: str, reason: str, at: datetime
) -> None:
    updated = connection.execute(
        text(
            "UPDATE edge_devices SET status = 'revoked', revoked_at = :at, revoked_by = :by, "
            "revoked_reason = :reason WHERE id = :id AND status = 'active'"
        ),
        {"at": at, "by": revoked_by, "reason": reason, "id": device_id},
    ).rowcount
    if not updated:
        raise DeviceConflict("DEVICE_ALREADY_REVOKED_OR_NOT_FOUND")


def get_device(connection: Connection, device_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"SELECT {_COLUMNS} FROM edge_devices WHERE id = :id"), {"id": device_id}
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_devices(connection: Connection) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(f"SELECT {_COLUMNS} FROM edge_devices ORDER BY created_at DESC")
        ).mappings()
    ]


def communication_status(device: dict[str, Any], *, now: datetime) -> str:
    """online si une relève a eu lieu récemment, offline si elle date trop,
    unknown si l'appareil n'a jamais donné signe de vie."""
    if device["last_seen_at"] is None:
        return "unknown"
    return "online" if now - device["last_seen_at"] <= ONLINE_AFTER else "offline"
