import { redirect } from "next/navigation";

import { config } from "./config";
import { getValidAccessToken } from "./session";

/**
 * Redirige vers la connexion si aucune session valide n'existe (absente, ou
 * jeton de rafraîchissement lui-même expiré). Centralisé ici pour que
 * chaque page protégée fasse exactement la même vérification.
 */
export async function requireAccessToken(): Promise<string> {
  const accessToken = await getValidAccessToken();
  if (!accessToken) {
    redirect("/login");
  }
  return accessToken;
}

export async function apiFetch(path: string, accessToken: string, init?: RequestInit) {
  return fetch(`${config.apiUrl}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      ...(init?.headers ?? {}),
      Authorization: `Bearer ${accessToken}`,
    },
  });
}
