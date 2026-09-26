import { NextResponse } from "next/server";

import { config } from "@/lib/config";
import { consumeOAuthFlowCookie, setTokensCookie } from "@/lib/session";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const error = url.searchParams.get("error");

  if (error) {
    return NextResponse.redirect(`${config.appUrl}/login?error=${encodeURIComponent(error)}`);
  }
  if (!code) {
    return NextResponse.redirect(`${config.appUrl}/login?error=code_manquant`);
  }

  const flow = await consumeOAuthFlowCookie();
  if (!flow) {
    return NextResponse.redirect(`${config.appUrl}/login?error=session_expiree`);
  }
  // Protection contre une CSRF de connexion : le "state" renvoyé par
  // Keycloak doit correspondre exactement à celui généré pour CE
  // navigateur au moment de la redirection (voir src/lib/pkce.ts).
  if (state !== flow.state) {
    return NextResponse.redirect(`${config.appUrl}/login?error=state_invalide`);
  }

  const tokenResponse = await fetch(`${config.oidcIssuer}/protocol/openid-connect/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.oidcClientId,
      redirect_uri: `${config.appUrl}/api/auth/callback`,
      code,
      code_verifier: flow.codeVerifier,
    }),
  });

  if (!tokenResponse.ok) {
    return NextResponse.redirect(`${config.appUrl}/login?error=echange_jeton`);
  }

  const data = (await tokenResponse.json()) as {
    access_token: string;
    refresh_token: string;
    expires_in: number;
  };
  await setTokensCookie({
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  });

  return NextResponse.redirect(config.appUrl);
}
