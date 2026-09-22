/**
 * Variables d'environnement du serveur web. Ce fichier n'est jamais importé
 * côté navigateur (pas de préfixe NEXT_PUBLIC_) : ce sont des adresses
 * internes utilisées uniquement par le serveur Next.js pour parler à
 * Keycloak et à l'API.
 */
export const config = {
  oidcIssuer: process.env.OIDC_ISSUER ?? "http://localhost:8080/realms/paios",
  oidcClientId: process.env.OIDC_CLIENT_ID ?? "paios-api",
  apiUrl: process.env.API_URL ?? "http://localhost:8000",
  appUrl: process.env.APP_URL ?? "http://localhost:3000",
};
