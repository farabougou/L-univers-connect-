"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, requireAccessToken } from "@/lib/api";

function failureCode(problem: unknown): string {
  const code = (problem as { code?: unknown } | null)?.code;
  return typeof code === "string" ? code : "CREATION_FAILED";
}

async function redirectOnFailure(floorPlanId: string, response: Response): Promise<never> {
  const problem = await response.json().catch(() => null);
  redirect(`/registre/plans/${floorPlanId}?error=${encodeURIComponent(failureCode(problem))}`);
}

/**
 * Ajoute un repère (ADR 011, étape S4) depuis les coordonnées choisies en
 * cliquant sur le plan (PlacementEditor.tsx, seul composant client de cette
 * page) : exactement une cible (espace ou position fonctionnelle), jamais
 * les deux.
 */
export async function createPlacement(formData: FormData) {
  const accessToken = await requireAccessToken();
  const floorPlanId = String(formData.get("floor_plan_id"));
  const targetType = formData.get("target_type");
  const targetId = formData.get("target_id");

  const body: Record<string, unknown> = {
    x_ratio: Number(formData.get("x_ratio")),
    y_ratio: Number(formData.get("y_ratio")),
  };
  if (targetType === "space") {
    body.space_id = targetId;
  } else if (targetType === "functional_location") {
    body.functional_location_id = targetId;
  }

  const response = await apiFetch(`/floor-plans/${floorPlanId}/placements`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    await redirectOnFailure(floorPlanId, response);
  }

  revalidatePath(`/registre/plans/${floorPlanId}`);
  redirect(`/registre/plans/${floorPlanId}`);
}

export async function validatePlacement(formData: FormData) {
  const accessToken = await requireAccessToken();
  const floorPlanId = String(formData.get("floor_plan_id"));
  const placementId = formData.get("placement_id");

  const response = await apiFetch(`/placements/${placementId}/validate`, accessToken, {
    method: "POST",
  });
  if (!response.ok) {
    await redirectOnFailure(floorPlanId, response);
  }

  revalidatePath(`/registre/plans/${floorPlanId}`);
  redirect(`/registre/plans/${floorPlanId}`);
}

export async function deletePlacement(formData: FormData) {
  const accessToken = await requireAccessToken();
  const floorPlanId = String(formData.get("floor_plan_id"));
  const placementId = formData.get("placement_id");

  const response = await apiFetch(`/placements/${placementId}`, accessToken, {
    method: "DELETE",
  });
  if (!response.ok) {
    await redirectOnFailure(floorPlanId, response);
  }

  revalidatePath(`/registre/plans/${floorPlanId}`);
  redirect(`/registre/plans/${floorPlanId}`);
}
