"""Client HTTP de l'agent Edge vers l'API (M4) : la seule façon dont un
appareil parle au backend, jamais un accès direct à la base de données
(voir app/routers/devices.py, app/devices.py).

Le jeton d'appareil est renouvelé automatiquement avant son expiration, et
une seule fois de plus sur un 401 inattendu (jeton révoqué, horloge
décalée) — jamais une boucle de nouvelles tentatives.

Deux façons de prouver son identité à `/devices/auth` (voir app/devices.py
pour le détail du modèle) : `SharedSecretCredential` (compatibilité
uniquement, à ne plus utiliser pour du nouveau matériel) ou
`PrivateKeyCredential` (modèle cible — la clé privée ne quitte jamais ce
processus, jamais transmise, jamais journalisée ; seule une preuve signée
courte, à usage unique, est envoyée).
"""

import time
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from jose import jwt

from app.devices import ASSERTION_ALGORITHM, MAX_ASSERTION_TTL

_TOKEN_REFRESH_MARGIN_SECONDS = 30


class DeviceCredential(Protocol):
    def auth_payload(self) -> dict[str, Any]:
        """Le contenu à ajouter au corps de POST /devices/auth."""
        ...


class SharedSecretCredential:
    """Compatibilité uniquement (voir app/devices.py) : à ne plus utiliser
    pour du nouveau matériel."""

    def __init__(self, secret: str) -> None:
        self._secret = secret

    def auth_payload(self) -> dict[str, Any]:
        return {"secret": self._secret}


class PrivateKeyCredential:
    """Modèle cible : une nouvelle preuve signée à chaque authentification,
    jamais réutilisée (voir la protection contre le rejeu côté serveur,
    `device_assertion_nonces`). La clé privée reste en mémoire de ce
    processus le temps de signer, jamais journalisée ni transmise."""

    def __init__(self, *, private_key_pem: str, device_id: str, tenant_id: uuid.UUID) -> None:
        self._private_key_pem = private_key_pem
        self._device_id = device_id
        self._tenant_id = tenant_id

    def auth_payload(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        claims = {
            "device_id": self._device_id,
            "tenant_id": str(self._tenant_id),
            "jti": uuid.uuid4().hex,
            "iat": int(now.timestamp()),
            "exp": int((now + MAX_ASSERTION_TTL).timestamp()),
        }
        assertion = jwt.encode(claims, self._private_key_pem, algorithm=ASSERTION_ALGORITHM)
        return {"assertion": assertion}


class EdgeApiClient:
    def __init__(
        self,
        *,
        client: httpx.Client,
        tenant_id: uuid.UUID,
        device_id: str,
        secret: str | None = None,
        credential: DeviceCredential | None = None,
    ) -> None:
        if (secret is None) == (credential is None):
            raise ValueError("indiquer exactement un de secret ou credential")
        self.tenant_id = tenant_id
        self._client = client
        self._device_id = device_id
        self._credential = credential or SharedSecretCredential(secret)
        self._token: str | None = None
        self._token_expires_at = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "EdgeApiClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _authenticate(self) -> None:
        response = self._client.post(
            "/devices/auth",
            json={
                "tenant_id": str(self.tenant_id),
                "device_id": self._device_id,
                **self._credential.auth_payload(),
            },
        )
        response.raise_for_status()
        body = response.json()
        self._token = body["access_token"]
        self._token_expires_at = (
            time.monotonic() + body["expires_in"] - _TOKEN_REFRESH_MARGIN_SECONDS
        )

    def _authorized_request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._token is None or time.monotonic() >= self._token_expires_at:
            self._authenticate()
        response = self._client.request(
            method, path, headers={"Authorization": f"Bearer {self._token}"}, **kwargs
        )
        if response.status_code == 401:
            self._authenticate()
            response = self._client.request(
                method, path, headers={"Authorization": f"Bearer {self._token}"}, **kwargs
            )
        response.raise_for_status()
        return response

    def get_config(self, equipment_id: uuid.UUID) -> dict[str, Any] | None:
        """None si aucune configuration n'est active pour cet équipement."""
        try:
            response = self._authorized_request(
                "GET", "/edge/config", params={"equipment_id": str(equipment_id)}
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        return response.json()

    def get_bacnet_config(self, equipment_id: uuid.UUID) -> dict[str, Any] | None:
        """Même principe que get_config, pour un équipement relevé par
        BACnet plutôt que Modbus (voir GET /edge/config/bacnet)."""
        try:
            response = self._authorized_request(
                "GET", "/edge/config/bacnet", params={"equipment_id": str(equipment_id)}
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        return response.json()

    def post_measurements(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        response = self._authorized_request("POST", "/edge/measurements", json={"items": items})
        return response.json()

    def get_pending_commands(self, equipment_id: uuid.UUID) -> list[dict[str, Any]]:
        """Récupère (et marque « sent » côté API) les commandes en attente
        pour cet équipement — jamais renvoyées une seconde fois."""
        response = self._authorized_request(
            "GET", "/edge/commands", params={"equipment_id": str(equipment_id)}
        )
        return response.json()

    def acknowledge_command(
        self,
        command_id: uuid.UUID,
        *,
        success: bool,
        actual_value: float | None,
        failure_reason: str | None,
    ) -> dict[str, Any]:
        response = self._authorized_request(
            "POST",
            f"/edge/commands/{command_id}/ack",
            json={
                "success": success,
                "actual_value": actual_value,
                "failure_reason": failure_reason,
            },
        )
        return response.json()
