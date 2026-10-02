import Link from "next/link";

import { SignalActions } from "@/components/SignalActions";
import { apiFetch, requireAccessToken } from "@/lib/api";
import {
  badgeStyle,
  cardStyle,
  cellStyle,
  colors,
  headerCellStyle,
  pageContainerStyle,
  sectionTitleStyle,
  tableScrollStyle,
} from "@/lib/formStyles";
import { errorMessage, getLocale, getTranslator } from "@/lib/i18n";
import {
  type Severity,
  SEVERITY_COLOR,
  prioritizeAlarms,
} from "@/lib/portfolio";
import { formatDateTime } from "@/i18n/translator";

import {
  acknowledgeSignal,
  clearAlarm,
  confirmFinding,
  setHandling,
} from "./actions";

/**
 * Alarms & Incidents (directive UI/dashboard, section 36 point 4) : le
 * portefeuille complet des alarmes et constats ouverts, pas seulement les 8
 * premières déjà montrées par le bloc « Alarmes prioritaires » du Global
 * Command Center, et avec les constats en plus (absents de ce bloc). Modèle
 * State/Event/Policy/Alert/Incident distinct (directive, section 24) :
 * alarmes et constats restent deux tables séparées, avec leurs propres
 * actions, jamais fondues en une seule notion générique.
 */

type AlarmDetail = {
  id: string;
  functional_location_id: string | null;
  severity: string;
  message: string;
  condition_state: string;
  ack_state: string;
  handling_status: string;
  raised_at: string;
};

type FindingDetail = {
  id: string;
  subject_node_id: string;
  kind: string;
  severity: string;
  title: string;
  certainty: string;
  condition_state: string;
  ack_state: string;
  handling_status: string;
  last_seen_at: string;
};

type FunctionalLocation = { id: string; code: string; name: string };

async function _openSignals<T extends { severity: string }>(
  accessToken: string,
  path: string,
): Promise<T[]> {
  const results = await Promise.all(
    ["open", "in_progress"].map(async (handlingStatus) => {
      const response = await apiFetch(
        `${path}?handling_status=${handlingStatus}`,
        accessToken,
      );
      return response.ok ? ((await response.json()) as T[]) : [];
    }),
  );
  return results.flat();
}

