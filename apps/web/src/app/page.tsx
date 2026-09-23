import Link from "next/link";
import { redirect } from "next/navigation";

import { apiFetch, requireAccessToken } from "@/lib/api";
import { getTranslator } from "@/lib/i18n";

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

export default async function DashboardPage() {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();

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

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
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
            </tr>
          </thead>
          <tbody>
            {locations.map((location) => (
              <tr key={location.id}>
                <td style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>
                  {location.code}
                </td>
                <td style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>
                  {location.name}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
