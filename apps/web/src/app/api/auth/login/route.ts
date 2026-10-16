import { NextResponse } from "next/server";

import { config } from "@/lib/config";
import { generatePkcePair, generateState } from "@/lib/pkce";
import { setOAuthFlowCookie } from "@/lib/session";

export async function GET() {
  const { codeVerifier, codeChallenge } = generatePkcePair();
  const state = generateState();
  await setOAuthFlowCookie({ codeVerifier, state });

  const authUrl = new URL(`${config.oidcIssuer}/protocol/openid-connect/auth`);
  authUrl.searchParams.set("client_id", config.oidcClientId);
  authUrl.searchParams.set("redirect_uri", `${config.appUrl}/api/auth/callback`);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("scope", "openid profile");
  authUrl.searchParams.set("code_challenge", codeChallenge);
  authUrl.searchParams.set("code_challenge_method", "S256");
  authUrl.searchParams.set("state", state);

  return NextResponse.redirect(authUrl);
}
