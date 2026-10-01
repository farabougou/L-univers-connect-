import Link from "next/link";

import { apiFetch, requireAccessToken } from "@/lib/api";
import {
  cardStyle,
  cellStyle,
  colors,
  headerCellStyle,
  pageContainerStyle,
  sectionTitleStyle,
  tableScrollStyle,
} from "@/lib/formStyles";
import { getLocale, getTranslator } from "@/lib/i18n";
import { formatDate, formatNumber } from "@/i18n/translator";
import { canManage as computeCanManage, type Me } from "@/lib/roles";

import { endDesiredState } from "./actions";

/**
 * Page Automation (directive UI/dashboard, section 36, point 13) : toutes
 * les attentes déclarées actives du portefeuille (app/desired_states.py),
 * en une seule vue plutôt que d'ouvrir chaque fiche équipement une à une.
 * Nouvel endpoint bulk `GET /desired-states/portfolio-active`.
 *
 * Ce que cette page montre n'est PAS une automatisation qui agit : c'est
 * une attente déclarée par un humain, comparée à l'état réel pour détecter
 * une dérive (règle non négociable 1 — aucune commande vers un équipement
 * réel). La seule capacité d'écriture du dépôt reste réservée à l'appareil
 * explicitement simulé (device_type "simulated_relay",
 * app/connectors/simulated_actuator.py), déjà exposée sur la fiche
 * équipement — jamais reproduite ici.
 */

type PortfolioDesiredState = {
  id: string;
  point_id: string;
  point_code: string;
  point_name: string;
  point_unit: string | null;
  functional_location_id: string | null;
  value: number;
  daily_start: string | null;
  daily_end: string | null;
  timezone: string | null;
  reason: string;
  created_by: string;
  valid_from: string;
};

export default async function AutomationPage() {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();
  const locale = await getLocale();

  const [statesResponse, meResponse] = await Promise.all([
    apiFetch("/desired-states/portfolio-active", accessToken),
    apiFetch("/me", accessToken),
  ]);
  const states: PortfolioDesiredState[] = statesResponse.ok
    ? await statesResponse.json()
    : [];
  const me: Me = meResponse.ok ? await meResponse.json() : { roles: [] };
  const canManage = computeCanManage(me);

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>
        {t("web.automation_page.title")}
      </h1>
      <p style={{ color: colors.textMuted, marginBottom: 20, maxWidth: 720 }}>
        {t("web.automation_page.intro")}
      </p>

      {states.length === 0 ? (
        <section style={cardStyle}>
          <p style={{ color: colors.textMuted }}>
            {t("web.automation_page.no_states")}
          </p>
        </section>
      ) : (
        <section style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "20px 24px 0" }}>
            <h2 style={sectionTitleStyle}>
              {t("web.automation_page.states_title")}
            </h2>
          </div>
          <div style={tableScrollStyle}>
            <table
              className="responsive-table"
              style={{ width: "100%", borderCollapse: "collapse" }}
            >
              <thead>
                <tr>
                  <th style={headerCellStyle}>
                    {t("mobile.passport.equipment")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.telemetry_page.col_point")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.automation_page.col_expected")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.automation_page.col_window")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.automation_page.col_reason")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.dashboard.col_since")}
                  </th>
                  <th style={headerCellStyle} />
                </tr>
              </thead>
              <tbody>
                {states.map((state) => (
                  <tr key={state.id}>
                    <td
                      data-label={t("mobile.passport.equipment")}
                      style={cellStyle}
                    >
                      {state.functional_location_id ? (
                        <Link
                          href={`/registre/${state.functional_location_id}`}
                          style={{ color: colors.accent }}
                        >
                          {t("web.spatial_page.open_link")}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td
                      data-label={t("web.telemetry_page.col_point")}
                      style={cellStyle}
                    >
                      {state.point_code} — {state.point_name}
                    </td>
                    <td
                      data-label={t("web.automation_page.col_expected")}
                      style={cellStyle}
                    >
                      {formatNumber(locale, state.value)}
                      {state.point_unit ? ` ${state.point_unit}` : ""}
                    </td>
                    <td
                      data-label={t("web.automation_page.col_window")}
                      style={cellStyle}
                    >
                      {state.daily_start && state.daily_end
                        ? `${state.daily_start}–${state.daily_end} (${state.timezone})`
                        : "—"}
                    </td>
                    <td
                      data-label={t("web.automation_page.col_reason")}
                      style={cellStyle}
                    >
                      {state.reason}
                    </td>
                    <td
                      data-label={t("web.dashboard.col_since")}
                      style={cellStyle}
                    >
                      {formatDate(locale, state.valid_from, null)}
                    </td>
                    <td style={cellStyle}>
                      {canManage && (
                        <form action={endDesiredState}>
                          <input
                            type="hidden"
                            name="desired_state_id"
                            value={state.id}
                          />
                          <button type="submit">
                            {t("web.registre.end_desired_state")}
                          </button>
                        </form>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
