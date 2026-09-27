import Link from "next/link";
import { redirect } from "next/navigation";

import { apiFetch, requireAccessToken } from "@/lib/api";
import { cellStyle, headerCellStyle } from "@/lib/formStyles";
import { getLocale, getTranslator } from "@/lib/i18n";
import { type EquipmentStatus, statusMessage } from "@/lib/passport";
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
    _openSignals<Alarm>(accessToken, "/alarms"),
    _openSignals<Finding>(accessToken, "/findings"),
  ]);

  const locationsBySite = new Map<string, FunctionalLocation[]>();
  for (const location of locations) {
    const list = locationsBySite.get(location.site_id) ?? [];
    list.push(location);
    locationsBySite.set(location.site_id, list);
  }

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
    <main style={{ maxWidth: 1000, margin: "40px auto", padding: "0 16px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>{t("common.app_name")}</h1>
        <a href="/api/auth/logout">{t("common.sign_out")}</a>
      </header>
      <p>{t("web.dashboard.signed_in_as", { user: me.sub, roles: me.roles.join(", ") })}</p>

      <nav style={{ margin: "16px 0", display: "flex", flexDirection: "column", gap: 8 }}>
        <Link href="/ordres-de-travail">{t("web.dashboard.work_orders_link")} →</Link>
        <Link href="/registre">{t("web.dashboard.registry_link")} →</Link>
      </nav>

      <h2>{t("web.dashboard.portfolio_title")}</h2>
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", margin: "8px 0 24px" }}>
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

      {sites.length === 0 ? (
        <p>{t("web.dashboard.no_sites")}</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 24 }}>
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
                <td style={cellStyle}>{entry.site.name}</td>
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
                      <span style={{ color: "#9ca3af" }}>{t("web.dashboard.edge_none")}</span>
                    )}
                  </td>
                )}
                <td style={cellStyle}>
                  <Link href={`/?site=${entry.site.id}`}>{t("web.dashboard.drill_down")} →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selectedSite && (
        <section>
          <h2>
            {t("web.dashboard.site_equipment_title", { name: selectedSite.name })}
            {" — "}
            <Link href="/">{t("web.dashboard.back_to_portfolio")}</Link>
          </h2>
          {selectedLocations.length === 0 ? (
            <p>{t("web.dashboard.no_equipment")}</p>
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
                        <Link href={`/registre/${location.id}`}>{location.code}</Link>
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
      <div style={{ fontSize: 28, fontWeight: 600 }}>{value}</div>
      <div style={{ color: "#6b7280", fontSize: 13 }}>{label}</div>
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
      <div style={{ fontSize: 28, fontWeight: 600 }}>{total}</div>
      <div style={{ color: "#6b7280", fontSize: 13, marginBottom: 4 }}>{label}</div>
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
    return <span style={{ color: "#9ca3af" }}>{t("web.dashboard.alerts_none")}</span>;
  }
  return (
    <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
      {present.map((severity) => (
        <span
          key={severity}
          title={t(`severity.${severity}`)}
          style={{
            color: "white",
            background: SEVERITY_COLOR[severity],
            borderRadius: 4,
            padding: "1px 6px",
            fontSize: 12,
          }}
        >
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
          style={{
            color: "white",
            background: COMMUNICATION_COLOR[entry.key],
            borderRadius: 4,
            padding: "1px 6px",
            fontSize: 12,
          }}
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
  if (!status) return <span>—</span>;
  const { key, params } = statusMessage(status);
  const rendered = Object.fromEntries(
    Object.entries(params ?? {}).map(([name, value]) => [
      name,
      name === "since" ? formatDateTime(locale, value) : t(value),
    ]),
  );
  return <span>{t(key, rendered)}</span>;
}
