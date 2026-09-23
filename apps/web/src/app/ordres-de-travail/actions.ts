"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, requireAccessToken } from "@/lib/api";

export async function createWorkOrder(formData: FormData) {
  const accessToken = await requireAccessToken();
  const title = formData.get("title");

  if (typeof title !== "string" || title.trim().length === 0) {
    redirect("/ordres-de-travail?error=TITLE_REQUIRED");
  }

  const response = await apiFetch("/work-orders", accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title,
      work_order_type: formData.get("work_order_type"),
      priority: formData.get("priority"),
    }),
  });

  if (!response.ok) {
    // Seul le code stable de l'erreur passe dans l'adresse, jamais un texte.
    const problem = await response.json().catch(() => null);
    const code = typeof problem?.code === "string" ? problem.code : "CREATION_FAILED";
    redirect(`/ordres-de-travail?error=${encodeURIComponent(code)}`);
  }

  revalidatePath("/ordres-de-travail");
}

export async function updateWorkOrderStatus(formData: FormData) {
  const accessToken = await requireAccessToken();
  const workOrderId = formData.get("work_order_id");

  const response = await apiFetch(`/work-orders/${workOrderId}/status`, accessToken, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: formData.get("status") }),
  });

  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    const code = typeof problem?.code === "string" ? problem.code : "CREATION_FAILED";
    redirect(`/ordres-de-travail?error=${encodeURIComponent(code)}`);
  }

  revalidatePath("/ordres-de-travail");
  revalidatePath("/registre");
}
