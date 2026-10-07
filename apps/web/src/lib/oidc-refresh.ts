import { config } from "./config";

export type TokenSet = {
  accessToken: string;
  refreshToken: string;
  /** Horodatage epoch (ms) d'expiration du jeton d'accès. */
  expiresAt: number;
};

/**
 * Échange un jeton de rafraîchissement contre un nouveau jeu de jetons
 * auprès de Keycloak. Volontairement sans dépendance à `next/headers` : ce
 * même échange doit pouvoir être fait aussi bien depuis le middleware
 * (Edge runtime, écrit les cookies sur la réponse) que depuis un composant
 * serveur (session.ts, écrit les cookies via `cookies()`) — voir le
 * middleware pour pourquoi le rafraîchissement ne peut pas se faire dans un
 * composant serveur lui-même.
 */
export async function fetchRefreshedTokens(refreshToken: string): Promise<TokenSet | null> {
  const response = await fetch(`${config.oidcIssuer}/protocol/openid-connect/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      client_id: config.oidcClientId,
      refresh_token: refreshToken,
    }),
  });
  if (!response.ok) {
    return null;
  }
  const data = (await response.json()) as {
    access_token: string;
    refresh_token?: string;
    expires_in: number;
  };
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token ?? refreshToken,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
}
