/**
 * Tableau de bord Accueil (maquette de référence, 06/10/2026) : uniquement
 * des comptes réels déjà exposés par l'API, mêmes sources que le Global
 * Command Center web (apps/web/src/app/page.tsx) — jamais un chiffre
 * fabriqué pour remplir un écran. « Bâtiments » compte les espaces de type
 * `building` (GET /spaces, app/spatial_vocabulary.py) ; « Alertes » compte
 * les alarmes et constats ouverts (même filtre que src/lib/alerts.ts).
 */

type RawSite = { id: string; archived_at: string | null };
type RawFunctionalLocation = { id: string; archived_at: string | null };
type RawSpace = { id: string; space_type: string };
type RawActivity = {
  kind: "intervention" | "work_order" | "alarm" | "finding" | "event";
  at: string;
  functional_location_id: string | null;
  reference_id: string;
  title: string | null;
};
type RawFunctionalLocationLabel = { id: string; code: string; name: string };

export type DashboardCounts = {
  sites: number;
  buildings: number;
  equipment: number;
  openAlerts: number;
};

export type ActivityItem = {
  key: string;
  kind: RawActivity["kind"];
  at: string;
  title: string | null;
  equipmentId: string | null;
  equipmentLabel: string | null;
};

async function fetchJson<T>(url: string, accessToken: string): Promise<T[]> {
  const response = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
  return response.ok ? ((await response.json()) as T[]) : [];
}

async function countOpenSignals(apiUrl: string, accessToken: string, path: string): Promise<number> {
  const results = await Promise.all(
    ["open", "in_progress"].map((handlingStatus) =>
      fetchJson<{ id: string }>(`${apiUrl}${path}?handling_status=${handlingStatus}`, accessToken),
    ),
  );
  return results.reduce((total, batch) => total + batch.length, 0);
}

export async function fetchDashboardCounts(
  apiUrl: string,
  accessToken: string,
): Promise<DashboardCounts> {
  const [sites, locations, spaces, alarmCount, findingCount] = await Promise.all([
    fetchJson<RawSite>(`${apiUrl}/sites`, accessToken),
    fetchJson<RawFunctionalLocation>(`${apiUrl}/functional-locations`, accessToken),
    fetchJson<RawSpace>(`${apiUrl}/spaces`, accessToken),
    countOpenSignals(apiUrl, accessToken, "/alarms"),
    countOpenSignals(apiUrl, accessToken, "/findings"),
  ]);
  return {
    sites: sites.filter((site) => site.archived_at === null).length,
    buildings: spaces.filter((space) => space.space_type === "building").length,
    equipment: locations.filter((location) => location.archived_at === null).length,
    openAlerts: alarmCount + findingCount,
  };
}

export async function fetchRecentActivity(
  apiUrl: string,
  accessToken: string,
): Promise<ActivityItem[]> {
  const [entries, locations] = await Promise.all([
    fetchJson<RawActivity>(`${apiUrl}/activity/recent`, accessToken),
    fetchJson<RawFunctionalLocationLabel>(`${apiUrl}/functional-locations`, accessToken),
  ]);
  const locationById = new Map(locations.map((location) => [location.id, location]));
  return entries.map((entry) => {
    const location = entry.functional_location_id
      ? locationById.get(entry.functional_location_id)
      : undefined;
    return {
      key: `${entry.kind}-${entry.reference_id}`,
      kind: entry.kind,
      at: entry.at,
      title: entry.title,
      equipmentId: location ? entry.functional_location_id : null,
      equipmentLabel: location ? `${location.code} — ${location.name}` : null,
    };
  });
}
