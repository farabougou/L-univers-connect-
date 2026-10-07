/**
 * Création d'un site (POST /sites, services/api/app/routers/assets.py) —
 * réservée aux rôles `responsable_exploitation` et `admin_tenant`
 * (`_MANAGE_REGISTRY_ROLES` côté serveur, voir src/lib/roles.ts). L'écran
 * appelant (app/ajouter-site.tsx) ne montre ce formulaire qu'à ces rôles,
 * mais l'API revérifie toujours elle-même — ce client traduit aussi un 403
 * au cas où le rôle aurait changé entre l'ouverture de l'écran et l'envoi.
 */

export type CreateSiteResult =
  | { ok: true }
  | { ok: false; messageKey: string };

export async function createSite(
  apiUrl: string,
  accessToken: string,
  name: string,
  timezone: string,
): Promise<CreateSiteResult> {
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/sites`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name, timezone }),
    });
  } catch {
    return { ok: false, messageKey: "mobile.add_site.offline" };
  }
  if (response.ok) {
    return { ok: true };
  }
  if (response.status === 403) {
    return { ok: false, messageKey: "mobile.add_site.forbidden" };
  }
  const body = await response.json().catch(() => null);
  if (body?.code === "TIMEZONE_UNKNOWN") {
    return { ok: false, messageKey: "mobile.add_site.invalid_timezone" };
  }
  return { ok: false, messageKey: "mobile.add_site.server_error" };
}
