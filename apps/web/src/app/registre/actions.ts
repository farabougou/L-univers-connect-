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
  redirect(`/registre?error=${encodeURIComponent(failureCode(problem))}`);
}

export async function createSite(formData: FormData) {
  const accessToken = await requireAccessToken();
  const response = await apiFetch("/sites", accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: formData.get("name"),
      timezone: formData.get("timezone"),
    }),
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/registre");
}

export async function createSpace(formData: FormData) {
  const accessToken = await requireAccessToken();
  const parentId = formData.get("parent_id");
  const response = await apiFetch("/spaces", accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      site_id: formData.get("site_id"),
      parent_id: parentId ? parentId : null,
      space_type: formData.get("space_type"),
      code: formData.get("code"),
      name: formData.get("name"),
    }),
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/registre");
}

export async function closeSpace(formData: FormData) {
  const accessToken = await requireAccessToken();
  const spaceId = formData.get("space_id");
  const response = await apiFetch(`/spaces/${spaceId}/close`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: formData.get("reason") }),
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/registre");
}

export async function updateSiteTimezone(formData: FormData) {
  const accessToken = await requireAccessToken();
  const siteId = formData.get("site_id");
  const response = await apiFetch(`/sites/${siteId}/timezone`, accessToken, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ timezone: formData.get("timezone") }),
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/registre");
}

/**
 * Archiver masque un site des listes par défaut sans rien supprimer :
 * jamais de suppression réelle (CLAUDE.md, règle non négociable 3 — rien
 * n'est écrasé). Réversible via unarchiveSite.
 */
export async function archiveSite(formData: FormData) {
  const accessToken = await requireAccessToken();
  const siteId = formData.get("site_id");
  const response = await apiFetch(`/sites/${siteId}/archive`, accessToken, { method: "POST" });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/registre");
}

export async function unarchiveSite(formData: FormData) {
  const accessToken = await requireAccessToken();
  const siteId = formData.get("site_id");
  const response = await apiFetch(`/sites/${siteId}/unarchive`, accessToken, { method: "POST" });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/registre");
}

