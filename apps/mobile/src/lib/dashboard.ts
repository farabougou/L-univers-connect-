/**
 * Tableau de bord Accueil (maquette de référence, 06/10/2026) : uniquement
 * des comptes réels déjà exposés par l'API, mêmes sources que le Global
 * Command Center web (apps/web/src/app/page.tsx) — jamais un chiffre
 * fabriqué pour remplir un écran. « Bâtiments » compte les espaces de type
 * `building` (GET /spaces, app/spatial_vocabulary.py) ; « Alertes » compte
 * les alarmes et constats ouverts (même filtre que src/lib/alerts.ts).
 */

import { loadEquipmentLabels } from "./equipmentLabels";

type RawSite = { id: string; archived_at: string | null };
type RawSpace = { id: string; space_type: string };
type RawActivity = {
  kind: "intervention" | "work_order" | "alarm" | "finding" | "event";
  at: string;
  functional_location_id: string | null;
  reference_id: string;
  title: string | null;
};

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

/**
 * Nombre de signalements ouverts, SANS télécharger la liste : `limit=1` ne rend
 * qu'une ligne et l'en-tête `X-Total-Count` donne le total (app/pagination.py).
 * Pendant une tempête d'alarmes, la liste complète pèserait des mégaoctets pour
 * afficher un seul nombre.
 */
async function countOpenSignals(apiUrl: string, accessToken: string, path: string): Promise<number> {
  const totals = await Promise.all(
    ["open", "in_progress"].map(async (handlingStatus) => {
      const url = `${apiUrl}${path}?handling_status=${handlingStatus}`;
      const response = await fetch(`${url}&limit=1`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) return 0;
      const header = response.headers.get("X-Total-Count");
      // Number(null) vaut 0 : sans cette précaution, un en-tête absent afficherait « 0 alerte ».
      const total = header === null ? Number.NaN : Number(header);
      if (Number.isInteger(total) && total >= 0) return total;
      // Serveur sans pagination : repli sur la liste complète, plutôt qu'un faux nombre.
      return (await fetchJson<{ id: string }>(url, accessToken)).length;
    }),
  );
  return totals.reduce((total, count) => total + count, 0);
}

export async function fetchDashboardCounts(
  apiUrl: string,
  accessToken: string,
): Promise<DashboardCounts> {
  const [sites, locations, spaces, alarmCount, findingCount] = await Promise.all([
    fetchJson<RawSite>(`${apiUrl}/sites`, accessToken),
    loadEquipmentLabels(apiUrl, accessToken),
    fetchJson<RawSpace>(`${apiUrl}/spaces`, accessToken),
    countOpenSignals(apiUrl, accessToken, "/alarms"),
    countOpenSignals(apiUrl, accessToken, "/findings"),
  ]);
  return {
    sites: sites.filter((site) => site.archived_at === null).length,
    buildings: spaces.filter((space) => space.space_type === "building").length,
    // La liste des équipements exclut déjà les archivés (serveur et liste locale).
    equipment: locations.length,
    openAlerts: alarmCount + findingCount,
  };
}

export async function fetchRecentActivity(
  apiUrl: string,
  accessToken: string,
): Promise<ActivityItem[]> {
  const [entries, locations] = await Promise.all([
    fetchJson<RawActivity>(`${apiUrl}/activity/recent`, accessToken),
    loadEquipmentLabels(apiUrl, accessToken),
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
