"use client";

import { useSearchParams } from "next/navigation";

export function CreationError() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");
  if (!error) return null;

  const message =
    error === "titre_requis"
      ? "Le titre est obligatoire."
      : `La création a échoué (${error}). Vérifie que tu as le rôle nécessaire.`;

  return <p style={{ color: "#c0392b" }}>{message}</p>;
}