/** Même principe que archiveSite, pour un équipement (position fonctionnelle). */
export async function archiveEquipment(formData: FormData) {
  const accessToken = await requireAccessToken();
  const locationId = formData.get("functional_location_id");
  const response = await apiFetch(`/functional-locations/${locationId}/archive`, accessToken, {
    method: "POST",
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/registre");
}

export async function unarchiveEquipment(formData: FormData) {
  const accessToken = await requireAccessToken();
  const locationId = formData.get("functional_location_id");
  const response = await apiFetch(`/functional-locations/${locationId}/unarchive`, accessToken, {
    method: "POST",
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/registre");
}

/**
 * Un équipement suppose quatre ressources liées (modèle, exemplaire,
 * emplacement fonctionnel, affectation) : cette action les crée dans
 * l'ordre, puis mint l'étiquette du nouvel équipement directement, pour que
 * la personne reparte avec un QR prêt à imprimer sans étape supplémentaire.
 */
export async function createEquipment(formData: FormData) {
  const accessToken = await requireAccessToken();
  const json = { "Content-Type": "application/json" };

  const modelResponse = await apiFetch("/product-models", accessToken, {
    method: "POST",
    headers: json,
    body: JSON.stringify({
      manufacturer: formData.get("manufacturer"),
      reference: formData.get("reference"),
      equipment_type: formData.get("equipment_type"),
    }),
  });
  if (!modelResponse.ok) {
    await redirectOnFailure(modelResponse);
  }
  const model = await modelResponse.json();

  const unitResponse = await apiFetch("/physical-units", accessToken, {
    method: "POST",
    headers: json,
    body: JSON.stringify({
      product_model_id: model.id,
      serial_number: formData.get("serial_number"),
    }),
  });
  if (!unitResponse.ok) {
    await redirectOnFailure(unitResponse);
  }
  const unit = await unitResponse.json();

  const spaceId = formData.get("space_id");
  const locationResponse = await apiFetch("/functional-locations", accessToken, {
    method: "POST",
    headers: json,
    body: JSON.stringify({
      site_id: formData.get("site_id"),
      code: formData.get("code"),
      name: formData.get("name"),
      kind: "equipment",
      space_id: spaceId ? spaceId : null,
    }),
  });
  if (!locationResponse.ok) {
    await redirectOnFailure(locationResponse);
  }
  const location = await locationResponse.json();

  const assignmentResponse = await apiFetch(
    `/functional-locations/${location.id}/assignment`,
    accessToken,
    { method: "POST", headers: json, body: JSON.stringify({ physical_unit_id: unit.id }) },
  );
  if (!assignmentResponse.ok) {
    await redirectOnFailure(assignmentResponse);
  }

  const tagResponse = await apiFetch(`/graph/nodes/${location.id}/tags`, accessToken, {
    method: "POST",
    headers: json,
    body: JSON.stringify({ tag_type: "qr" }),
  });
  if (!tagResponse.ok) {
    await redirectOnFailure(tagResponse);
  }
  const tag = await tagResponse.json();

  revalidatePath("/registre");
  redirect(
    `/registre?tag=${encodeURIComponent(tag.payload)}&label=${encodeURIComponent(location.name)}`,
  );
}

/**
 * Étiquette d'un équipement déjà enregistré : réutilise l'étiquette active
 * existante plutôt que d'en créer une nouvelle à chaque clic (une seule
 * étiquette physique par équipement, voir app/tags.py).
 */
export async function showTag(formData: FormData) {
  const accessToken = await requireAccessToken();
  const locationId = formData.get("functional_location_id");
  const label = formData.get("label");

  const listResponse = await apiFetch(`/graph/nodes/${locationId}/tags`, accessToken);
  if (!listResponse.ok) {
    await redirectOnFailure(listResponse);
  }
  const tags = await listResponse.json();
  const active = tags.find((tag: { status: string }) => tag.status === "active");
  if (active) {
    redirect(`/registre?tag=${encodeURIComponent(active.payload)}&label=${encodeURIComponent(String(label))}`);
  }

  const createResponse = await apiFetch(`/graph/nodes/${locationId}/tags`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag_type: "qr" }),
  });
  if (!createResponse.ok) {
    await redirectOnFailure(createResponse);
  }
  const tag = await createResponse.json();
  redirect(`/registre?tag=${encodeURIComponent(tag.payload)}&label=${encodeURIComponent(String(label))}`);
}

/**
 * Envoi d'un plan (ADR 011, étape S3) : le navigateur envoie le fichier ici,
 * ce serveur fait le double aller-retour vers l'API (URL présignée, puis
 * envoi direct au stockage) — pas de JavaScript côté client, comme le reste
 * de cette page. L'empreinte SHA-256 exigée par l'API est calculée ici, sur
 * les octets réellement envoyés.
 */
export async function uploadFloorPlan(formData: FormData) {
  const accessToken = await requireAccessToken();
  const spaceId = formData.get("space_id");
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    redirect("/registre?error=CREATION_FAILED");
  }

  const uploadUrlResponse = await apiFetch(
    `/spaces/${spaceId}/floor-plans/upload-url`,
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
    redirect("/registre?error=CREATION_FAILED");
  }

  const sha256 = createHash("sha256").update(Buffer.from(bytes)).digest("hex");
  const createResponse = await apiFetch(`/spaces/${spaceId}/floor-plans`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      object_key: objectKey,
      filename: file.name,
      content_type: file.type,
      sha256,
    }),
  });
  if (!createResponse.ok) {
    await redirectOnFailure(createResponse);
  }

  revalidatePath("/registre");
  redirect(`/registre?space=${spaceId}`);
}

