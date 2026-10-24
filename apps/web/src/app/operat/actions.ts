"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, requireAccessToken } from "@/lib/api";

function failureCode(problem: unknown): string {
  const code = (problem as { code?: unknown } | null)?.code;
  return typeof code === "string" ? code : "CREATION_FAILED";
}

async function redirectOnFailure(response: Response, to: string): Promise<never> {
  const problem = await response.json().catch(() => null);
  redirect(`${to}?error=${encodeURIComponent(failureCode(problem))}`);
}

/**
 * Crée un brouillon de déclaration OPERAT pour un site et une année de
 * référence (`POST /sites/{site_id}/operat-declarations`, app.regulatory.operat).
 */
export async function createOperatDeclaration(formData: FormData) {
  const accessToken = await requireAccessToken();
  const siteId = formData.get("site_id");
  const referenceYear = Number(formData.get("reference_year"));

  const response = await apiFetch(`/sites/${siteId}/operat-declarations`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reference_year: referenceYear }),
  });
  if (!response.ok) {
    await redirectOnFailure(response, "/operat");
  }
  revalidatePath("/operat");
}

/** Remplace l'ensemble des champs modifiables (PUT, pas une fusion partielle
 * — voir app/schemas.py::OperatDeclarationUpdate) ; un champ laissé vide
 * côté formulaire efface la valeur existante, comme un formulaire qui
 * renvoie son état complet. */
export async function updateOperatDeclaration(formData: FormData) {
  const accessToken = await requireAccessToken();
  const declarationId = formData.get("declaration_id");
  const numberOrNull = (name: string) => {
    const value = formData.get(name);
    return value && String(value).trim() !== "" ? Number(value) : null;
  };
  const textOrNull = (name: string) => {
    const value = formData.get(name);
    return value && String(value).trim() !== "" ? String(value).trim() : null;
  };

  const response = await apiFetch(`/operat-declarations/${declarationId}`, accessToken, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      floor_area_m2: numberOrNull("floor_area_m2"),
      activity_category: textOrNull("activity_category"),
      electricity_kwh: numberOrNull("electricity_kwh"),
      gas_kwh: numberOrNull("gas_kwh"),
      heat_network_kwh: numberOrNull("heat_network_kwh"),
      other_kwh: numberOrNull("other_kwh"),
      other_label: textOrNull("other_label"),
      notes: textOrNull("notes"),
    }),
  });
  if (!response.ok) {
    await redirectOnFailure(response, `/operat/${declarationId}`);
  }
  revalidatePath(`/operat/${declarationId}`);
  revalidatePath("/operat");
}

export async function markOperatDeclarationReady(formData: FormData) {
  const accessToken = await requireAccessToken();
  const declarationId = formData.get("declaration_id");

  const response = await apiFetch(
    `/operat-declarations/${declarationId}/mark-ready`,
    accessToken,
    { method: "POST" },
  );
  if (!response.ok) {
    await redirectOnFailure(response, `/operat/${declarationId}`);
  }
  revalidatePath(`/operat/${declarationId}`);
  revalidatePath("/operat");
}

/** Enregistre qu'une personne a transmis la déclaration sur le portail
 * OPERAT — aucune transmission automatique (app.regulatory.operat). */
export async function recordOperatSubmission(formData: FormData) {
  const accessToken = await requireAccessToken();
  const declarationId = formData.get("declaration_id");
  const submissionReference = formData.get("submission_reference");

  const response = await apiFetch(
    `/operat-declarations/${declarationId}/submissions`,
    accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        submission_reference:
          submissionReference && String(submissionReference).trim() !== ""
            ? String(submissionReference).trim()
            : null,
      }),
    },
  );
  if (!response.ok) {
    await redirectOnFailure(response, `/operat/${declarationId}`);
  }
  revalidatePath(`/operat/${declarationId}`);
  revalidatePath("/operat");
}
