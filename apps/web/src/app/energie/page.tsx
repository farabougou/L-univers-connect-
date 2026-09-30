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
import {
  countMetersWithoutData,
  summarizeEnergyByUnit,
  type PortfolioEnergyMeter,
} from "@/lib/energy";
import { getLocale, getTranslator } from "@/lib/i18n";
import { formatDate, formatNumber } from "@/i18n/translator";

/**
 * Page Energy (directive UI/dashboard, section 36 point 6) : le détail par
 * compteur que le bloc « Énergie » du Global Command Center résume (total
 * par unité, tendance) sans jamais lister les compteurs eux-mêmes — ici
 * chaque compteur, avec un lien direct vers la fiche équipement où vivent
 * déjà la comparaison à une baseline et l'historique complet
 * (`app/energy/normalization.py`, section « Performance énergétique »).
 * Aucun nouvel endpoint : réutilise GET /energy/portfolio-summary, déjà
 * construit pour le tableau de bord (app/energy/aggregation.py).
 */

type FunctionalLocation = { id: string; code: string; name: string };

export default async function EnergyPage() {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();
  const locale = await getLocale();

  const [energyResponse, locationsResponse] = await Promise.all([
    apiFetch("/energy/portfolio-summary", accessToken),
    apiFetch("/functional-locations", accessToken),
  ]);
  const energySummary: { reference_date: string; meters: PortfolioEnergyMeter[] } | null =
    energyResponse.ok ? await energyResponse.json() : null;
  const locations: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];
  const locationById = new Map(locations.map((location) => [location.id, location]));

  const meters = energySummary?.meters ?? [];
  const byUnit = summarizeEnergyByUnit(meters);
  const metersWithoutData = countMetersWithoutData(meters);

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>{t("web.energy_page.title")}</h1>

      {meters.length === 0 ? (
        <section style={cardStyle}>
          <p style={{ color: colors.textMuted }}>{t("web.energy_page.no_meters")}</p>
        </section>
      ) : (
        <>
          <section style={{ ...cardStyle, marginBottom: 24 }}>
            <h2 style={sectionTitleStyle}>{t("web.energy_page.summary_title")}</h2>
            <p style={{ color: colors.textMuted, fontSize: 13, marginBottom: 16 }}>
              {t("web.dashboard.energy_reference_date", {
                date: energySummary ? formatDate(locale, energySummary.reference_date) : "",
              })}
            </p>
            <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
              {byUnit.map((summary) => (
                <div key={summary.unit}>
                  <div style={{ fontSize: 28, fontWeight: 600, color: colors.textPrimary }}>
                    {summary.totalConsumption === null
                      ? t("web.dashboard.energy_unavailable")
                      : formatNumber(locale, summary.totalConsumption)}
                  </div>
                  <div style={{ color: colors.textMuted, fontSize: 13 }}>
                    {t("web.dashboard.energy_consumption_label", { unit: summary.unit })}
                  </div>
                </div>
              ))}
            </div>
            {metersWithoutData > 0 && (
              <p style={{ color: colors.textMuted, fontSize: 12, marginTop: 16 }}>
                {t("web.dashboard.energy_meters_without_data", { count: metersWithoutData })}
              </p>
            )}
          </section>

          <section style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
            <div style={{ padding: "20px 24px 0" }}>
              <h2 style={sectionTitleStyle}>{t("web.energy_page.meters_title")}</h2>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={headerCellStyle}>{t("mobile.passport.equipment")}</th>
                  <th style={headerCellStyle}>{t("web.energy_page.col_unit")}</th>
                  <th style={headerCellStyle}>{t("web.energy_page.col_consumption")}</th>
                  <th style={headerCellStyle}>{t("web.energy_page.col_previous")}</th>
                  <th style={headerCellStyle} />
                </tr>
              </thead>
              <tbody>
                {meters.map((meter) => {
                  const location = locationById.get(meter.functional_location_id);
                  return (
                    <tr key={meter.point_id}>
                      <td style={cellStyle}>
                        {location ? (
                          <Link
                            href={`/registre/${location.id}`}
                            style={{ color: colors.accent }}
                          >
                            {location.code} — {location.name}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td style={cellStyle}>{meter.unit}</td>
                      <td style={cellStyle}>
                        {meter.consumption === null
                          ? t("web.dashboard.energy_unavailable")
                          : formatNumber(locale, meter.consumption)}
                      </td>
                      <td style={cellStyle}>
                        {meter.previous_consumption === null
                          ? t("web.dashboard.energy_unavailable")
                          : formatNumber(locale, meter.previous_consumption)}
                      </td>
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
          </section>
        </>
      )}
    </main>
  );
}
