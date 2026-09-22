import { cookies } from "next/headers";

import { config } from "./config";

const TOKENS_COOKIE = "paios_tokens";
const OAUTH_FLOW_COOKIE = "paios_oauth_flow";

export type TokenSet = {
  accessToken: string;
  refreshToken: string;
  /** Horodatage epoch (ms) d'expiration du jeton d'accès. */
  expiresAt: number;
};

/**
 * Jeux de jetons Keycloak stockés dans un cookie httpOnly : jamais
 * accessibles depuis le JavaScript du navigateur. Le jeton d'accès expire
 * rapidement (quelques minutes, réglage par défaut de Keycloak) ; c'est le
 * jeton de rafraîchissement, plus long à vivre, qui permet de rester
 * connecté sans redemander un mot de passe (voir getValidAccessToken).
 */
export async function setTokensCookie(tokens: TokenSet) {
  const cookieStore = await cookies();
  cookieStore.set(TOKENS_COOKIE, JSON.stringify(tokens), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
}

async function getTokensCookie(): Promise<TokenSet | null> {
  const cookieStore = await cookies();
  const raw = cookieStore.get(TOKENS_COOKIE)?.value;
  if (!raw) return null;
  try {
    return JSON.parse(raw) as TokenSet;
  } catch {
    return null;
  }
}

export async function clearTokensCookie() {
  const cookieStore = await cookies();
  cookieStore.delete(TOKENS_COOKIE);
}

/**
 * Renvoie un jeton d'accès garanti valide, en le rafraîchissant
 * silencieusement auprès de Keycloak s'il est expiré ou proche de
 * l'expiration. Renvoie `null` seulement si aucune session n'existe ou si
 * le rafraîchissement échoue (jeton de rafraîchissement lui-même expiré ou
 * révoqué) — dans ce cas la session locale est aussi effacée.
 */
export async function getValidAccessToken(): Promise<string | null> {
  const tokens = await getTokensCookie();
  if (!tokens) return null;

  // Marge de 10 secondes pour ne jamais envoyer à l'API un jeton qui
  // expirerait pendant le trajet réseau.
  if (Date.now() < tokens.expiresAt - 10_000) {
    return tokens.accessToken;
  }

  const refreshed = await refreshTokens(tokens.refreshToken);
  if (!refreshed) {
    await clearTokensCookie();
    return null;
  }
  return refreshed.accessToken;
}

async function refreshTokens(refreshToken: string): Promise<TokenSet | null> {
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
  const tokens: TokenSet = {
    accessToken: data.access_token,
    refreshToken: data.refresh_token ?? refreshToken,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
  await setTokensCookie(tokens);
  return tokens;
}

export type OAuthFlow = {
  codeVerifier: string;
  state: string;
};

/**
 * Le "code verifier" PKCE et le "state" anti-CSRF ne doivent vivre que le
 * temps de l'aller-retour vers Keycloak (quelques secondes à quelques
 * minutes) : jamais stockés plus longtemps, jamais réutilisés pour une
 * autre connexion.
 */
export async function setOAuthFlowCookie(flow: OAuthFlow) {
  const cookieStore = await cookies();
  cookieStore.set(OAUTH_FLOW_COOKIE, JSON.stringify(flow), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 300,
  });
}

export async function consumeOAuthFlowCookie(): Promise<OAuthFlow | null> {
  const cookieStore = await cookies();
  const raw = cookieStore.get(OAUTH_FLOW_COOKIE)?.value;
  cookieStore.delete(OAUTH_FLOW_COOKIE);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as OAuthFlow;
  } catch {
    return null;
  }
}
