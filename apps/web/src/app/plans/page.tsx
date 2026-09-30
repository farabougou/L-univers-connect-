import Link from "next/link";

import { apiFetch, requireAccessToken } from "@/lib/api";
import {
  cardStyle,
  cellStyle,
  colors,
  headerCellStyle,
  pageContainerStyle,
  sectionTitleStyle,
} from "@/lib/formStyles";
import { getLocale, getTranslator } from "@/lib/i18n";
import { formatDateTime } from "@/i18n/translator";

/**
 * Page Spatial/BIM (directive UI/dashboard, section 36, point 12) :
 * dernière version de chaque plan 2D du portefeuille, avec le site et
 * l'espace visés, en une seule vue plutôt que d'ouvrir chaque espace une à
 * une depuis /registre. Nouvel endpoint bulk `GET /floor-plans/portfolio`
 * (`app/floor_plans.py::list_portfolio_floor_plans`), même motif
 * `DISTINCT ON` que la santé des actifs, la chronologie et la télémétrie.
 *
 * L'envoi d'un nouveau plan et l'import IFC restent sur /registre (ADR 011,
 * étapes S3 et section 2) : cette page complète, elle ne duplique pas — le
 * clic « Ouvrir » ci-dessous mène à l'éditeur de placements déjà existant
 * (/registre/plans/[floorPlanId]).
 */

type PortfolioFloorPlan = {
  id: string;
  space_id: string;
  space_code: string;
  space_name: string;
  site_id: string;
  site_name: string;
  version: number;
  filename: string;
  content_type: string;
  download_url: string;
  uploaded_by: string;
  uploaded_at: string;
  validated_placement_count: number;
};

export default async function SpatialPage() {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();
  const locale = await getLocale();

  const response = await apiFetch("/floor-plans/portfolio", accessToken);
  const plans: PortfolioFloorPlan[] = response.ok ? await response.json() : [];

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>
        {t("web.spatial_page.title")}
      </h1>

      {plans.length === 0 ? (
        <section style={cardStyle}>
          <p style={{ color: colors.textMuted }}>
            {t("web.spatial_page.no_plans")}
          </p>
          <p style={{ marginTop: 8 }}>
            <Link href="/registre" style={{ color: colors.accent }}>
              {t("web.spatial_page.go_to_registry")}
            </Link>
          </p>
        </section>
      ) : (
        <section style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "20px 24px 0" }}>
            <h2 style={sectionTitleStyle}>
              {t("web.spatial_page.plans_title")}
            </h2>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={headerCellStyle}>
                  {t("web.spatial_page.col_site")}
                </th>
                <th style={headerCellStyle}>
                  {t("web.spatial_page.col_space")}
                </th>
                <th style={headerCellStyle}>
                  {t("web.spatial_page.col_version")}
                </th>
                <th style={headerCellStyle}>
                  {t("web.spatial_page.col_placements")}
                </th>
                <th style={headerCellStyle}>
                  {t("web.documents_page.col_uploaded")}
                </th>
                <th style={headerCellStyle} />
              </tr>
            </thead>
            <tbody>
              {plans.map((plan) => (
                <tr key={plan.id}>
                  <td style={cellStyle}>{plan.site_name}</td>
                  <td style={cellStyle}>
                    <Link
                      href={`/registre?space=${plan.space_id}`}
                      style={{ color: colors.accent }}
                    >
                      {plan.space_code} — {plan.space_name}
                    </Link>
                  </td>
                  <td style={cellStyle}>{plan.version}</td>
                  <td style={cellStyle}>{plan.validated_placement_count}</td>
                  <td style={cellStyle}>
                    {t("web.registre.floor_plans_uploaded_by", {
                      actor: plan.uploaded_by,
                      date: formatDateTime(locale, plan.uploaded_at),
                    })}
                  </td>
                  <td style={cellStyle}>
                    <Link
                      href={`/registre/plans/${plan.id}`}
                      style={{ color: colors.accent }}
                    >
                      {t("web.spatial_page.open_link")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
