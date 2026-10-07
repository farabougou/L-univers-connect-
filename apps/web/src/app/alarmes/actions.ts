"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, requireAccessToken } from "@/lib/api";

/**
 * Mêmes actions que apps/web/src/app/registre/[id]/actions.ts, mais qui
 * reviennent sur /alarmes plutôt que sur la fiche d'un équipement précis :
 * cette page traite le portefeuille entier, jamais un seul actif. Dupliquées
 * plutôt que paramétrées pour ne jamais risquer de faire pointer par erreur
 * une redirection vers la mauvaise page (même principe que les fonctions
 * portefeuille de app/timeline.py côté API).
 */
type SignalKind = "alarm" | "finding";

function basePath(kind: SignalKind): string {
  return kind === "alarm" ? "/alarms" : "/findings";
}

function failureCode(problem: unknown): string {
  const code = (problem as { code?: unknown } | null)?.code;
  return typeof code === "string" ? code : "CREATION_FAILED";
}

async function redirectOnFailure(response: Response): Promise<never> {
  const problem = await response.json().catch(() => null);
  redirect(`/alarmes?error=${encodeURIComponent(failureCode(problem))}`);
}

export async function acknowledgeSignal(formData: FormData) {
  const accessToken = await requireAccessToken();
  const kind = formData.get("kind") as SignalKind;
  const signalId = formData.get("signal_id");

  const response = await apiFetch(`${basePath(kind)}/${signalId}/acknowledge`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/alarmes");
}

export async function confirmFinding(formData: FormData) {
  const accessToken = await requireAccessToken();
  const signalId = formData.get("signal_id");

  const response = await apiFetch(`/findings/${signalId}/confirm`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: formData.get("note") }),
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/alarmes");
}

export async function setHandling(formData: FormData) {
  const accessToken = await requireAccessToken();
  const kind = formData.get("kind") as SignalKind;
  const signalId = formData.get("signal_id");
  const handlingStatus = formData.get("handling_status");

  const response = await apiFetch(`${basePath(kind)}/${signalId}/handling`, accessToken, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handling_status: handlingStatus }),
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/alarmes");
}

export async function clearAlarm(formData: FormData) {
  const accessToken = await requireAccessToken();
  const signalId = formData.get("signal_id");

  const response = await apiFetch(`/alarms/${signalId}/clear`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/alarmes");
}
