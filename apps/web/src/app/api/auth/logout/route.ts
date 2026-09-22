import { NextResponse } from "next/server";

import { config } from "@/lib/config";
import { clearAccessTokenCookie } from "@/lib/session";

export async function GET() {
  await clearAccessTokenCookie();
  return NextResponse.redirect(`${config.appUrl}/login`);
}
