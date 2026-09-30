import Link from "next/link";
import { redirect } from "next/navigation";

import { BrandMark } from "@/components/BrandMark";
import { RecentActivityFeed } from "@/components/RecentActivityFeed";
import { ASSET_STATUS_COLOR, StatusBadge, equipmentStatusToAssetStatus } from "@/components/StatusBadge";
import { apiFetch, requireAccessToken } from "@/lib/api";
import {
  ACTIVITY_KINDS,
  toActivityFeedEntries,
  type ActivityKind,
  type PortfolioTimelineEntry,
} from "@/lib/activity";
import {
  badgeStyle,
  cardStyle,
  cellStyle,
  colors,
  headerCellStyle,
  pageContainerStyle,
  pageHeaderStyle,
  sectionTitleStyle,
} from "@/lib/formStyles";
import {
  type PortfolioEnergyMeter,
  countMetersWithoutData,
  summarizeEnergyByUnit,
} from "@/lib/energy";
import { ASSET_STATUS_ORDER, distributeByAssetStatus, type PortfolioEquipmentStatus } from "@/lib/health";
import { getLocale, getTranslator } from "@/lib/i18n";
import {
  type MaintenanceIntervention,
  countCriticalOpen,
  countInProgress,
  recentClosures,
  repeatingFailures,
} from "@/lib/maintenance";
import { type EquipmentStatus, statusMessage } from "@/lib/passport";
import { roleLabels } from "@/lib/roles";
import {
  type Alarm,
  type Finding,
  type FunctionalLocation as PortfolioLocation,
  type Severity,
  type SeverityCounts,
  type Site,
  type WorkOrder,
  type Device,
  SEVERITIES,
  SEVERITY_COLOR,
  aggregatePortfolio,
  prioritizeAlarms,
} from "@/lib/portfolio";
import { type Locale, formatDate, formatDateTime, formatNumber } from "@/i18n/translator";

type Me = {
  sub: string;
  tenant_id: string;
  roles: string[];
};

type FunctionalLocation = PortfolioLocation & { code: string; name: string };

const COMMUNICATION_COLOR: Record<string, string> = {
  online: "#16a34a",
  offline: "#dc2626",
  unreachable: "#dc2626",
  unknown: "#9ca3af",
};

// Nombre maximal affiché dans le bloc « Alarmes prioritaires » : éviter la
// surcharge visuelle (directive, section 18) — le lien de site donne accès
// au reste.
const MAX_PRIORITY_ALARMS = 8;
const MAX_REPEATING_FAILURES = 5;
const MAX_RECENT_CLOSURES = 5;

type AlarmDetail = Alarm & {
  id: string;
  message: string;
  ack_state: string;
  raised_at: string;
};

type WorkOrderDetail = WorkOrder & {
  id: string;
  title: string;
  work_order_type: string;
  priority: string;
};

async function _openSignals<T extends { severity: string }>(
  accessToken: string,
  path: string,
): Promise<T[]> {
  const results = await Promise.all(
    ["open", "in_progress"].map(async (handlingStatus) => {
      const response = await apiFetch(`${path}?handling_status=${handlingStatus}`, accessToken);
      return response.ok ? ((await response.json()) as T[]) : [];
    }),
  );
  return results.flat();
}

