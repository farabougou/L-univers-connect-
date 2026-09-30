import Link from "next/link";

import { apiFetch, requireAccessToken } from "@/lib/api";
import {
  badgeStyle,
  cardStyle,
  cellStyle,
  colors,
  headerCellStyle,
  pageContainerStyle,
  sectionTitleStyle,
} from "@/lib/formStyles";
import { getLocale, getTranslator } from "@/lib/i18n";
import { formatDateTime } from "@/i18n/translator";

type Site = { id: string; name: string };

type Device = {
  id: string;
  device_id: string;
  site_id: string | null;
  credential_type: string;
  status: string;
  communication_status: string;
  last_seen_at: string | null;
};

const COMMUNICATION_COLOR: Record<string, string> = {
  online: "#16a34a",
  offline: "#dc2626",
  unreachable: "#dc2626",
  unknown: "#9ca3af",
};

const ACCOUNT_COLOR: Record<string, string> = {
  active: "#16a34a",
  revoked: "#6b7280",
};

export default async function EdgeConnectivityPage() {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();
  const locale = await getLocale();

  const [sitesResponse, devicesResponse] = await Promise.all([
    apiFetch("/sites", accessToken),
    apiFetch("/devices", accessToken),
  ]);

  const sites: Site[] = sitesResponse.ok ? await sitesResponse.json() : [];
  // Réservé aux rôles de gestion côté API — un rôle terrain voit un message
  // explicite plutôt qu'une liste vide qui laisserait croire qu'il n'y a
  // aucune passerelle.
  const accessDenied = devicesResponse.status === 403;
  const devices: Device[] = devicesResponse.ok ? await devicesResponse.json() : [];

  const siteName = (id: string | null) =>
    (id ? sites.find((site) => site.id === id)?.name : null) ?? t("web.edge.unassigned_site");

  const devicesBySite = new Map<string, Device[]>();
  for (const device of devices) {
    const key = device.site_id ?? "__unassigned__";
    const list = devicesBySite.get(key) ?? [];
    list.push(device);
    devicesBySite.set(key, list);
  }
  const groups = [...devicesBySite.entries()].sort(([a], [b]) =>
    siteName(a === "__unassigned__" ? null : a).localeCompare(
      siteName(b === "__unassigned__" ? null : b),
    ),
  );

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent, fontWeight: 600 }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 4px" }}>{t("web.edge.title")}</h1>
      <p style={{ color: colors.textMuted, fontSize: 14, marginBottom: 24 }}>
        {t("web.edge.intro")}
      </p>

      {accessDenied ? (
        <section style={cardStyle}>
          <p style={{ color: colors.textMuted }}>{t("web.edge.access_denied")}</p>
        </section>
      ) : devices.length === 0 ? (
        <section style={cardStyle}>
          <p style={{ color: colors.textMuted }}>{t("web.edge.no_devices")}</p>
        </section>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {groups.map(([key, group]) => (
            <section key={key} style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
              <div style={{ padding: "20px 24px 0" }}>
                <h2 style={sectionTitleStyle}>
                  {siteName(key === "__unassigned__" ? null : key)}
                </h2>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={headerCellStyle}>{t("web.edge.col_device")}</th>
                    <th style={headerCellStyle}>{t("web.edge.col_account")}</th>
                    <th style={headerCellStyle}>{t("web.edge.col_communication")}</th>
                    <th style={headerCellStyle}>{t("web.edge.col_credential")}</th>
                    <th style={headerCellStyle}>{t("web.edge.col_last_seen")}</th>
                  </tr>
                </thead>
                <tbody>
                  {group.map((device) => (
                    <tr key={device.id}>
                      <td style={{ ...cellStyle, fontWeight: 600 }}>{device.device_id}</td>
                      <td style={cellStyle}>
                        <span style={badgeStyle(ACCOUNT_COLOR[device.status] ?? "#6b7280")}>
                          {t(`device_status.${device.status}`)}
                        </span>
                      </td>
                      <td style={cellStyle}>
                        <span
                          style={badgeStyle(
                            COMMUNICATION_COLOR[device.communication_status] ?? "#9ca3af",
                          )}
                        >
                          {t(`communication_status.${device.communication_status}`)}
                        </span>
                      </td>
                      <td style={cellStyle}>{t(`credential_type.${device.credential_type}`)}</td>
                      <td style={cellStyle}>
                        {device.last_seen_at
                          ? formatDateTime(locale, device.last_seen_at)
                          : t("web.edge.last_seen_never")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
