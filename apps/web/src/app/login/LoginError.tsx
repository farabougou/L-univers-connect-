"use client";

import { useSearchParams } from "next/navigation";

/** Le code technique reçu dans l'adresse n'est jamais affiché (ADR 013). */
export function LoginError({ message }: { message: string }) {
  const searchParams = useSearchParams();
  if (!searchParams.get("error")) return null;
  return <p style={{ color: "#c0392b" }}>{message}</p>;
}