export default async function PortfolioPage({
  searchParams,
}: {
  searchParams: Promise<{ site?: string }>;
}) {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();
  const locale = await getLocale();
  const { site: selectedSiteId } = await searchParams;

  const [
    meResponse,
    sitesResponse,
    locationsResponse,
    workOrdersResponse,
    devicesResponse,
    interventionsResponse,
    energyResponse,
    equipmentStatusesResponse,
    recentActivityResponse,
  ] = await Promise.all([
    apiFetch("/me", accessToken),
    apiFetch("/sites", accessToken),
    apiFetch("/functional-locations", accessToken),
    apiFetch("/work-orders", accessToken),
    apiFetch("/devices", accessToken),
    apiFetch("/interventions", accessToken),
    apiFetch("/energy/portfolio-summary", accessToken),
    apiFetch("/functional-locations/status-summary", accessToken),
    apiFetch("/activity/recent", accessToken),
  ]);

  if (!meResponse.ok) {
    redirect("/login");
  }

  const me: Me = await meResponse.json();
  const sites: Site[] = sitesResponse.ok ? await sitesResponse.json() : [];
  const locations: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];
  const workOrders: WorkOrderDetail[] = workOrdersResponse.ok
    ? await workOrdersResponse.json()
    : [];
  // Réservé aux rôles de gestion côté API (GET /devices) : un rôle terrain
  // voit le reste de la vue d'ensemble sans cette colonne, jamais une
  // colonne à zéro fabriquée pour combler l'absence de droit.
  const devices: Device[] | null = devicesResponse.ok ? await devicesResponse.json() : null;
  const interventions: MaintenanceIntervention[] = interventionsResponse.ok
    ? await interventionsResponse.json()
    : [];
  const energySummary: { reference_date: string; meters: PortfolioEnergyMeter[] } | null =
    energyResponse.ok ? await energyResponse.json() : null;
  const equipmentStatuses: PortfolioEquipmentStatus[] = equipmentStatusesResponse.ok
    ? await equipmentStatusesResponse.json()
    : [];
  const recentActivity: PortfolioTimelineEntry[] = recentActivityResponse.ok
    ? await recentActivityResponse.json()
    : [];

  const [alarms, findings] = await Promise.all([
    _openSignals<AlarmDetail>(accessToken, "/alarms"),
    _openSignals<Finding>(accessToken, "/findings"),
  ]);

  const siteById = new Map(sites.map((site) => [site.id, site]));
  const locationsBySite = new Map<string, FunctionalLocation[]>();
  const locationById = new Map<string, FunctionalLocation>();
  for (const location of locations) {
    const list = locationsBySite.get(location.site_id) ?? [];
    list.push(location);
    locationsBySite.set(location.site_id, list);
    locationById.set(location.id, location);
  }

  // Bloc « Alarmes prioritaires » (directive UI/dashboard, section 11) :
  // uniquement les alarmes réellement actives (déjà filtré par
  // _openSignals), triées par gravité puis par ancienneté — jamais une
  // simple liste chronologique brute.
  const priorityAlarms = prioritizeAlarms(alarms, MAX_PRIORITY_ALARMS);

  // Bloc « Maintenance » (directive UI/dashboard, section 12). « En retard »
  // n'est pas calculé : aucune date d'échéance n'existe sur un ordre de
  // travail aujourd'hui (voir apps/web/src/lib/maintenance.ts).
  const maintenanceInProgress = countInProgress(workOrders);
  const maintenanceCritical = countCriticalOpen(workOrders);
  const maintenanceRepeating = repeatingFailures(workOrders).slice(0, MAX_REPEATING_FAILURES);
  const maintenanceClosures = recentClosures(interventions, MAX_RECENT_CLOSURES);

  // Bloc « Énergie » (directive UI/dashboard, section 13). Consommation
  // brute par compteur d'énergie validé, groupée par unité — jamais
  // d'économies, de CO2 évité, de ROI ni de KPI réglementaire (voir
  // apps/web/src/lib/energy.ts). Production, batterie et groupe
  // électrogène ne sont pas modélisés aujourd'hui : ils n'apparaissent pas
  // ici plutôt qu'une case « indisponible » permanente.
  const energyMeters = energySummary?.meters ?? [];
  const energyByUnit = summarizeEnergyByUnit(energyMeters);
  const energyMetersWithoutData = countMetersWithoutData(energyMeters);

  // Bloc « Santé des actifs » (directive UI/dashboard, section 15).
  // Répartition Normal/Attention/Critique/Hors ligne/Donnée ancienne/
  // Inconnu/Maintenance, calculée pour tout le portefeuille en une
  // poignée de requêtes côté API (voir apps/web/src/lib/health.ts) —
  // jamais un appel par équipement depuis le navigateur (directive,
  // section 29). Ne déclenche aucune alerte : lecture pure, comme le
  // passeport équipement.
  const healthDistribution = distributeByAssetStatus(equipmentStatuses);

  // Bloc « Activité récente » (directive UI/dashboard, section 16).
  // Chronologie fusionnée pour tout le portefeuille (interventions, ordres
  // de travail, alarmes, constats — voir apps/web/src/lib/activity.ts et
  // app/timeline.py::portfolio_timeline), la plus récente d'abord, filtrable
  // par catégorie côté client (seule interaction du bloc).
  const activityFeedEntries = toActivityFeedEntries(recentActivity, locale, locationById);
  const activityKindLabels = Object.fromEntries(
    ACTIVITY_KINDS.map((kind) => [kind, t(`web.dashboard.activity_kind.${kind}`)]),
  ) as Record<ActivityKind, string>;

  const { bySite: portfolio, totals } = aggregatePortfolio(
    sites,
    locations,
    alarms,
    findings,
    workOrders,
    devices,
  );

  const selectedSite = selectedSiteId ? sites.find((site) => site.id === selectedSiteId) : null;
  const selectedLocations = selectedSite ? locationsBySite.get(selectedSite.id) ?? [] : [];

  const [alarmCountByLocation, findingCountByLocation, statuses] = await Promise.all([
    Promise.resolve(_countByLocation(alarms.map((a) => a.functional_location_id))),
    Promise.resolve(_countByLocation(findings.map((f) => f.subject_node_id))),
    Promise.all(
      selectedLocations.map(async (location) => {
        const response = await apiFetch(
          `/functional-locations/${location.id}/status`,
          accessToken,
        );
        const status: EquipmentStatus | null = response.ok ? await response.json() : null;
        return [location.id, status] as const;
      }),
    ),
  ]);
  const statusByLocation = new Map(statuses);

  return (
    <main style={pageContainerStyle}>
      <header style={pageHeaderStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: colors.accent }}>
            <BrandMark variant="mono" size={32} label={t("common.app_name")} />
          </span>
          <div>
            <h1 style={{ fontSize: 24, margin: 0 }}>{t("common.app_name")}</h1>
            <p style={{ color: colors.textMuted, fontSize: 14, marginTop: 4 }}>
              {t("web.dashboard.signed_in_as", { user: me.sub, roles: roleLabels(me.roles, t) })}
            </p>
          </div>
        </div>
        <a href="/api/auth/logout" style={{ color: colors.textMuted, fontSize: 14 }}>
          {t("common.sign_out")}
        </a>
      </header>

      <nav style={{ display: "flex", gap: 20, marginBottom: 24, flexWrap: "wrap" }}>
        <Link href="/alarmes" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.alarms_link")} →
        </Link>
        <Link href="/ordres-de-travail" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.maintenance_link")} →
        </Link>
        <Link href="/energie" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.energy_link")} →
        </Link>
        <Link href="/telemetrie" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.telemetry_link")} →
        </Link>
        <Link href="/documents" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.documents_link")} →
        </Link>
        <Link href="/plans" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.spatial_link")} →
        </Link>
        <Link href="/automation" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.automation_link")} →
        </Link>
        <Link href="/edge" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.edge_link")} →
        </Link>
        <Link href="/registre" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.registry_link")} →
        </Link>
      </nav>

      <section style={{ ...cardStyle, marginBottom: 24 }}>
        <h2 style={sectionTitleStyle}>{t("web.dashboard.portfolio_title")}</h2>
        <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
          <Kpi label={t("web.dashboard.kpi_sites")} value={String(sites.length)} />
          <Kpi label={t("web.dashboard.kpi_equipment")} value={String(totals.equipmentCount)} />
          <SeverityKpi
            label={t("web.dashboard.kpi_alarms")}
            counts={totals.alarmSeverity}
            t={t}
          />
          <SeverityKpi
            label={t("web.dashboard.kpi_findings")}
            counts={totals.findingSeverity}
            t={t}
          />
          <Kpi
            label={t("web.dashboard.kpi_work_orders")}
            value={String(totals.openWorkOrders)}
          />
        </div>
      </section>

      <section style={{ ...cardStyle, marginBottom: 24, padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "20px 24px 0" }}>
          <h2 style={sectionTitleStyle}>{t("web.dashboard.priority_alarms_title")}</h2>
        </div>
        {priorityAlarms.length === 0 ? (
          <p style={{ color: colors.textMuted, padding: "0 24px 20px" }}>
            {t("web.dashboard.no_priority_alarms")}
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={headerCellStyle}>{t("web.dashboard.col_severity")}</th>
                <th style={headerCellStyle}>{t("web.dashboard.equipment")}</th>
                <th style={headerCellStyle}>{t("web.dashboard.site_column")}</th>
                <th style={headerCellStyle}>{t("web.dashboard.col_message")}</th>
                <th style={headerCellStyle}>{t("web.dashboard.col_ack")}</th>
                <th style={headerCellStyle}>{t("web.dashboard.col_since")}</th>
                <th style={headerCellStyle} />
              </tr>
            </thead>
            <tbody>
              {priorityAlarms.map((alarm) => {
                const location = alarm.functional_location_id
                  ? locationById.get(alarm.functional_location_id)
                  : undefined;
                return (
                  <tr key={alarm.id}>
                    <td style={cellStyle}>
                      <span
                        title={t(`severity.${alarm.severity}`)}
                        style={badgeStyle(SEVERITY_COLOR[alarm.severity as Severity])}
                      >
                        {t(`severity.${alarm.severity}`)}
                      </span>
                    </td>
                    <td style={cellStyle}>
                      {location ? (
                        <Link href={`/registre/${location.id}`} style={{ color: colors.accent }}>
                          {location.code} — {location.name}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td style={cellStyle}>
                      {location ? (siteById.get(location.site_id)?.name ?? "—") : "—"}
                    </td>
                    <td style={cellStyle}>{alarm.message}</td>
                    <td style={cellStyle}>{t(`ack_state.${alarm.ack_state}`)}</td>
                    <td style={cellStyle}>{formatDateTime(locale, alarm.raised_at)}</td>
                    <td style={cellStyle}>
                      {location && (
                        <Link href={`/registre/${location.id}`} style={{ color: colors.accent }}>
                          {t("web.dashboard.drill_down")} →
                        </Link>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <section style={{ ...cardStyle, marginBottom: 24 }}>
        <h2 style={sectionTitleStyle}>{t("web.dashboard.maintenance_title")}</h2>
        <div style={{ display: "flex", gap: 32, flexWrap: "wrap", marginBottom: 12 }}>
          <Kpi
            label={t("web.dashboard.maintenance_in_progress")}
            value={String(maintenanceInProgress)}
          />
          <Kpi
            label={t("web.dashboard.maintenance_critical")}
            value={String(maintenanceCritical)}
          />
        </div>
        <p style={{ color: colors.textMuted, fontSize: 12, marginBottom: 20 }}>
          {t("web.dashboard.maintenance_overdue_unavailable")}
        </p>
        <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 280px" }}>
            <h3 style={sectionTitleStyle}>{t("web.dashboard.maintenance_repeating_title")}</h3>
            {maintenanceRepeating.length === 0 ? (
              <p style={{ color: colors.textMuted, fontSize: 13 }}>
                {t("web.dashboard.maintenance_repeating_none")}
              </p>
            ) : (
              <ul
                style={{
                  listStyle: "none",
                  padding: 0,
                  margin: 0,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                {maintenanceRepeating.map((entry) => {
                  const location = locationById.get(entry.functional_location_id);
                  return (
                    <li
                      key={entry.functional_location_id}
                      style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}
                    >
                      {location ? (
                        <Link href={`/registre/${location.id}`} style={{ color: colors.accent }}>
                          {location.code} — {location.name}
                        </Link>
                      ) : (
                        "—"
                      )}
                      <span style={{ color: colors.textMuted }}>
                        {t("web.dashboard.maintenance_repeating_count", {
                          count: entry.count,
                        })}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
          <div style={{ flex: "1 1 280px" }}>
            <h3 style={sectionTitleStyle}>{t("web.dashboard.maintenance_closures_title")}</h3>
            {maintenanceClosures.length === 0 ? (
              <p style={{ color: colors.textMuted, fontSize: 13 }}>
                {t("web.dashboard.maintenance_closures_none")}
              </p>
            ) : (
              <ul
                style={{
                  listStyle: "none",
                  padding: 0,
                  margin: 0,
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                }}
              >
                {maintenanceClosures.map((intervention) => {
                  const location = intervention.functional_location_id
                    ? locationById.get(intervention.functional_location_id)
                    : undefined;
                  return (
                    <li key={intervention.id} style={{ fontSize: 13 }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span>{location ? `${location.code} — ${location.name}` : "—"}</span>
                        <span style={{ color: colors.textMuted }}>
                          {formatDateTime(locale, intervention.ended_at as string)}
                        </span>
                      </div>
                      <div style={{ color: colors.textMuted }}>
                        {intervention.technician}
                        {intervention.summary ? ` — ${intervention.summary}` : ""}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </section>

      <section style={{ ...cardStyle, marginBottom: 24 }}>
        <h2 style={sectionTitleStyle}>{t("web.dashboard.energy_title")}</h2>
        {energyMeters.length === 0 ? (
          <p style={{ color: colors.textMuted }}>{t("web.dashboard.energy_no_meters")}</p>
        ) : (
          <>
            <p style={{ color: colors.textMuted, fontSize: 13, marginBottom: 16 }}>
              {t("web.dashboard.energy_reference_date", {
                date: energySummary ? formatDate(locale, energySummary.reference_date) : "",
              })}
            </p>
            <div style={{ display: "flex", gap: 32, flexWrap: "wrap", marginBottom: 12 }}>
              {energyByUnit.map((summary) => (
                <div key={summary.unit} style={{ display: "flex", gap: 32 }}>
                  <Kpi
                    label={t("web.dashboard.energy_consumption_label", { unit: summary.unit })}
                    value={
                      summary.totalConsumption === null
                        ? t("web.dashboard.energy_unavailable")
                        : formatNumber(locale, summary.totalConsumption)
                    }
                  />
                  <Kpi
                    label={t("web.dashboard.energy_trend_label")}
                    value={
                      summary.trendPercent === null
                        ? t("web.dashboard.energy_trend_unavailable")
                        : `${summary.trendPercent > 0 ? "+" : ""}${formatNumber(locale, summary.trendPercent, 1)} %`
                    }
                  />
                </div>
              ))}
            </div>
            {energyMetersWithoutData > 0 && (
              <p style={{ color: colors.textMuted, fontSize: 12 }}>
                {t("web.dashboard.energy_meters_without_data", { count: energyMetersWithoutData })}
              </p>
            )}
          </>
        )}
      </section>

      <section style={{ ...cardStyle, marginBottom: 24 }}>
        <h2 style={sectionTitleStyle}>{t("web.dashboard.health_title")}</h2>
        {locations.length === 0 ? (
          <p style={{ color: colors.textMuted }}>{t("web.dashboard.no_equipment")}</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {ASSET_STATUS_ORDER.map((assetStatus) => {
              const ids = healthDistribution[assetStatus];
              const percent = locations.length ? (ids.length / locations.length) * 100 : 0;
              return (
                <details key={assetStatus}>
                  <summary
                    style={{
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      padding: "6px 0",
                    }}
                  >
                    <StatusBadge status={assetStatus} label={t(`asset_status.${assetStatus}`)} />
                    <div
                      style={{
                        flex: 1,
                        background: "#f3f4f6",
                        borderRadius: 4,
                        height: 8,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${percent}%`,
                          background: ASSET_STATUS_COLOR[assetStatus],
                          height: "100%",
                        }}
                      />
                    </div>
                    <span
                      style={{ color: colors.textMuted, fontSize: 13, minWidth: 24, textAlign: "right" }}
                    >
                      {ids.length}
                    </span>
                  </summary>
                  {ids.length === 0 ? (
                    <p style={{ color: colors.textMuted, fontSize: 13, padding: "4px 0 8px 28px" }}>
                      {t("web.dashboard.health_category_empty")}
                    </p>
                  ) : (
                    <ul
                      style={{
                        listStyle: "none",
                        padding: "4px 0 8px 28px",
                        margin: 0,
                        display: "flex",
                        flexDirection: "column",
                        gap: 4,
                      }}
                    >
                      {ids.map((id) => {
                        const location = locationById.get(id);
                        return (
                          <li key={id} style={{ fontSize: 13 }}>
                            {location ? (
                              <Link href={`/registre/${id}`} style={{ color: colors.accent }}>
                                {location.code} — {location.name}
                              </Link>
                            ) : (
                              "—"
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </details>
              );
            })}
          </div>
        )}
      </section>

      <section style={{ ...cardStyle, marginBottom: 24 }}>
        <h2 style={sectionTitleStyle}>{t("web.dashboard.activity_title")}</h2>
        <RecentActivityFeed
          entries={activityFeedEntries}
          kindLabels={activityKindLabels}
          emptyLabel={t("web.dashboard.activity_empty")}
        />
      </section>

      {sites.length === 0 ? (
        <section style={cardStyle}>
          <p style={{ color: colors.textMuted }}>{t("web.dashboard.no_sites")}</p>
        </section>
      ) : (
        <section style={{ ...cardStyle, marginBottom: 24, padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={headerCellStyle}>{t("web.dashboard.site_column")}</th>
                <th style={headerCellStyle}>{t("web.dashboard.equipment")}</th>
                <th style={headerCellStyle}>{t("web.dashboard.kpi_alarms")}</th>
                <th style={headerCellStyle}>{t("web.dashboard.kpi_findings")}</th>
                <th style={headerCellStyle}>{t("web.dashboard.kpi_work_orders")}</th>
                {devices && <th style={headerCellStyle}>{t("web.dashboard.edge_column")}</th>}
                <th style={headerCellStyle} />
              </tr>
            </thead>
            <tbody>
              {portfolio.map((entry) => (
                <tr key={entry.site.id}>
                  <td style={{ ...cellStyle, fontWeight: 600 }}>{entry.site.name}</td>
                  <td style={cellStyle}>{entry.equipmentCount}</td>
                  <td style={cellStyle}>
                    <SeverityBadges counts={entry.alarmSeverity} t={t} />
                  </td>
                  <td style={cellStyle}>
                    <SeverityBadges counts={entry.findingSeverity} t={t} />
                  </td>
                  <td style={cellStyle}>{entry.openWorkOrders}</td>
                  {devices && (
                    <td style={cellStyle}>
                      {entry.devices && (entry.devices.online || entry.devices.offline || entry.devices.unknown) ? (
                        <DeviceBadges counts={entry.devices} t={t} />
                      ) : (
                        <span style={{ color: colors.textMuted }}>{t("web.dashboard.edge_none")}</span>
                      )}
                    </td>
                  )}
                  <td style={cellStyle}>
                    <Link href={`/?site=${entry.site.id}`} style={{ color: colors.accent }}>
                      {t("web.dashboard.drill_down")} →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {selectedSite && (
        <section style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "20px 24px 0" }}>
            <h2 style={sectionTitleStyle}>
              {t("web.dashboard.site_equipment_title", { name: selectedSite.name })}
              {" — "}
              <Link href="/" style={{ color: colors.accent, textTransform: "none", fontWeight: 600 }}>
                {t("web.dashboard.back_to_portfolio")}
              </Link>
            </h2>
          </div>
          {selectedLocations.length === 0 ? (
            <p style={{ color: colors.textMuted, padding: "0 24px 20px" }}>
              {t("web.dashboard.no_equipment")}
            </p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={headerCellStyle}>{t("web.dashboard.code")}</th>
                  <th style={headerCellStyle}>{t("web.dashboard.name")}</th>
                  <th style={headerCellStyle}>{t("web.dashboard.status_column")}</th>
                  <th style={headerCellStyle}>{t("web.dashboard.alerts_column")}</th>
                </tr>
              </thead>
              <tbody>
                {selectedLocations.map((location) => {
                  const status = statusByLocation.get(location.id) ?? null;
                  const alertCount =
                    (alarmCountByLocation.get(location.id) ?? 0) +
                    (findingCountByLocation.get(location.id) ?? 0);
                  return (
                    <tr key={location.id}>
                      <td style={cellStyle}>
                        <Link href={`/registre/${location.id}`} style={{ color: colors.accent }}>
                          {location.code}
                        </Link>
                      </td>
                      <td style={cellStyle}>{location.name}</td>
                      <td style={cellStyle}>
                        <StatusCell status={status} locale={locale} t={t} />
                      </td>
                      <td style={cellStyle}>
                        {alertCount > 0
                          ? t("web.dashboard.alerts_open", { count: String(alertCount) })
                          : t("web.dashboard.alerts_none")}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      )}
    </main>
  );
}

function _countByLocation(ids: (string | null)[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const id of ids) {
    if (!id) continue;
    counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  return counts;
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ minWidth: 120 }}>
      <div style={{ fontSize: 28, fontWeight: 600, color: colors.textPrimary }}>{value}</div>
      <div style={{ color: colors.textMuted, fontSize: 13 }}>{label}</div>
    </div>
  );
}

function SeverityKpi({
  label,
  counts,
  t,
}: {
  label: string;
  counts: SeverityCounts;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const total = SEVERITIES.reduce((sum, severity) => sum + counts[severity], 0);
  return (
    <div style={{ minWidth: 160 }}>
      <div style={{ fontSize: 28, fontWeight: 600, color: colors.textPrimary }}>{total}</div>
      <div style={{ color: colors.textMuted, fontSize: 13, marginBottom: 4 }}>{label}</div>
      <SeverityBadges counts={counts} t={t} />
    </div>
  );
}

function SeverityBadges({
  counts,
  t,
}: {
  counts: SeverityCounts;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const present = SEVERITIES.filter((severity) => counts[severity] > 0);
  if (present.length === 0) {
    return <span style={{ color: colors.textMuted }}>{t("web.dashboard.alerts_none")}</span>;
  }
  return (
    <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
      {present.map((severity) => (
        <span key={severity} title={t(`severity.${severity}`)} style={badgeStyle(SEVERITY_COLOR[severity])}>
          {counts[severity]} {t(`severity.${severity}`)}
        </span>
      ))}
    </span>
  );
}

function DeviceBadges({
  counts,
  t,
}: {
  counts: { online: number; offline: number; unknown: number };
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const entries: { key: string; value: number }[] = [
    { key: "online", value: counts.online },
    { key: "offline", value: counts.offline },
    { key: "unknown", value: counts.unknown },
  ].filter((entry) => entry.value > 0);
  return (
    <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
      {entries.map((entry) => (
        <span
          key={entry.key}
          title={t(`communication_status.${entry.key}`)}
          style={badgeStyle(COMMUNICATION_COLOR[entry.key])}
        >
          {entry.value} {t(`communication_status.${entry.key}`)}
        </span>
      ))}
    </span>
  );
}

function StatusCell({
  status,
  locale,
  t,
}: {
  status: EquipmentStatus | null;
  locale: Locale;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  if (!status) {
    return <StatusBadge status="unknown" label={t("asset_status.unknown")} />;
  }
  const assetStatus = equipmentStatusToAssetStatus(status);
  const { key, params } = statusMessage(status);
  const rendered = Object.fromEntries(
    Object.entries(params ?? {}).map(([name, value]) => [
      name,
      name === "since" ? formatDateTime(locale, value) : t(value),
    ]),
  );
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <StatusBadge status={assetStatus} label={t(`asset_status.${assetStatus}`)} />
      <span style={{ color: colors.textMuted, fontSize: 13 }}>{t(key, rendered)}</span>
    </span>
  );
}
