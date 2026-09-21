from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://paios:paios_dev_password@localhost:5432/paios"

    # Fournisseur OpenID Connect (Keycloak, voir docs/adr/002). L'API ne fait
    # jamais confiance à un jeton sans vérifier sa signature auprès de
    # l'émetteur déclaré ici.
    oidc_issuer: str = "http://localhost:8080/realms/paios"
    oidc_audience: str = "paios-api"


settings = Settings()
