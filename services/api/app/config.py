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

    # Stockage des photos, compatible S3 (MinIO en local, voir docs/adr/006).
    # Changer de fournisseur en production ne demande que ces variables,
    # jamais une modification du code applicatif.
    storage_endpoint_url: str = "http://localhost:9000"
    storage_access_key: str = "paios-storage"
    storage_secret_key: str = "storage_dev_password"
    storage_bucket: str = "paios-photos"
    storage_region: str = "us-east-1"


settings = Settings()
