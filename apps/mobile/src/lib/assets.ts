/**
 * Registre d'actifs filtrable — écran terrain « Actifs » (app/actifs.tsx).
 * Réutilise les mêmes endpoints que le Global Command Center web
 * (apps/web/src/app/page.tsx) : GET /sites, GET /functional-locations,
 * GET /functional-locations/status-summary — tous trois déjà existants,
 * aucun nouvel endpoint nécessaire.
 */

import { type AssetStatus, equipmentStatusToAssetStatus } from "../design/colors";

type RawSite = { id: string; name: string; archived_at: string | null };

type RawFunctionalLocation = {
  id: string;
  site_id: string;
  code: string;
  name: string;
  archived_at: string | null;
};

type RawStatus = {
  functional_location_id: string;
  operational_status: string;
  communication_status: string;
  current: boolean;
  reason: string | null;
};

export type Site = { id: string; name: string };

export type AssetListItem = {
  id: string;
  code: string;
  name: string;
  siteId: string;
  siteName: string;
  status: AssetStatus;
};

async function fetchJson<T>(url: string, accessToken: string): Promise<T[]> {
  const response = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
  return response.ok ? ((await response.json()) as T[]) : [];
}

export async function fetchAssets(
  apiUrl: string,
  accessToken: string,
): Promise<{ sites: Site[]; assets: AssetListItem[] }> {
  const [sites, locations, statuses] = await Promise.all([
    fetchJson<RawSite>(`${apiUrl}/sites`, accessToken),
    fetchJson<RawFunctionalLocation>(`${apiUrl}/functional-locations`, accessToken),
    fetchJson<RawStatus>(`${apiUrl}/functional-locations/status-summary`, accessToken),
  ]);

  const siteById = new Map(sites.map((site) => [site.id, site]));
  const statusByLocation = new Map(statuses.map((status) => [status.functional_location_id, status]));

  const assets: AssetListItem[] = locations
    .filter((location) => location.archived_at === null)
    .map((location) => {
      const site = siteById.get(location.site_id);
      const status = statusByLocation.get(location.id);
      return {
        id: location.id,
        code: location.code,
        name: location.name,
        siteId: location.site_id,
        siteName: site?.name ?? "",
        status: status
          ? equipmentStatusToAssetStatus({
              operational_status: status.operational_status,
              communication_status: status.communication_status,
              current: status.current,
              reason: status.reason,
            })
          : "unknown",
      };
    });

  return {
    sites: sites
      .filter((site) => site.archived_at === null)
      .map((site) => ({ id: site.id, name: site.name })),
    assets,
  };
}
