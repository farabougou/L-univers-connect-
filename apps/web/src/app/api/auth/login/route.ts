import { NextResponse } from "next/server";

import { config } from "@/lib/config";
import { generatePkcePair } from "@/lib/pkce";
import { setPkceVerifierCookie } from "@/lib/session";

export async function GET() {
  const { codeVerifier, codeChallenge } = generatePkcePair();
  await setPkceVerifierCookie(codeVerifier);

  const authUrl = new URL(`${config.oidcIssuer}/protocol/openid-connect/auth`);
  authUrl.searchParams.set("client_id", config.oidcClientId);
  authUrl.searchParams.set("redirect_uri", `${config.appUrl}/api/auth/callback`);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("scope", "openid profile");
  authUrl.searchParams.set("code_challenge", codeChallenge);
  authUrl.searchParams.set("code_challenge_method", "S256");

  return NextResponse.redirect(authUrl);
}
