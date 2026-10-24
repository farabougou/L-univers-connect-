/**
 * Marge de sécurité avant l'expiration réelle du jeton : évite d'envoyer à
 * l'API un jeton qui expirerait pendant le trajet réseau (voir
 * getValidAccessToken dans session.ts).
 */
export const REFRESH_MARGIN_MS = 10_000;

/**
 * Isolé du reste de la logique de session (qui dépend de `next/headers`,
 * difficile à tester unitairement) pour que cette règle — la plus sujette
 * aux erreurs d'un rafraîchissement de jeton (décalages d'un cran) — soit
 * directement vérifiable (voir la règle non négociable 7 : tester en
 * premier tout ce qui touche au temps).
 */
export function isAccessTokenExpired(expiresAt: number, now: number = Date.now()): boolean {
  return now >= expiresAt - REFRESH_MARGIN_MS;
}
