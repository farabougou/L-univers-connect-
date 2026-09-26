/**
 * Variables d'environnement de l'application mobile. Les valeurs `EXPO_PUBLIC_*`
 * sont intégrées à l'application au moment de sa construction (voir Expo) et ne
 * sont donc jamais secrètes : elles servent uniquement à pointer vers le bon
 * serveur, pas à authentifier l'application elle-même.
 *
 * Depuis un téléphone physique, "localhost" désigne le téléphone lui-même, pas
 * l'ordinateur qui fait tourner Keycloak et l'API : utiliser l'adresse IP de
 * l'ordinateur sur le réseau local (voir apps/mobile/README.md).
 */
/**
 * Une adresse sans schéma (oubli fréquent en configuration manuelle du
 * fichier `.env`) casse silencieusement l'échange OIDC ou les appels API.
 * On complète avec `https://` plutôt que de propager l'erreur plus loin.
 */
function withScheme(url: string): string {
  return /^https?:\/\//.test(url) ? url : `https://${url}`;
}

export const config = {
  oidcIssuer: withScheme(
    process.env.EXPO_PUBLIC_OIDC_ISSUER ?? "http://localhost:8080/realms/paios",
  ),
  oidcClientId: process.env.EXPO_PUBLIC_OIDC_CLIENT_ID ?? "paios-api",
  apiUrl: withScheme(
    process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000",
  ),
};
