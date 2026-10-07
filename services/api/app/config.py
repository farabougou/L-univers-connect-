from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    # Niveau des logs JSON (DEBUG, INFO, WARNING, ERROR), voir app/observability.
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://paios:paios_dev_password@localhost:5432/paios"

    # Fournisseur OpenID Connect (Keycloak, voir docs/adr/002). L'API ne fait
    # jamais confiance à un jeton sans vérifier sa signature auprès de
    # l'émetteur déclaré ici.
    oidc_issuer: str = "http://localhost:8080/realms/paios"
    oidc_audience: str = "paios-api"

    @field_validator("oidc_issuer")
    @classmethod
    def _oidc_issuer_has_scheme(cls, value: str) -> str:
        """Une adresse sans schéma (oubli fréquent en configuration manuelle)
        casse silencieusement la vérification des jetons : la requête vers le
        fournisseur OIDC échoue, ou pire, la comparaison avec le `iss` du
        jeton échoue sans message clair. On complète plutôt que de propager
        l'erreur plus loin."""
        return value if value.startswith(("http://", "https://")) else f"https://{value}"

    # Signature des jetons d'appareil Edge (M4, app/devices.py) : un flux
    # séparé de l'OIDC humain, jamais mélangé. À changer en production
    # (variable d'environnement), comme les autres secrets ci-dessous.
    device_token_secret: str = "dev-only-change-me-in-production"

    # Stockage des photos, compatible S3 (MinIO en local, voir docs/adr/006).
    # Changer de fournisseur en production ne demande que ces variables,
    # jamais une modification du code applicatif.
    storage_endpoint_url: str = "http://localhost:9000"
    storage_access_key: str = "paios-storage"
    storage_secret_key: str = "storage_dev_password"
    storage_bucket: str = "paios-photos"
    storage_region: str = "us-east-1"


settings = Settings()
