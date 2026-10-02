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
import { errorMessage, getLocale, getTranslator } from "@/lib/i18n";
import { formatDateTime } from "@/i18n/translator";

import {
  markOperatDeclarationReady,
  recordOperatSubmission,
  updateOperatDeclaration,
} from "../actions";

type OperatDeclaration = {
  id: string;
  site_id: string;
  reference_year: number;
  status: "draft" | "ready" | "submitted";
  floor_area_m2: number | null;
  activity_category: string | null;
  electricity_kwh: number | null;
  gas_kwh: number | null;
  heat_network_kwh: number | null;
  other_kwh: number | null;
  other_label: string | null;
  notes: string | null;
  submitted_by: string | null;
  submitted_at: string | null;
  submission_reference: string | null;
};

type OperatSummary = {
  annee_reference: number;
  surface_m2: number | null;
  categorie_activite: string | null;
  electricite_kwh: number | null;
  gaz_kwh: number | null;
  reseau_chaleur_kwh: number | null;
  autre_kwh: number | null;
  autre_libelle: string | null;
};

export default async function OperatDeclarationPage({
  params,
  searchParams,
}: {
  params: Promise<{ declarationId: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { declarationId } = await params;
  const { error: errorCode } = await searchParams;
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();
  const locale = await getLocale();

  const [declarationResponse, summaryResponse] = await Promise.all([
    apiFetch(`/operat-declarations/${declarationId}`, accessToken),
    apiFetch(`/operat-declarations/${declarationId}/summary`, accessToken),
  ]);

  if (!declarationResponse.ok) {
    return (
      <main style={pageContainerStyle}>
        <Link href="/operat" style={{ color: colors.accent }}>
          ← {t("common.back")}
        </Link>
        <p>{t("web.registre.access_denied")}</p>
      </main>
    );
  }

  const declaration: OperatDeclaration = await declarationResponse.json();
  const summary: OperatSummary | null = summaryResponse.ok ? await summaryResponse.json() : null;
  const error = errorCode
    ? (errorMessage(locale, errorCode) ?? t("web.registre.creation_failed"))
    : null;
  const frozen = declaration.status === "submitted";

  return (
    <main style={pageContainerStyle}>
      <Link href="/operat" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>
        {t("web.operat_page.edit_title", { year: String(declaration.reference_year) })}
      </h1>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}

      <section style={{ ...cardStyle, marginBottom: 20 }}>
        {frozen && (
          <p style={{ color: colors.textMuted, marginBottom: 12 }}>
            {t("web.operat_page.frozen_notice")}
          </p>
        )}
        <form action={updateOperatDeclaration}>
          <input type="hidden" name="declaration_id" value={declaration.id} />
          <label style={labelStyle}>
            {t("web.operat_page.field_floor_area")}
            <input
              type="number"
              step="0.01"
              name="floor_area_m2"
              defaultValue={declaration.floor_area_m2 ?? ""}
              disabled={frozen}
              style={fieldStyle}
            />
          </label>
          <label style={labelStyle}>
            {t("web.operat_page.field_activity_category")}
            <input
              type="text"
              name="activity_category"
              defaultValue={declaration.activity_category ?? ""}
              disabled={frozen}
              style={fieldStyle}
            />
          </label>
          <label style={labelStyle}>
            {t("web.operat_page.field_electricity")}
            <input
              type="number"
              step="0.01"
              name="electricity_kwh"
              defaultValue={declaration.electricity_kwh ?? ""}
              disabled={frozen}
              style={fieldStyle}
            />
          </label>
          <label style={labelStyle}>
            {t("web.operat_page.field_gas")}
            <input
              type="number"
              step="0.01"
              name="gas_kwh"
              defaultValue={declaration.gas_kwh ?? ""}
              disabled={frozen}
              style={fieldStyle}
            />
          </label>
          <label style={labelStyle}>
            {t("web.operat_page.field_heat_network")}
            <input
              type="number"
              step="0.01"
              name="heat_network_kwh"
              defaultValue={declaration.heat_network_kwh ?? ""}
              disabled={frozen}
              style={fieldStyle}
            />
          </label>
          <label style={labelStyle}>
            {t("web.operat_page.field_other")}
            <input
              type="number"
              step="0.01"
              name="other_kwh"
              defaultValue={declaration.other_kwh ?? ""}
              disabled={frozen}
              style={fieldStyle}
            />
          </label>
          <label style={labelStyle}>
            {t("web.operat_page.field_other_label")}
            <input
              type="text"
              name="other_label"
              defaultValue={declaration.other_label ?? ""}
              disabled={frozen}
              style={fieldStyle}
            />
          </label>
          <label style={labelStyle}>
            {t("web.operat_page.field_notes")}
            <textarea
              name="notes"
              defaultValue={declaration.notes ?? ""}
              disabled={frozen}
              style={{ ...fieldStyle, minHeight: 80 }}
            />
          </label>
          {!frozen && (
            <button type="submit" style={submitStyle}>
              {t("web.operat_page.save")}
            </button>
          )}
        </form>

        {!frozen && declaration.status === "draft" && (
          <form action={markOperatDeclarationReady} style={{ marginTop: 12 }}>
            <input type="hidden" name="declaration_id" value={declaration.id} />
            <button type="submit" style={submitStyle}>
              {t("web.operat_page.mark_ready")}
            </button>
          </form>
        )}
        {declaration.status === "ready" && (
          <p style={{ color: colors.textMuted, marginTop: 12 }}>
            {t("web.operat_page.already_ready")}
          </p>
        )}
      </section>

      {summary && (
        <section style={{ ...cardStyle, marginBottom: 20 }}>
          <h2 style={sectionTitleStyle}>{t("web.operat_page.summary_title")}</h2>
          <div style={tableScrollStyle}>
            <table className="responsive-table" style={{ width: "100%", borderCollapse: "collapse" }}>
              <tbody>
                <tr>
                  <th style={headerCellStyle}>{t("web.operat_page.col_year")}</th>
                  <td style={cellStyle}>{summary.annee_reference}</td>
                </tr>
                <tr>
                  <th style={headerCellStyle}>{t("web.operat_page.col_surface")}</th>
                  <td style={cellStyle}>{summary.surface_m2 ?? "—"}</td>
                </tr>
                <tr>
                  <th style={headerCellStyle}>{t("web.operat_page.col_activity")}</th>
                  <td style={cellStyle}>{summary.categorie_activite ?? "—"}</td>
                </tr>
                <tr>
                  <th style={headerCellStyle}>{t("web.operat_page.field_electricity")}</th>
                  <td style={cellStyle}>{summary.electricite_kwh ?? "—"}</td>
                </tr>
                <tr>
                  <th style={headerCellStyle}>{t("web.operat_page.field_gas")}</th>
                  <td style={cellStyle}>{summary.gaz_kwh ?? "—"}</td>
                </tr>
                <tr>
                  <th style={headerCellStyle}>{t("web.operat_page.field_heat_network")}</th>
                  <td style={cellStyle}>{summary.reseau_chaleur_kwh ?? "—"}</td>
                </tr>
                <tr>
                  <th style={headerCellStyle}>{t("web.operat_page.field_other")}</th>
                  <td style={cellStyle}>
                    {summary.autre_kwh ?? "—"}
                    {summary.autre_libelle ? ` (${summary.autre_libelle})` : ""}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>{t("web.operat_page.record_submission")}</h2>
        {declaration.status === "submitted" ? (
          <p style={{ color: colors.textMuted }}>
            {t("web.operat_page.already_submitted", {
              date: declaration.submitted_at
                ? formatDateTime(locale, declaration.submitted_at, null)
                : "",
              reference: declaration.submission_reference
                ? t("web.operat_page.reference_suffix", {
                    reference: declaration.submission_reference,
                  })
                : "",
            })}
          </p>
        ) : (
          <form action={recordOperatSubmission}>
            <input type="hidden" name="declaration_id" value={declaration.id} />
            <label style={labelStyle}>
              {t("web.operat_page.submission_reference")}
              <input type="text" name="submission_reference" style={fieldStyle} />
            </label>
            <button
              type="submit"
              style={submitStyle}
              disabled={declaration.status !== "ready"}
            >
              {t("web.operat_page.record_submission")}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
