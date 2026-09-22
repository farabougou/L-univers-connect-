import { cookies } from "next/headers";

const ACCESS_TOKEN_COOKIE = "paios_access_token";
const OAUTH_FLOW_COOKIE = "paios_oauth_flow";

/**
 * Jeton d'accès Keycloak stocké dans un cookie httpOnly : jamais accessible
 * depuis le JavaScript du navigateur, jamais transmis à un autre site
 * (SameSite=lax). Ce serveur ne réémet pas son propre jeton de session :
 * le jeton Keycloak, déjà signé et vérifiable, sert directement de preuve
 * d'identité auprès de l'API (voir services/api/app/auth.py).
 */
export async function setAccessTokenCookie(accessToken: string, expiresInSeconds: number) {
  const cookieStore = await cookies();
  cookieStore.set(ACCESS_TOKEN_COOKIE, accessToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: expiresInSeconds,
  });
}

export async function getAccessTokenCookie(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(ACCESS_TOKEN_COOKIE)?.value ?? null;
}

export async function clearAccessTokenCookie() {
  const cookieStore = await cookies();
  cookieStore.delete(ACCESS_TOKEN_COOKIE);
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
