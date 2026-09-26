import { NextResponse, type NextRequest } from "next/server";

import { fetchRefreshedTokens, type TokenSet } from "@/lib/oidc-refresh";
import { isAccessTokenExpired } from "@/lib/token-expiry";

const TOKENS_COOKIE = "paios_tokens";

/**
 * Un composant serveur (ex. app/registre/page.tsx) ne peut pas écrire de
 * cookie : Next.js l'interdit hors Server Action / Route Handler /
 * middleware. Comme lire un jeton d'accès expiré déclenche justement une
 * écriture de cookie (le rafraîchissement), on le fait ici, avant que la
 * page ne s'exécute, pour que les composants serveur ne trouvent jamais un
 * jeton expiré.
 */
export async function proxy(request: NextRequest) {
  const raw = request.cookies.get(TOKENS_COOKIE)?.value;
  if (!raw) {
    return NextResponse.next();
  }

  let tokens: TokenSet;
  try {
    tokens = JSON.parse(raw) as TokenSet;
  } catch {
    return NextResponse.next();
  }

  if (!isAccessTokenExpired(tokens.expiresAt)) {
    return NextResponse.next();
  }

  const refreshed = await fetchRefreshedTokens(tokens.refreshToken);
  if (!refreshed) {
    const response = NextResponse.next();
    response.cookies.delete(TOKENS_COOKIE);
    return response;
  }

  request.cookies.set(TOKENS_COOKIE, JSON.stringify(refreshed));
  const response = NextResponse.next({ request });
  response.cookies.set(TOKENS_COOKIE, JSON.stringify(refreshed), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return response;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
