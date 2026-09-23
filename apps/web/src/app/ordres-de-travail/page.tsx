import Link from "next/link";

import type { Translator } from "@/i18n/translator";
import { apiFetch, requireAccessToken } from "@/lib/api";
import { errorMessage, getTranslator } from "@/lib/i18n";

import { createWorkOrder } from "./actions";

type WorkOrder = {
  id: string;
  title: string;
  work_order_type: string;
  priority: string;
  status: string;
  functional_location_id: string | null;
};
type FunctionalLocation = { id: string; code: string; name: string };

const cellStyle = { borderBottom: "1px solid #eee", padding: "6px 8px", textAlign: "left" as const };
const headerCellStyle = { borderBottom: "1px solid #ddd", padding: "6px 8px", textAlign: "left" as const };
const fieldStyle = { display: "block", width: "100%", padding: 8, marginTop: 4 };

const TYPES = ["corrective", "preventive", "predictive", "inspection"];
const PRIORITIES = ["low", "medium", "high", "urgent"];

function creationError(translator: Translator, code: string | undefined): string | null {
  if (!code) return null;
  if (code === "TITLE_REQUIRED") return translator.t("web.work_orders.title_required");
  return (
    errorMessage(translator.locale, code) ?? translator.t("web.work_orders.creation_failed")
  );
}

export default async function WorkOrdersPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const accessToken = await requireAccessToken();
  const translator = await getTranslator();
  const { t } = translator;
  const error = creationError(translator, (await searchParams).error);
  const [response, locationsResponse] = await Promise.all([
    apiFetch("/work-orders", accessToken),
    apiFetch("/functional-locations", accessToken),
  ]);
  const workOrders: WorkOrder[] = response.ok ? await response.json() : [];
  const locations: FunctionalLocation[] = locationsResponse.ok ? await locationsResponse.json() : [];
  const location = (id: string | null) => locations.find((candidate) => candidate.id === id);

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
      <Link href="/">← {t("common.back")}</Link>
      <h1>{t("web.work_orders.title")}</h1>

      {workOrders.length === 0 ? (
        <p>{t("web.work_orders.empty")}</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 32 }}>
          <thead>
            <tr>
              <th style={headerCellStyle}>{t("web.work_orders.col_title")}</th>
              <th style={headerCellStyle}>{t("web.work_orders.col_type")}</th>
              <th style={headerCellStyle}>{t("web.work_orders.col_priority")}</th>
              <th style={headerCellStyle}>{t("web.work_orders.col_status")}</th>
              <th style={headerCellStyle}>{t("mobile.passport.equipment")}</th>
            </tr>
          </thead>
          <tbody>
            {workOrders.map((workOrder) => {
              const target = location(workOrder.functional_location_id);
              return (
                <tr key={workOrder.id}>
                  <td style={cellStyle}>{workOrder.title}</td>
                  <td style={cellStyle}>{t(`work_order.type.${workOrder.work_order_type}`)}</td>
                  <td style={cellStyle}>{t(`work_order.priority.${workOrder.priority}`)}</td>
                  <td style={cellStyle}>{t(`work_order.status.${workOrder.status}`)}</td>
                  <td style={cellStyle}>
                    {target ? (
                      <Link href={`/registre/${target.id}`}>{target.code}</Link>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <h2>{t("web.work_orders.create")}</h2>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}
      <form action={createWorkOrder} style={{ maxWidth: 400 }}>
        <label>
          {t("web.work_orders.col_title")}
          <input name="title" required style={fieldStyle} />
        </label>
        <label style={{ display: "block", marginTop: 12 }}>
          {t("web.work_orders.col_type")}
          <select name="work_order_type" defaultValue="corrective" style={fieldStyle}>
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`work_order.type.${type}`)}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "block", marginTop: 12 }}>
          {t("web.work_orders.col_priority")}
          <select name="priority" defaultValue="medium" style={fieldStyle}>
            {PRIORITIES.map((priority) => (
              <option key={priority} value={priority}>
                {t(`work_order.priority.${priority}`)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          style={{
            marginTop: 16,
            padding: "10px 20px",
            background: "#2563eb",
            color: "white",
            border: "none",
            borderRadius: 8,
          }}
        >
          {t("web.work_orders.submit")}
        </button>
      </form>
    </main>
  );
}
