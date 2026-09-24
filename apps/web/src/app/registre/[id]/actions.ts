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

/**
 * Confirmation d'un constat : seulement une personne (jamais un système), et
 * jamais pour une prédiction (l'API le refuse aussi, voir app/findings.py).
 */
export async function confirmFinding(formData: FormData) {
  const accessToken = await requireAccessToken();
  const signalId = formData.get("signal_id");
  const nodeId = String(formData.get("node_id"));

  const response = await apiFetch(`/findings/${signalId}/confirm`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: formData.get("note") }),
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

/**
 * Règle de détection déterministe (ADR 012 §2.15, F4) : une nouvelle version
 * naît en brouillon, sans effet tant qu'elle n'est pas activée séparément
 * (voir activateRule) — jamais de règle qui s'applique dès sa création.
 */
export async function createThresholdRule(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const pointId = String(formData.get("point_id"));
  const recommendedAction = formData.get("recommended_action");

  const response = await apiFetch("/configs", accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      config_type: "alarm_rule",
      subject_key: pointId,
      reason: formData.get("reason"),
      content: {
        kind: "threshold",
        point_id: pointId,
        severity: formData.get("severity"),
        title: formData.get("title"),
        recommended_action: recommendedAction || null,
        create_work_order: formData.get("create_work_order") === "on",
        operator: formData.get("operator"),
        threshold: Number(formData.get("threshold")),
      },
    }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function createDivergenceRule(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const pointId = String(formData.get("point_id"));
  const recommendedAction = formData.get("recommended_action");

  const response = await apiFetch("/configs", accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      config_type: "alarm_rule",
      subject_key: pointId,
      reason: formData.get("reason"),
      content: {
        kind: "desired_state_divergence",
        point_id: pointId,
        severity: formData.get("severity"),
        title: formData.get("title"),
        recommended_action: recommendedAction || null,
        create_work_order: formData.get("create_work_order") === "on",
        tolerance: Number(formData.get("tolerance")),
      },
    }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function activateRule(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const versionId = formData.get("version_id");

  const response = await apiFetch(`/configs/${versionId}/activate`, accessToken, {
    method: "POST",
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function restoreRule(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const versionId = formData.get("version_id");

  const response = await apiFetch(`/configs/${versionId}/restore`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: formData.get("reason") }),
  });
  if (!response.ok) {
    await redirectOnFailure(nodeId, response);
  }
  revalidatePath(`/registre/${nodeId}`);
}

export async function retireRule(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const versionId = formData.get("version_id");

  const response = await apiFetch(`/configs/${versionId}/retire`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: formData.get("reason") }),
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

/**
 * Connexion Modbus d'un équipement (ADR 012 §2.11-2.12), en configuration
 * versionnée comme les règles de détection : sujet = l'équipement. Une
 * nouvelle version naît en brouillon, sans effet tant qu'elle n'est pas
 * activée (voir activateRule, réutilisé ici — l'endpoint /configs ne dépend
 * pas du type de configuration).
 */
export async function createDeviceMapping(formData: FormData) {
  const accessToken = await requireAccessToken();
  const nodeId = String(formData.get("node_id"));
  const pointIds = String(formData.get("point_ids"))
    .split(",")
    .filter(Boolean);
  const points = pointIds
    .map((pointId) => ({
      point_id: pointId,
      register_name: formData.get(`register_${pointId}`),
    }))
    .filter((entry) => entry.register_name);

  const response = await apiFetch("/configs", accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      config_type: "modbus_device_mapping",
      subject_key: nodeId,
      reason: formData.get("reason"),
      content: {
        device_type: "sdm120",
        host: formData.get("host"),
        port: Number(formData.get("port")),
        points,
      },
    }),
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
