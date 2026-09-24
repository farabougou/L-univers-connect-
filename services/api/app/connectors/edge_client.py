"""Client HTTP de l'agent Edge vers l'API (M4) : la seule façon dont un
appareil parle au backend, jamais un accès direct à la base de données
(voir app/routers/devices.py, app/devices.py).

Le jeton d'appareil est renouvelé automatiquement avant son expiration, et
une seule fois de plus sur un 401 inattendu (jeton révoqué, horloge
décalée) — jamais une boucle de nouvelles tentatives.
"""

import time
import uuid
from typing import Any

import httpx

_TOKEN_REFRESH_MARGIN_SECONDS = 30


class EdgeApiClient:
    def __init__(
        self, *, client: httpx.Client, tenant_id: uuid.UUID, device_id: str, secret: str
    ) -> None:
        self.tenant_id = tenant_id
        self._client = client
        self._device_id = device_id
        self._secret = secret
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
                "secret": self._secret,
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

    def post_measurements(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        response = self._authorized_request("POST", "/edge/measurements", json={"items": items})
        return response.json()
