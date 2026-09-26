import { cookies } from "next/headers";

import { type TokenSet, fetchRefreshedTokens } from "./oidc-refresh";
import { isAccessTokenExpired } from "./token-expiry";

const TOKENS_COOKIE = "paios_tokens";
const OAUTH_FLOW_COOKIE = "paios_oauth_flow";

export type { TokenSet };

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

  if (!isAccessTokenExpired(tokens.expiresAt)) {
    return tokens.accessToken;
  }

  // Ce composant serveur ne peut pas écrire de cookie (Next.js l'interdit
  // hors Server Action / Route Handler / middleware) : le middleware
  // rafraîchit déjà le jeton avant que la page ne s'exécute, donc ce point ne
  // devrait normalement jamais être atteint avec un jeton expiré. S'il l'est
  // quand même (horloge limite entre le middleware et le rendu), on lit le
  // résultat sans écrire de cookie ici — la requête suivante sera rattrapée
  // par le middleware, ou l'utilisateur sera renvoyé se connecter si le
  // jeton de rafraîchissement est lui-même expiré.
  const refreshed = await fetchRefreshedTokens(tokens.refreshToken);
  return refreshed?.accessToken ?? null;
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