/**
 * Envoi d'un fichier IFC (ADR 011, section 2) : même dance en deux temps
 * que les plans (URL présignée, puis envoi direct au stockage). L'analyse
 * se fait côté serveur dès la confirmation ; le résultat (propositions ou
 * échec) est déjà là au moment de la redirection.
 */
export async function uploadIfcImport(formData: FormData) {
  const accessToken = await requireAccessToken();
  const siteId = formData.get("site_id");
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    redirect("/registre?error=CREATION_FAILED");
  }

  const uploadUrlResponse = await apiFetch(`/sites/${siteId}/ifc-imports/upload-url`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name }),
  });
  if (!uploadUrlResponse.ok) {
    await redirectOnFailure(uploadUrlResponse);
  }
  const { upload_url: uploadUrl, object_key: objectKey } = await uploadUrlResponse.json();

  const bytes = await file.arrayBuffer();
  const putResponse = await fetch(uploadUrl, {
    method: "PUT",
    body: bytes,
    headers: { "Content-Type": "application/octet-stream" },
  });
  if (!putResponse.ok) {
    redirect("/registre?error=CREATION_FAILED");
  }

  const sha256 = createHash("sha256").update(Buffer.from(bytes)).digest("hex");
  const createResponse = await apiFetch(`/sites/${siteId}/ifc-imports`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ object_key: objectKey, filename: file.name, sha256 }),
  });
  if (!createResponse.ok) {
    await redirectOnFailure(createResponse);
  }
  const batch = await createResponse.json();

  revalidatePath("/registre");
  redirect(`/registre?import_site=${siteId}&import_batch=${batch.id}`);
}

export async function acceptIfcImportProposal(formData: FormData) {
  const accessToken = await requireAccessToken();
  const proposalId = formData.get("proposal_id");
  const siteId = formData.get("site_id");
  const batchId = formData.get("batch_id");

  const response = await apiFetch(`/ifc-import-proposals/${proposalId}/accept`, accessToken, {
    method: "POST",
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    redirect(
      `/registre?import_site=${siteId}&import_batch=${batchId}&error=${encodeURIComponent(failureCode(problem))}`,
    );
  }

  revalidatePath("/registre");
  redirect(`/registre?import_site=${siteId}&import_batch=${batchId}`);
}

export async function rejectIfcImportProposal(formData: FormData) {
  const accessToken = await requireAccessToken();
  const proposalId = formData.get("proposal_id");
  const siteId = formData.get("site_id");
  const batchId = formData.get("batch_id");

  const response = await apiFetch(`/ifc-import-proposals/${proposalId}/reject`, accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: formData.get("reason") }),
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    redirect(
      `/registre?import_site=${siteId}&import_batch=${batchId}&error=${encodeURIComponent(failureCode(problem))}`,
    );
  }

  revalidatePath("/registre");
  redirect(`/registre?import_site=${siteId}&import_batch=${batchId}`);
}

function optionalText(value: FormDataEntryValue | null): string | null {
  const text = typeof value === "string" ? value.trim() : "";
  return text.length > 0 ? text : null;
}

export async function createProvider(formData: FormData) {
  const accessToken = await requireAccessToken();
  const response = await apiFetch("/providers", accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: formData.get("name"),
      contact_name: optionalText(formData.get("contact_name")),
      contact_email: optionalText(formData.get("contact_email")),
      contact_phone: optionalText(formData.get("contact_phone")),
    }),
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/registre");
}

export async function updateProvider(formData: FormData) {
  const accessToken = await requireAccessToken();
  const providerId = formData.get("provider_id");
  const response = await apiFetch(`/providers/${providerId}`, accessToken, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: formData.get("name"),
      contact_name: optionalText(formData.get("contact_name")),
      contact_email: optionalText(formData.get("contact_email")),
      contact_phone: optionalText(formData.get("contact_phone")),
    }),
  });
  if (!response.ok) {
    await redirectOnFailure(response);
  }
  revalidatePath("/registre");
}
