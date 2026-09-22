"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, requireAccessToken } from "@/lib/api";

export async function createWorkOrder(formData: FormData) {
  const accessToken = await requireAccessToken();
  const title = formData.get("title");

  if (typeof title !== "string" || title.trim().length === 0) {
    redirect("/ordres-de-travail?error=titre_requis");
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
    redirect(`/ordres-de-travail?error=creation_echouee_${response.status}`);
  }

  revalidatePath("/ordres-de-travail");
}
