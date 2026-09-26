import Link from "next/link";
import { redirect } from "next/navigation";

import { apiFetch, requireAccessToken } from "@/lib/api";
import { getLocale, getTranslator } from "@/lib/i18n";
import { type EquipmentStatus, statusMessage } from "@/lib/passport";
import { type Locale, formatDateTime } from "@/i18n/translator";

type Me = {
  sub: string;
  tenant_id: string;
  roles: string[];
};

type FunctionalLocation = {
  id: string;
  code: string;
  name: string;
};

type Alert = { functional_location_id?: string; subject_node_id?: string };

async function _openCount(
  accessToken: string,
  path: string,
  locationField: keyof Alert,
): Promise<Map<string, number>> {
  const counts = new Map<string, number>();
  for (const handlingStatus of ["open", "in_progress"]) {
    const response = await apiFetch(`${path}?handling_status=${handlingStatus}`, accessToken);
    if (!response.ok) continue;
    const rows: Alert[] = await response.json();
    for (const row of rows) {
      const locationId = row[locationField];
      if (!locationId) continue;
      counts.set(locationId, (counts.get(locationId) ?? 0) + 1);
    }
  }
  return counts;
}

export default async function DashboardPage() {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();
  const locale = await getLocale();

  const [meResponse, locationsResponse] = await Promise.all([
    apiFetch("/me", accessToken),
    apiFetch("/functional-locations", accessToken),
  ]);

  if (!meResponse.ok) {
    redirect("/login");
  }

  const me: Me = await meResponse.json();
  const locations: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];

  // Le tableau de bord montre l'état réel de la vraie chaîne (télémétrie,
  // alarmes, constats), jamais des valeurs figées : trois appels tenant
  // entiers (pas un par équipement) pour les alertes, puis un appel léger
  // par équipement pour son état de fonctionnement/communication.
  const [alarmCounts, findingCounts, statuses] = await Promise.all([
    _openCount(accessToken, "/alarms", "functional_location_id"),
    _openCount(accessToken, "/findings", "subject_node_id"),
    Promise.all(
      locations.map(async (location) => {
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
    <main style={{ maxWidth: 900, margin: "40px auto", padding: "0 16px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>{t("common.app_name")}</h1>
        <a href="/api/auth/logout">{t("common.sign_out")}</a>
      </header>
      <p>{t("web.dashboard.signed_in_as", { user: me.sub, roles: me.roles.join(", ") })}</p>

      <nav style={{ margin: "16px 0", display: "flex", flexDirection: "column", gap: 8 }}>
        <Link href="/ordres-de-travail">{t("web.dashboard.work_orders_link")} →</Link>
        <Link href="/registre">{t("web.dashboard.registry_link")} →</Link>
      </nav>

      <h2>{t("web.dashboard.equipment")}</h2>
      {locations.length === 0 ? (
        <p>{t("web.dashboard.no_equipment")}</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
                {t("web.dashboard.code")}
              </th>
              <th style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
                {t("web.dashboard.name")}
              </th>
              <th style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
                {t("web.dashboard.status_column")}
              </th>
              <th style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
                {t("web.dashboard.alerts_column")}
              </th>
            </tr>
          </thead>
          <tbody>
            {locations.map((location) => {
              const status = statusByLocation.get(location.id) ?? null;
              const alertCount =
                (alarmCounts.get(location.id) ?? 0) + (findingCounts.get(location.id) ?? 0);
              return (
                <tr key={location.id}>
                  <td style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>
                    <Link href={`/registre/${location.id}`}>{location.code}</Link>
                  </td>
                  <td style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>
                    {location.name}
                  </td>
                  <td style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>
                    <StatusCell status={status} locale={locale} t={t} />
                  </td>
                  <td style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>
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
    </main>
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
