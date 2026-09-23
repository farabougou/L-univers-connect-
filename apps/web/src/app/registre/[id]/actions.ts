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

export async function declareDesiredState(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const pointId = formData.get("point_id");
  const dailyStart = formData.get("daily_start");
  const dailyEnd = formData.get("daily_end");
  const timezone = formData.get("timezone");

  const response = await apiFetch(`/points/${pointId}/desired-states`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      value: Number(formData.get("value")),
      reason: formData.get("reason"),
      daily_start: dailyStart || null,
      daily_end: dailyEnd || null,
      timezone: timezone || null,
    }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function endDesiredState(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const desiredStateId = formData.get("desired_state_id");

  const response = await apiFetch(`/desired-states/${desiredStateId}/end`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function changeLifecycleState(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const unitId = formData.get("physical_unit_id");
  const note = formData.get("note");

  const response = await apiFetch(`/physical-units/${unitId}/lifecycle`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to_state: formData.get("to_state"), note: note || null }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function setAssetCode(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const unitId = formData.get("unit_id");

  const response = await apiFetch(`/physical-units/${unitId}/asset-code`, accessToken, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_code: formData.get("asset_code") }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function setProperty(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const unitId = formData.get("unit_id");
  const unitField = formData.get("unit");
  const rawValue = String(formData.get("value"));
  const numericValue = Number(rawValue);
  const value = rawValue.trim() !== "" && !Number.isNaN(numericValue) ? numericValue : rawValue;

  const response = await apiFetch(`/graph/nodes/${unitId}/properties`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      key: formData.get("key"),
      value,
      unit: unitField || null,
      source: formData.get("source"),
      reason: formData.get("reason"),
    }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function revokeTag(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const code = formData.get("code");

  const response = await apiFetch(`/tags/${code}/revoke`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: formData.get("reason") }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function createTagForEquipment(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));

  const response = await apiFetch(`/graph/nodes/${nodeId}/tags`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag_type: "qr" }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function createWorkOrderForEquipment(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));

  const response = await apiFetch("/work-orders", accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: formData.get("title"),
      work_order_type: formData.get("work_order_type"),
      priority: formData.get("priority"),
      functional_location_id: nodeId,
    }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}