export default async function AlarmsPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();
  const locale = await getLocale();
  const { error: errorCode } = await searchParams;
  const error = errorCode ? errorMessage(locale, errorCode) : null;

  const [alarms, findings, locationsResponse] = await Promise.all([
    _openSignals<AlarmDetail>(accessToken, "/alarms"),
    _openSignals<FindingDetail>(accessToken, "/findings"),
    apiFetch("/functional-locations", accessToken),
  ]);
  const locations: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];
  const locationById = new Map(
    locations.map((location) => [location.id, location]),
  );

  // Même tri que le bloc « Alarmes prioritaires » du Global Command Center
  // (gravité puis ancienneté) — mais ici sans limite, cette page montre tout
  // le portefeuille. `raised_at`/`last_seen_at` jouent le même rôle
  // d'horodatage de référence pour chaque nature de signal.
  const priorityAlarms = prioritizeAlarms(alarms, alarms.length);
  const priorityFindings = prioritizeAlarms(
    findings.map((finding) => ({
      ...finding,
      raised_at: finding.last_seen_at,
    })),
    findings.length,
  );

  const signalActions = {
    acknowledgeSignal,
    clearAlarm,
    setHandling,
    confirmFinding,
  };

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>
        {t("web.alarms_page.title")}
      </h1>
      {error && <p style={{ color: colors.danger }}>{error}</p>}

      <section
        style={{
          ...cardStyle,
          marginBottom: 24,
          padding: 0,
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "20px 24px 0" }}>
          <h2 style={sectionTitleStyle}>
            {t("web.alarms_page.alarms_section_title")}
          </h2>
        </div>
        {priorityAlarms.length === 0 ? (
          <p style={{ color: colors.textMuted, padding: "0 24px 20px" }}>
            {t("web.alarms_page.no_alarms")}
          </p>
        ) : (
          <div style={tableScrollStyle}>
            <table
              className="responsive-table"
              style={{ width: "100%", borderCollapse: "collapse" }}
            >
              <thead>
                <tr>
                  <th style={headerCellStyle}>
                    {t("web.dashboard.col_severity")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.dashboard.equipment")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.dashboard.col_message")}
                  </th>
                  <th style={headerCellStyle}>{t("web.dashboard.col_ack")}</th>
                  <th style={headerCellStyle}>
                    {t("web.dashboard.col_since")}
                  </th>
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
                      <td
                        data-label={t("web.dashboard.col_severity")}
                        style={cellStyle}
                      >
                        <span
                          title={t(`severity.${alarm.severity}`)}
                          style={badgeStyle(
                            SEVERITY_COLOR[alarm.severity as Severity],
                          )}
                        >
                          {t(`severity.${alarm.severity}`)}
                        </span>
                      </td>
                      <td
                        data-label={t("web.dashboard.equipment")}
                        style={cellStyle}
                      >
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
                      <td
                        data-label={t("web.dashboard.col_message")}
                        style={cellStyle}
                      >
                        {alarm.message}
                      </td>
                      <td
                        data-label={t("web.dashboard.col_ack")}
                        style={cellStyle}
                      >
                        {t(`ack_state.${alarm.ack_state}`)}
                      </td>
                      <td
                        data-label={t("web.dashboard.col_since")}
                        style={cellStyle}
                      >
                        {formatDateTime(locale, alarm.raised_at)}
                      </td>
                      <td style={cellStyle}>
                        <SignalActions
                          kind="alarm"
                          signal={alarm}
                          nodeId=""
                          actions={signalActions}
                          t={t}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "20px 24px 0" }}>
          <h2 style={sectionTitleStyle}>
            {t("web.alarms_page.findings_section_title")}
          </h2>
        </div>
        {priorityFindings.length === 0 ? (
          <p style={{ color: colors.textMuted, padding: "0 24px 20px" }}>
            {t("web.alarms_page.no_findings")}
          </p>
        ) : (
          <div style={tableScrollStyle}>
            <table
              className="responsive-table"
              style={{ width: "100%", borderCollapse: "collapse" }}
            >
              <thead>
                <tr>
                  <th style={headerCellStyle}>
                    {t("web.dashboard.col_severity")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.dashboard.equipment")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.dashboard.col_message")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.alarms_page.col_certainty")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.dashboard.col_since")}
                  </th>
                  <th style={headerCellStyle} />
                </tr>
              </thead>
              <tbody>
                {priorityFindings.map((finding) => {
                  const location = locationById.get(finding.subject_node_id);
                  return (
                    <tr key={finding.id}>
                      <td
                        data-label={t("web.dashboard.col_severity")}
                        style={cellStyle}
                      >
                        <span
                          title={t(`severity.${finding.severity}`)}
                          style={badgeStyle(
                            SEVERITY_COLOR[finding.severity as Severity],
                          )}
                        >
                          {t(`severity.${finding.severity}`)}
                        </span>
                      </td>
                      <td
                        data-label={t("web.dashboard.equipment")}
                        style={cellStyle}
                      >
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
                      <td
                        data-label={t("web.dashboard.col_message")}
                        style={cellStyle}
                      >
                        {finding.title}
                      </td>
                      <td
                        data-label={t("web.alarms_page.col_certainty")}
                        style={cellStyle}
                      >
                        {t(`certainty.${finding.certainty}`)}
                      </td>
                      <td
                        data-label={t("web.dashboard.col_since")}
                        style={cellStyle}
                      >
                        {formatDateTime(locale, finding.last_seen_at)}
                      </td>
                      <td style={cellStyle}>
                        <SignalActions
                          kind="finding"
                          signal={{ ...finding, findingKind: finding.kind }}
                          nodeId=""
                          actions={signalActions}
                          t={t}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
