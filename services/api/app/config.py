from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    # Niveau des logs JSON (DEBUG, INFO, WARNING, ERROR), voir app/observability.
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://paios:paios_dev_password@localhost:5432/paios"

    # Pool de connexions Postgres (app/db.py). Les routes synchrones de
    # FastAPI s'exécutent dans un pool de fils (40 par défaut) : un pool de
    # connexions beaucoup plus petit ferait attendre les requêtes. Valeurs par
    # défaut prudentes (30 connexions au maximum par processus, loin des 100
    # d'un Postgres standard) ; à ajuster par variable d'environnement.
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 15
    # Recycle les connexions plus anciennes que cette durée, avant qu'un
    # proxy réseau intermédiaire ne les coupe de son côté.
    db_pool_recycle_seconds: int = 1800

    # Contrôle d'admission (app/admission.py) : requêtes HTTP traitées en même
    # temps par processus. 0 = la capacité du pool de connexions, ce qui rend
    # impossible l'attente d'une connexion (interblocage fils/connexions). Les
    # requêtes en trop patientent au plus ce délai, puis reçoivent un 503.
    max_in_flight_requests: int = 0
    admission_queue_timeout_seconds: float = 5.0

    # Capacité déclarée (app/capacity.py). Railway n'expose pas le nombre de
    # répliques à l'application : on le déclare ici pour que la vérification de
    # démarrage compte le total de connexions à la base de TOUTES les instances.
    expected_replicas: int = 1

    # Limitation de débit (app/rate_limit.py). `memory://` : compteurs propres à
    # chaque processus, exacts tant qu'il n'y a qu'un processus et une instance
    # (cas actuel). Au-delà, les quotas seraient multipliés par le nombre
    # d'instances : passer à un stockage partagé, par exemple `redis://...`
    # (voir infra/RAILWAY_STAGING.md).
    rate_limit_storage_uri: str = "memory://"
    # En-tête portant l'adresse réelle du client, posé et écrasé par le proxy de
    # l'hébergeur (Railway : `X-Real-IP`). Vide : on n'en lit aucun (défaut sûr,
    # un client pourrait sinon se fabriquer autant de quotas qu'il veut).
    client_ip_header: str = ""

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
