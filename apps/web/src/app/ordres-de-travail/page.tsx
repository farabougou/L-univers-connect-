import Link from "next/link";

import { formatDateTime, type Translator } from "@/i18n/translator";
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
import { errorMessage, getLocale, getTranslator } from "@/lib/i18n";
import {
  recentClosures,
  repeatingFailures,
  type MaintenanceIntervention,
  type MaintenanceWorkOrder,
} from "@/lib/maintenance";

import { createWorkOrder, updateWorkOrderStatus } from "./actions";

/**
 * Page Maintenance (directive UI/dashboard, section 36 point 5) : le
 * portefeuille complet des ordres de travail (déjà là), enrichi des deux
 * listes que le bloc « Maintenance » du Global Command Center ne montre
 * qu'en aperçu limité (pannes répétitives, dernières clôtures) — ici sans
 * plafond, cette page est le complément « tout voir » du bloc résumé,
 * exactement comme /alarmes l'est pour « Alarmes prioritaires ». Mêmes
 * fonctions pures que le tableau de bord (apps/web/src/lib/maintenance.ts),
 * aucune deuxième logique de calcul.
 */

type WorkOrder = MaintenanceWorkOrder;
type FunctionalLocation = { id: string; code: string; name: string };

const TYPES = ["corrective", "preventive", "predictive", "inspection"];
const PRIORITIES = ["low", "medium", "high", "urgent"];
const STATUSES = ["open", "in_progress", "completed", "cancelled"];

function creationError(
  translator: Translator,
  code: string | undefined,
): string | null {
  if (!code) return null;
  if (code === "TITLE_REQUIRED")
    return translator.t("web.work_orders.title_required");
  return (
    errorMessage(translator.locale, code) ??
    translator.t("web.work_orders.creation_failed")
  );
}

