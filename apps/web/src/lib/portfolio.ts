/**
 * Agrégation pure pour la vue Portfolio (`/`, ADR 014 §2 — Global Command
 * Center) : regroupe équipements, alarmes, constats, ordres de travail et
 * passerelles Edge par site. Aucun appel réseau ici, pour rester testable
 * sans backend (voir portfolio.test.ts).
 */

// Quatre gravités du référentiel (ADR 013, étape L3) : jamais un cinquième
// niveau inventé pour cet écran.
export const SEVERITIES = ["critical", "major", "warning", "info"] as const;
export type Severity = (typeof SEVERITIES)[number];
export type SeverityCounts = Record<Severity, number>;

export function emptySeverityCounts(): SeverityCounts {
  return { critical: 0, major: 0, warning: 0, info: 0 };
}

export function addSeverity(counts: SeverityCounts, severity: string): void {
  if ((SEVERITIES as readonly string[]).includes(severity)) {
    counts[severity as Severity] += 1;
  }
}

export function mergeSeverityCounts(a: SeverityCounts, b: SeverityCounts): SeverityCounts {
  return {
    critical: a.critical + b.critical,
    major: a.major + b.major,
    warning: a.warning + b.warning,
    info: a.info + b.info,
  };
}

export type Site = { id: string; name: string };
export type FunctionalLocation = { id: string; site_id: string };
export type Alarm = { functional_location_id: string | null; severity: string };
export type Finding = { subject_node_id: string; severity: string };
export type WorkOrder = { functional_location_id: string | null; status: string };
export type Device = { site_id: string | null; communication_status: string };

export type DeviceCounts = { online: number; offline: number; unknown: number };

// Une alarme critique passe toujours avant une majeure, même plus ancienne
// (directive UI/dashboard du 30/09/2026, section 20 — ordre de priorité).
const SEVERITY_RANK: Record<Severity, number> = { critical: 0, major: 1, warning: 2, info: 3 };

/**
 * Trie les alarmes par gravité puis par ancienneté (la plus ancienne
 * d'abord, à gravité égale) et ne garde que les `limit` premières — jamais
 * une simple liste chronologique brute (directive, section 11), jamais une
 * surcharge visuelle (section 18).
 */
export function prioritizeAlarms<T extends { severity: string; raised_at: string }>(
  alarms: T[],
  limit: number,
): T[] {
  return [...alarms]
    .sort((a, b) => {
      const bySeverity = SEVERITY_RANK[a.severity as Severity] - SEVERITY_RANK[b.severity as Severity];
      return bySeverity !== 0 ? bySeverity : a.raised_at.localeCompare(b.raised_at);
    })
    .slice(0, limit);
}

export type SitePortfolio = {
  site: Site;
  equipmentCount: number;
  alarmSeverity: SeverityCounts;
  findingSeverity: SeverityCounts;
  openWorkOrders: number;
  devices: DeviceCounts | null;
};

export type PortfolioTotals = {
  equipmentCount: number;
  alarmSeverity: SeverityCounts;
  findingSeverity: SeverityCounts;
  openWorkOrders: number;
};

const OPEN_WORK_ORDER_STATUSES = new Set(["open", "in_progress"]);

/**
 * `devices` est `null` quand l'appel `GET /devices` a été refusé (rôle
 * terrain) : la colonne Edge est alors absente du résultat par site,
 * jamais une colonne à zéro fabriquée pour combler l'absence de droit.
 */
export function aggregatePortfolio(
  sites: Site[],
  locations: FunctionalLocation[],
  alarms: Alarm[],
  findings: Finding[],
  workOrders: WorkOrder[],
  devices: Device[] | null,
): { bySite: SitePortfolio[]; totals: PortfolioTotals } {
  const siteByLocation = new Map(locations.map((location) => [location.id, location.site_id]));
  const locationCountBySite = new Map<string, number>();
  for (const location of locations) {
    locationCountBySite.set(location.site_id, (locationCountBySite.get(location.site_id) ?? 0) + 1);
  }

  const bySiteId = new Map<string, SitePortfolio>();
  for (const site of sites) {
    bySiteId.set(site.id, {
      site,
      equipmentCount: locationCountBySite.get(site.id) ?? 0,
      alarmSeverity: emptySeverityCounts(),
      findingSeverity: emptySeverityCounts(),
      openWorkOrders: 0,
      devices: devices ? { online: 0, offline: 0, unknown: 0 } : null,
    });
  }

  for (const alarm of alarms) {
    const siteId = alarm.functional_location_id
      ? siteByLocation.get(alarm.functional_location_id)
      : undefined;
    const entry = siteId ? bySiteId.get(siteId) : undefined;
    if (entry) addSeverity(entry.alarmSeverity, alarm.severity);
  }

  for (const finding of findings) {
    // Un constat porté par un espace ou un point (pas un équipement)
    // n'est pas encore rattaché à un site ici (voir app/rules.py::_subject)
    // — compté seulement quand subject_node_id désigne un équipement connu.
    const siteId = siteByLocation.get(finding.subject_node_id);
    const entry = siteId ? bySiteId.get(siteId) : undefined;
    if (entry) addSeverity(entry.findingSeverity, finding.severity);
  }

  for (const workOrder of workOrders) {
    if (!OPEN_WORK_ORDER_STATUSES.has(workOrder.status)) continue;
    const siteId = workOrder.functional_location_id
      ? siteByLocation.get(workOrder.functional_location_id)
      : undefined;
    const entry = siteId ? bySiteId.get(siteId) : undefined;
    if (entry) entry.openWorkOrders += 1;
  }

  if (devices) {
    for (const device of devices) {
      const entry = device.site_id ? bySiteId.get(device.site_id) : undefined;
      if (!entry || !entry.devices) continue;
      if (device.communication_status === "online") entry.devices.online += 1;
      else if (device.communication_status === "unknown") entry.devices.unknown += 1;
      else entry.devices.offline += 1;
    }
  }

  const bySite = sites.map((site) => bySiteId.get(site.id)!).filter(Boolean);
  const totals = bySite.reduce<PortfolioTotals>(
    (acc, entry) => ({
      equipmentCount: acc.equipmentCount + entry.equipmentCount,
      alarmSeverity: mergeSeverityCounts(acc.alarmSeverity, entry.alarmSeverity),
      findingSeverity: mergeSeverityCounts(acc.findingSeverity, entry.findingSeverity),
      openWorkOrders: acc.openWorkOrders + entry.openWorkOrders,
    }),
    {
      equipmentCount: 0,
      alarmSeverity: emptySeverityCounts(),
      findingSeverity: emptySeverityCounts(),
      openWorkOrders: 0,
    },
  );

  return { bySite, totals };
}
