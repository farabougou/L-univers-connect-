import { NextResponse } from "next/server";

import { config } from "@/lib/config";
import { consumePkceVerifierCookie, setAccessTokenCookie } from "@/lib/session";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const error = url.searchParams.get("error");

  if (error) {
    return NextResponse.redirect(`${config.appUrl}/login?error=${encodeURIComponent(error)}`);
  }
  if (!code) {
    return NextResponse.redirect(`${config.appUrl}/login?error=code_manquant`);
  }

  const codeVerifier = await consumePkceVerifierCookie();
  if (!codeVerifier) {
    return NextResponse.redirect(`${config.appUrl}/login?error=session_expiree`);
  }

  const tokenResponse = await fetch(`${config.oidcIssuer}/protocol/openid-connect/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.oidcClientId,
      redirect_uri: `${config.appUrl}/api/auth/callback`,
      code,
      code_verifier: codeVerifier,
    }),
  });

  if (!tokenResponse.ok) {
    return NextResponse.redirect(`${config.appUrl}/login?error=echange_jeton`);
  }

  const tokens = (await tokenResponse.json()) as { access_token: string; expires_in: number };
  await setAccessTokenCookie(tokens.access_token, tokens.expires_in);

  return NextResponse.redirect(config.appUrl);
}
