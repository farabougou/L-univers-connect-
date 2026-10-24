"use server";

import { redirect } from "next/navigation";

import { apiFetch, requireAccessToken } from "@/lib/api";
import { parseTagCode } from "@/lib/tagLookup";

function failureCode(problem: unknown): string {
  const code = (problem as { code?: unknown } | null)?.code;
  return typeof code === "string" ? code : "TAG_UNKNOWN";
}

/**
 * Résout une étiquette (code tapé à la main ou décodé d'un QR par la
 * caméra, voir QrScanner.tsx) et mène directement à la fiche équipement
 * déjà existante (`/registre/[id]`, qui affiche le même passeport que
 * `GET /graph/nodes/{id}/passport` côté mobile) — jamais une deuxième vue
 * passeport dupliquée côté web.
 */
export async function lookupTag(formData: FormData) {
  const raw = String(formData.get("code") ?? "");
  const code = parseTagCode(raw);
  if (!code) {
    redirect("/passeport?error=TAG_INVALID_CODE");
  }

  const accessToken = await requireAccessToken();
  const response = await apiFetch(`/tags/${code}`, accessToken);
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    redirect(`/passeport?error=${encodeURIComponent(failureCode(problem))}`);
  }

  const body = await response.json();
  redirect(`/registre/${body.tag.node_id}`);
}
