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
import { formatDateTime, formatNumber } from "@/i18n/translator";

/**
 * Page Telemetry (directive UI/dashboard, section 36 point 9) : la dernière
 * valeur de chaque point validé du portefeuille, en une seule vue plutôt
 * que d'ouvrir chaque fiche équipement une à une. Nouvel endpoint bulk
 * (GET /telemetry/portfolio-latest, app/telemetry_overview.py) plutôt
 * qu'un appel par point depuis le navigateur (directive, section 29).
 *
 * Ne recalcule jamais le score de confiance complet
 * (GET /points/{id}/trust, plusieurs requêtes par point) : seulement la
 * fraîcheur simple (périmé ou non selon l'intervalle attendu) — pour le
 * détail complet d'un point, la fiche équipement reste la référence.
 */

type TelemetryEntry = {
  point_id: string;
  functional_location_id: string | null;
  code: string;
  name: string;
  point_class: string | null;
  unit: string | null;
  value: number | null;
  measured_at: string | null;
  stale: boolean | null;
};

type FunctionalLocation = { id: string; code: string; name: string };

export default async function TelemetryPage() {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();
  const locale = await getLocale();

  const [telemetryResponse, locationsResponse] = await Promise.all([
    apiFetch("/telemetry/portfolio-latest", accessToken),
    apiFetch("/functional-locations", accessToken),
  ]);
  const entries: TelemetryEntry[] = telemetryResponse.ok ? await telemetryResponse.json() : [];
  const locations: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];
  const locationById = new Map(locations.map((location) => [location.id, location]));

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>{t("web.telemetry_page.title")}</h1>

      {entries.length === 0 ? (
        <section style={cardStyle}>
          <p style={{ color: colors.textMuted }}>{t("web.telemetry_page.no_points")}</p>
        </section>
      ) : (
        <section style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "20px 24px 0" }}>
            <h2 style={sectionTitleStyle}>{t("web.telemetry_page.points_title")}</h2>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={headerCellStyle}>{t("mobile.passport.equipment")}</th>
                <th style={headerCellStyle}>{t("web.telemetry_page.col_point")}</th>
                <th style={headerCellStyle}>{t("web.telemetry_page.col_class")}</th>
                <th style={headerCellStyle}>{t("web.telemetry_page.col_value")}</th>
                <th style={headerCellStyle}>{t("web.dashboard.col_since")}</th>
                <th style={headerCellStyle} />
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                const location = entry.functional_location_id
                  ? locationById.get(entry.functional_location_id)
                  : undefined;
                return (
                  <tr key={entry.point_id}>
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
                      {entry.code} — {entry.name}
                    </td>
                    <td style={cellStyle}>
                      {entry.point_class ? t(`point_class.${entry.point_class}`) : "—"}
                    </td>
                    <td style={cellStyle}>
                      {entry.value === null
                        ? t("web.telemetry_page.no_value")
                        : `${formatNumber(locale, entry.value)}${entry.unit ? ` ${entry.unit}` : ""}`}
                    </td>
                    <td style={cellStyle}>
                      {entry.measured_at
                        ? formatDateTime(locale, entry.measured_at)
                        : t("web.telemetry_page.never_measured")}
                    </td>
                    <td style={cellStyle}>
                      {entry.stale && (
                        <span style={badgeStyle("#d97706")}>{t("web.telemetry_page.stale")}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
