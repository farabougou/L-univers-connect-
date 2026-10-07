"use server";

import { createHash } from "node:crypto";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, requireAccessToken } from "@/lib/api";

function failureCode(problem: unknown): string {
  const code = (problem as { code?: unknown } | null)?.code;
  return typeof code === "string" ? code : "CREATION_FAILED";
}

async function redirectOnFailure(response: Response): Promise<never> {
  const problem = await response.json().catch(() => null);
  redirect(`/documents?error=${encodeURIComponent(failureCode(problem))}`);
}

/**
 * Envoi d'un document d'équipement (section 36, point 10) : même dance en
 * deux temps que les plans 2D (app/registre/actions.ts::uploadFloorPlan) —
 * URL présignée puis envoi direct au stockage, empreinte SHA-256 calculée
 * ici sur les octets réellement envoyés.
 */
export async function uploadDocument(formData: FormData) {
  const accessToken = await requireAccessToken();
  const functionalLocationId = formData.get("functional_location_id");
  const category = formData.get("category");
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    redirect("/documents?error=CREATION_FAILED");
  }

  const uploadUrlResponse = await apiFetch(
    `/functional-locations/${functionalLocationId}/documents/upload-url`,
    accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, content_type: file.type }),
    },
  );
  if (!uploadUrlResponse.ok) {
    await redirectOnFailure(uploadUrlResponse);
  }
  const { upload_url: uploadUrl, object_key: objectKey } = await uploadUrlResponse.json();

  const bytes = await file.arrayBuffer();
  const putResponse = await fetch(uploadUrl, {
    method: "PUT",
    body: bytes,
    headers: { "Content-Type": file.type },
  });
  if (!putResponse.ok) {
    redirect("/documents?error=CREATION_FAILED");
  }

  const sha256 = createHash("sha256").update(Buffer.from(bytes)).digest("hex");
  const createResponse = await apiFetch(
    `/functional-locations/${functionalLocationId}/documents`,
    accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category,
        object_key: objectKey,
        filename: file.name,
        content_type: file.type,
        sha256,
      }),
    },
  );
  if (!createResponse.ok) {
    await redirectOnFailure(createResponse);
  }

  revalidatePath("/documents");
  redirect("/documents");
}
