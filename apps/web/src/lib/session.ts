import { cookies } from "next/headers";

const ACCESS_TOKEN_COOKIE = "paios_access_token";
const PKCE_VERIFIER_COOKIE = "paios_pkce_verifier";

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

/**
 * Le "code verifier" PKCE ne doit vivre que le temps de l'aller-retour vers
 * Keycloak (quelques secondes à quelques minutes) : jamais stocké plus
 * longtemps, jamais réutilisé pour une autre connexion.
 */
export async function setPkceVerifierCookie(codeVerifier: string) {
  const cookieStore = await cookies();
  cookieStore.set(PKCE_VERIFIER_COOKIE, codeVerifier, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 300,
  });
}

export async function consumePkceVerifierCookie(): Promise<string | null> {
  const cookieStore = await cookies();
  const value = cookieStore.get(PKCE_VERIFIER_COOKIE)?.value ?? null;
  cookieStore.delete(PKCE_VERIFIER_COOKIE);
  return value;
}
