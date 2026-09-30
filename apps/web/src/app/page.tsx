import Link from "next/link";
import { redirect } from "next/navigation";

import { BrandMark } from "@/components/BrandMark";
import { StatusBadge, equipmentStatusToAssetStatus } from "@/components/StatusBadge";
import { apiFetch, requireAccessToken } from "@/lib/api";
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
import { getLocale, getTranslator } from "@/lib/i18n";
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
  aggregatePortfolio,
  prioritizeAlarms,
} from "@/lib/portfolio";
import { type Locale, formatDateTime } from "@/i18n/translator";

type Me = {
  sub: string;
  tenant_id: string;
  roles: string[];
};

type FunctionalLocation = PortfolioLocation & { code: string; name: string };

const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "#dc2626",
  major: "#ea580c",
  warning: "#d97706",
  info: "#6b7280",
};

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

type AlarmDetail = Alarm & {
  id: string;
  message: string;
  ack_state: string;
  raised_at: string;
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

  const [meResponse, sitesResponse, locationsResponse, workOrdersResponse, devicesResponse] =
    await Promise.all([
      apiFetch("/me", accessToken),
      apiFetch("/sites", accessToken),
      apiFetch("/functional-locations", accessToken),
      apiFetch("/work-orders", accessToken),
      apiFetch("/devices", accessToken),
    ]);

  if (!meResponse.ok) {
    redirect("/login");
  }

  const me: Me = await meResponse.json();
  const sites: Site[] = sitesResponse.ok ? await sitesResponse.json() : [];
  const locations: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];
  const workOrders: WorkOrder[] = workOrdersResponse.ok ? await workOrdersResponse.json() : [];
  // Réservé aux rôles de gestion côté API (GET /devices) : un rôle terrain
  // voit le reste de la vue d'ensemble sans cette colonne, jamais une
  // colonne à zéro fabriquée pour combler l'absence de droit.
  const devices: Device[] | null = devicesResponse.ok ? await devicesResponse.json() : null;

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
        <Link href="/edge" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.edge_link")} →
        </Link>
        <Link href="/ordres-de-travail" style={{ color: colors.accent, fontWeight: 600 }}>
          {t("web.dashboard.work_orders_link")} →
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
