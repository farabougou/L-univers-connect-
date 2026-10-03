"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, requireAccessToken } from "@/lib/api";

function failureCode(problem: unknown): string {
  const code = (problem as { code?: unknown } | null)?.code;
  return typeof code === "string" ? code : "CREATION_FAILED";
}

async function redirectOnFailure(response: Response): Promise<never> {
  const problem = await response.json().catch(() => null);
  redirect(`/automation?error=${encodeURIComponent(failureCode(problem))}`);
}

/**
 * Même appel que endDesiredState (app/registre/[id]/actions.ts), mais avec
 * une cible de retour propre à cette page portefeuille — patron déjà établi
 * (chaque page garde ses propres actions plutôt que de partager un fichier
 * couplé à une autre page).
 */
export async function endDesiredState(formData: FormData) {
  const accessToken = await requireAccessToken();
  const desiredStateId = formData.get("desired_state_id");

  const response = await apiFetch(
    `/desired-states/${desiredStateId}/end`,
    accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/automation");
}