export default async function MaintenancePage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const accessToken = await requireAccessToken();
  const translator = await getTranslator();
  const { t } = translator;
  const locale = await getLocale();
  const error = creationError(translator, (await searchParams).error);
  const [response, locationsResponse, interventionsResponse] =
    await Promise.all([
      apiFetch("/work-orders", accessToken),
      apiFetch("/functional-locations", accessToken),
      apiFetch("/interventions", accessToken),
    ]);
  const workOrders: WorkOrder[] = response.ok ? await response.json() : [];
  const locations: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];
  const interventions: MaintenanceIntervention[] = interventionsResponse.ok
    ? await interventionsResponse.json()
    : [];
  const location = (id: string | null) =>
    locations.find((candidate) => candidate.id === id);

  const allRepeatingFailures = repeatingFailures(workOrders);
  const allRecentClosures = recentClosures(interventions, interventions.length);

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>
        {t("web.work_orders.page_title")}
      </h1>

      <section
        style={{
          ...cardStyle,
          marginBottom: 24,
          padding: 0,
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "20px 24px 0" }}>
          <h2 style={sectionTitleStyle}>{t("web.work_orders.title")}</h2>
        </div>
        {workOrders.length === 0 ? (
          <p style={{ color: colors.textMuted, padding: "0 24px 20px" }}>
            {t("web.work_orders.empty")}
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
                    {t("web.work_orders.col_title")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.work_orders.col_type")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.work_orders.col_priority")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.work_orders.col_status")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("mobile.passport.equipment")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {workOrders.map((workOrder) => {
                  const target = location(workOrder.functional_location_id);
                  return (
                    <tr key={workOrder.id}>
                      <td
                        data-label={t("web.work_orders.col_title")}
                        style={cellStyle}
                      >
                        {workOrder.title}
                      </td>
                      <td
                        data-label={t("web.work_orders.col_type")}
                        style={cellStyle}
                      >
                        {t(`work_order.type.${workOrder.work_order_type}`)}
                      </td>
                      <td
                        data-label={t("web.work_orders.col_priority")}
                        style={cellStyle}
                      >
                        {t(`work_order.priority.${workOrder.priority}`)}
                      </td>
                      <td
                        data-label={t("web.work_orders.col_status")}
                        style={cellStyle}
                      >
                        <form
                          action={updateWorkOrderStatus}
                          style={{ display: "flex", gap: 4 }}
                        >
                          <input
                            type="hidden"
                            name="work_order_id"
                            value={workOrder.id}
                          />
                          <select name="status" defaultValue={workOrder.status}>
                            {STATUSES.map((status) => (
                              <option key={status} value={status}>
                                {t(`work_order.status.${status}`)}
                              </option>
                            ))}
                          </select>
                          <button type="submit">
                            {t("web.work_orders.update_status")}
                          </button>
                        </form>
                      </td>
                      <td
                        data-label={t("mobile.passport.equipment")}
                        style={cellStyle}
                      >
                        {target ? (
                          <Link
                            href={`/registre/${target.id}`}
                            style={{ color: colors.accent }}
                          >
                            {target.code}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div style={{ padding: 24 }}>
          <h2 style={sectionTitleStyle}>{t("web.work_orders.create")}</h2>
          {error && <p style={{ color: "#c0392b" }}>{error}</p>}
          <form action={createWorkOrder} style={{ maxWidth: 400 }}>
            <label>
              {t("web.work_orders.col_title")}
              <input name="title" required style={fieldStyle} />
            </label>
            <label style={labelStyle}>
              {t("web.work_orders.col_type")}
              <select
                name="work_order_type"
                defaultValue="corrective"
                style={fieldStyle}
              >
                {TYPES.map((type) => (
                  <option key={type} value={type}>
                    {t(`work_order.type.${type}`)}
                  </option>
                ))}
              </select>
            </label>
            <label style={labelStyle}>
              {t("web.work_orders.col_priority")}
              <select name="priority" defaultValue="medium" style={fieldStyle}>
                {PRIORITIES.map((priority) => (
                  <option key={priority} value={priority}>
                    {t(`work_order.priority.${priority}`)}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" style={submitStyle}>
              {t("web.work_orders.submit")}
            </button>
          </form>
        </div>
      </section>

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <section style={{ ...cardStyle, flex: "1 1 320px" }}>
          <h2 style={sectionTitleStyle}>
            {t("web.dashboard.maintenance_repeating_title")}
          </h2>
          {allRepeatingFailures.length === 0 ? (
            <p style={{ color: colors.textMuted, fontSize: 13 }}>
              {t("web.dashboard.maintenance_repeating_none")}
            </p>
          ) : (
            <ul
              style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              {allRepeatingFailures.map((entry) => {
                const target = location(entry.functional_location_id);
                return (
                  <li
                    key={entry.functional_location_id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 13,
                    }}
                  >
                    {target ? (
                      <Link
                        href={`/registre/${target.id}`}
                        style={{ color: colors.accent }}
                      >
                        {target.code} — {target.name}
                      </Link>
                    ) : (
                      "—"
                    )}
                    <span style={{ color: colors.textMuted }}>
                      {t("web.dashboard.maintenance_repeating_count", {
                        count: entry.count,
                      })}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section style={{ ...cardStyle, flex: "1 1 320px" }}>
          <h2 style={sectionTitleStyle}>
            {t("web.dashboard.maintenance_closures_title")}
          </h2>
          {allRecentClosures.length === 0 ? (
            <p style={{ color: colors.textMuted, fontSize: 13 }}>
              {t("web.dashboard.maintenance_closures_none")}
            </p>
          ) : (
            <ul
              style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              {allRecentClosures.map((intervention) => {
                const target = intervention.functional_location_id
                  ? location(intervention.functional_location_id)
                  : undefined;
                return (
                  <li key={intervention.id} style={{ fontSize: 13 }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <span>
                        {target ? `${target.code} — ${target.name}` : "—"}
                      </span>
                      <span style={{ color: colors.textMuted }}>
                        {formatDateTime(
                          locale,
                          intervention.ended_at as string,
                        )}
                      </span>
                    </div>
                    <div style={{ color: colors.textMuted }}>
                      {intervention.technician}
                      {intervention.summary ? ` — ${intervention.summary}` : ""}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
