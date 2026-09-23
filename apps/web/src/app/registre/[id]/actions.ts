"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, requireAccessToken } from "@/lib/api";

type SignalKind = "alarm" | "finding";

function basePath(kind: SignalKind): string {
  return kind === "alarm" ? "/alarms" : "/findings";
}

function failureCode(problem: unknown): string {
  const code = (problem as { code?: unknown } | null)?.code;
  return typeof code === "string" ? code : "CREATION_FAILED";
}

async function redirectOnFailure(nodeId: string, response: Response): Promise<never> {
  const problem = await response.json().catch(() => null);
  redirect(`/registre/${nodeId}?error=${encodeURIComponent(failureCode(problem))}`);
}

export async function acknowledgeSignal(formData: FormData) {
  const accessToken = await requireAccessToken();
  const kind = formData.get("kind") as SignalKind;
  const signalId = formData.get("signal_id");
  const nodeId = String(formData.get("node_id"));

  const response = await apiFetch(`${basePath(kind)}/${signalId}/acknowledge`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function setHandling(formData: FormData) {
  const accessToken = await requireAccessToken();
  const kind = formData.get("kind") as SignalKind;
  const signalId = formData.get("signal_id");
  const nodeId = String(formData.get("node_id"));
  const handlingStatus = formData.get("handling_status");

  const response = await apiFetch(`${basePath(kind)}/${signalId}/handling`, accessToken, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handling_status: handlingStatus }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

/**
 * Retour à la normale déclaré par une personne : seulement pour les alarmes
 * (saisies à la main, aucune mesure ne peut le détecter) ; un constat se
 * dégage automatiquement quand la règle qui l'a soulevé revient à la
 * normale (voir app/rules.py, clear_finding_by_key), jamais manuellement.
 */
export async function clearAlarm(formData: FormData) {
  const accessToken = await requireAccessToken();
  const signalId = formData.get("signal_id");
  const nodeId = String(formData.get("node_id"));

  const response = await apiFetch(`/alarms/${signalId}/clear`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}
