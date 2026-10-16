-- Rôle applicatif dédié, sans privilège superutilisateur.
--
-- PostgreSQL applique une règle absolue : Row Level Security ne s'applique
-- JAMAIS à un rôle superutilisateur, quelle que soit la politique définie.
-- L'image officielle postgres donne pourtant le statut superutilisateur au
-- rôle défini par POSTGRES_USER. On garde donc "postgres" comme compte
-- d'administration (utilisé uniquement à l'initialisation), et on crée ici
-- un rôle applicatif "paios" normal, propriétaire de la base de données,
-- avec lequel l'API se connecte réellement.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'paios') THEN
        CREATE ROLE paios LOGIN PASSWORD 'paios_dev_password';
    END IF;
END
$$;

ALTER DATABASE paios OWNER TO paios;
GRANT ALL PRIVILEGES ON DATABASE paios TO paios;
