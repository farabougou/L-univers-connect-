import { NextResponse } from "next/server";

import { config } from "@/lib/config";
import { clearTokensCookie } from "@/lib/session";

export async function GET() {
  await clearTokensCookie();
  return NextResponse.redirect(`${config.appUrl}/login`);
}
