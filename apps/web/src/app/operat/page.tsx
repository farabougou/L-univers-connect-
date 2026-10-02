import Link from "next/link";

import { apiFetch, requireAccessToken } from "@/lib/api";
import {
  cardStyle,
  cellStyle,
  colors,
  fieldStyle,
  headerCellStyle,
  labelStyle,
  pageContainerStyle,
  sectionTitleStyle,
  submitStyle,
  tableScrollStyle,
} from "@/lib/formStyles";
import { getTranslator } from "@/lib/i18n";
import { canManage as computeCanManage, type Me } from "@/lib/roles";

import { createOperatDeclaration } from "./actions";

/**
 * Page OPERAT / Éco Énergie Tertiaire (docs/regulatory/01-operat-eco-energie-tertiaire.md,
 * directive de Mohamed du 02/10/2026) : une déclaration par site et par
 * année de référence, regroupées ici par site plutôt qu'une page par site —
 * un seul appel bulk (`GET /operat-declarations/portfolio`), comme les
 * autres pages portefeuille (Énergie, Automatisation).
 */

type Site = { id: string; name: string };

type OperatDeclaration = {
  id: string;
  site_id: string;
  reference_year: number;
  status: "draft" | "ready" | "submitted";
  floor_area_m2: number | null;
  activity_category: string | null;
  electricity_kwh: number | null;
};

export default async function OperatPage() {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();

  const [sitesResponse, declarationsResponse, meResponse] = await Promise.all([
    apiFetch("/sites", accessToken),
    apiFetch("/operat-declarations/portfolio", accessToken),
    apiFetch("/me", accessToken),
  ]);
  const sites: Site[] = sitesResponse.ok ? await sitesResponse.json() : [];
  const declarations: OperatDeclaration[] = declarationsResponse.ok
    ? await declarationsResponse.json()
    : [];
  const me: Me = meResponse.ok ? await meResponse.json() : { roles: [] };
  const canManage = computeCanManage(me);

  const declarationsBySite = new Map<string, OperatDeclaration[]>();
  for (const declaration of declarations) {
    const list = declarationsBySite.get(declaration.site_id) ?? [];
    list.push(declaration);
    declarationsBySite.set(declaration.site_id, list);
  }
  const currentYear = new Date().getFullYear();

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>{t("web.operat_page.title")}</h1>
      <p style={{ color: colors.textMuted, marginBottom: 20, maxWidth: 720 }}>
        {t("web.operat_page.intro")}
      </p>

      {sites.length === 0 ? (
        <section style={cardStyle}>
          <p style={{ color: colors.textMuted }}>{t("web.operat_page.no_sites")}</p>
        </section>
      ) : (
        sites.map((site) => {
          const siteDeclarations = declarationsBySite.get(site.id) ?? [];
          const hasCurrentYear = siteDeclarations.some(
            (declaration) => declaration.reference_year === currentYear,
          );
          return (
            <section key={site.id} style={{ ...cardStyle, marginBottom: 20 }}>
              <h2 style={sectionTitleStyle}>{site.name}</h2>

              {siteDeclarations.length > 0 && (
                <div style={tableScrollStyle}>
                  <table
                    className="responsive-table"
                    style={{ width: "100%", borderCollapse: "collapse", marginBottom: 12 }}
                  >
                    <thead>
                      <tr>
                        <th style={headerCellStyle}>{t("web.operat_page.col_year")}</th>
                        <th style={headerCellStyle}>{t("web.operat_page.col_status")}</th>
                        <th style={headerCellStyle}>{t("web.operat_page.col_surface")}</th>
                        <th style={headerCellStyle}>{t("web.operat_page.col_activity")}</th>
                        <th style={headerCellStyle}>{t("web.operat_page.col_electricity")}</th>
                        <th style={headerCellStyle} />
                      </tr>
                    </thead>
                    <tbody>
                      {siteDeclarations.map((declaration) => (
                        <tr key={declaration.id}>
                          <td data-label={t("web.operat_page.col_year")} style={cellStyle}>
                            {declaration.reference_year}
                          </td>
                          <td data-label={t("web.operat_page.col_status")} style={cellStyle}>
                            {t(`web.operat_page.status.${declaration.status}`)}
                          </td>
                          <td data-label={t("web.operat_page.col_surface")} style={cellStyle}>
                            {declaration.floor_area_m2 ?? "—"}
                          </td>
                          <td data-label={t("web.operat_page.col_activity")} style={cellStyle}>
                            {declaration.activity_category ?? "—"}
                          </td>
                          <td data-label={t("web.operat_page.col_electricity")} style={cellStyle}>
                            {declaration.electricity_kwh ?? "—"}
                          </td>
                          <td style={cellStyle}>
                            {canManage && (
                              <Link href={`/operat/${declaration.id}`} style={{ color: colors.accent }}>
                                {t("web.operat_page.edit")}
                              </Link>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {canManage && !hasCurrentYear && (
                <form action={createOperatDeclaration} style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
                  <input type="hidden" name="site_id" value={site.id} />
                  <label style={{ ...labelStyle, marginTop: 0 }}>
                    {t("web.operat_page.new_declaration_year")}
                    <input
                      type="number"
                      name="reference_year"
                      defaultValue={currentYear}
                      min={2020}
                      max={2100}
                      required
                      style={fieldStyle}
                    />
                  </label>
                  <button type="submit" style={submitStyle}>
                    {t("web.operat_page.new_declaration_submit")}
                  </button>
                </form>
              )}
            </section>
          );
        })
      )}
    </main>
  );
}
