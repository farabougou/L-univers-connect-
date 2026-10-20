from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def build_engine(database_url: str) -> Engine:
    """`pool_pre_ping` vérifie une connexion avant de la prêter : une
    connexion coupée côté Postgres (redémarrage, bascule, délai d'inactivité
    d'un proxy réseau) est remplacée en silence au lieu de devenir une erreur
    500 pour la personne. Le contexte tenant (`app.current_tenant_id`) est
    local à la transaction (voir app/tenancy.py) : réutiliser ou remplacer une
    connexion du pool ne peut donc jamais faire passer un tenant à un autre."""
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
    )


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass
