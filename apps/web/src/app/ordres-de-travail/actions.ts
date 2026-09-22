"use server";

import { revalidatePath } from "next/cache";

import { apiFetch, requireAccessToken } from "@/lib/api";

export async function createWorkOrder(formData: FormData) {
  const accessToken = await requireAccessToken();
  const title = formData.get("title");

  if (typeof title !== "string" || title.trim().length === 0) {
    return;
  }

  await apiFetch("/work-orders", accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title,
      work_order_type: formData.get("work_order_type"),
      priority: formData.get("priority"),
    }),
  });

  revalidatePath("/ordres-de-travail");
}
