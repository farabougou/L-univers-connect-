/**
 * Variables d'environnement du serveur web. Ce fichier n'est jamais importé
 * côté navigateur (pas de préfixe NEXT_PUBLIC_) : ce sont des adresses
 * internes utilisées uniquement par le serveur Next.js pour parler à
 * Keycloak et à l'API.
 */

/**
 * Une adresse sans schéma (ex. `mon-service.up.railway.app`, oubli fréquent
 * en configuration manuelle) casse silencieusement l'échange OIDC : Keycloak
 * reçoit un `redirect_uri` invalide et refuse la connexion sans message
 * clair. On complète avec `https://` plutôt que de propager l'erreur plus
 * loin dans un flux difficile à déboguer.
 */
function withScheme(url: string): string {
  return /^https?:\/\//.test(url) ? url : `https://${url}`;
}

export const config = {
  oidcIssuer: withScheme(process.env.OIDC_ISSUER ?? "http://localhost:8080/realms/paios"),
  oidcClientId: process.env.OIDC_CLIENT_ID ?? "paios-api",
  apiUrl: withScheme(process.env.API_URL ?? "http://localhost:8000"),
  appUrl: withScheme(process.env.APP_URL ?? "http://localhost:3000"),
};
