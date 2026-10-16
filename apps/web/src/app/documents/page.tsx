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
import { getLocale, getTranslator } from "@/lib/i18n";
import { formatDateTime } from "@/i18n/translator";

import { uploadDocument } from "./actions";

/**
 * Page Documents (directive UI/dashboard, section 36, point 10) :
 * bibliothèque de tout le portefeuille — manuels, certificats, garanties,
 * fiches techniques, contrats, rapports de conformité rattachés à un
 * équipement. Distincte de « Plans & BIM » (plans d'étage, ADR 011) et des
 * photos d'intervention : un document ici est une pièce administrative ou
 * technique de l'équipement.
 *
 * Réutilise le patron déjà établi pour l'envoi de fichiers (URL présignée
 * puis confirmation, voir app/registre/actions.ts::uploadFloorPlan) —
 * app/documents/actions.ts::uploadDocument fait la même chose pour un
 * document d'équipement.
 */

type PortfolioDocument = {
  id: string;
  functional_location_id: string;
  functional_location_code: string;
  functional_location_name: string;
  category: string;
  filename: string;
  content_type: string;
  download_url: string;
  uploaded_by: string;
  uploaded_at: string;
};

type FunctionalLocation = { id: string; code: string; name: string };

const CATEGORIES = [
  "manual",
  "certificate",
  "warranty",
  "datasheet",
  "compliance_report",
  "contract",
  "other",
] as const;

export default async function DocumentsPage() {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();
  const locale = await getLocale();

  const [documentsResponse, locationsResponse] = await Promise.all([
    apiFetch("/documents/portfolio", accessToken),
    apiFetch("/functional-locations", accessToken),
  ]);
  const documents: PortfolioDocument[] = documentsResponse.ok
    ? await documentsResponse.json()
    : [];
  const locations: FunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>
        {t("web.documents_page.title")}
      </h1>

      {documents.length === 0 ? (
        <section style={cardStyle}>
          <p style={{ color: colors.textMuted }}>
            {t("web.documents_page.no_documents")}
          </p>
        </section>
      ) : (
        <section style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "20px 24px 0" }}>
            <h2 style={sectionTitleStyle}>
              {t("web.documents_page.library_title")}
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
                    {t("web.documents_page.col_category")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.documents_page.col_filename")}
                  </th>
                  <th style={headerCellStyle}>
                    {t("web.documents_page.col_uploaded")}
                  </th>
                  <th style={headerCellStyle} />
                </tr>
              </thead>
              <tbody>
                {documents.map((document) => (
                  <tr key={document.id}>
                    <td
                      data-label={t("mobile.passport.equipment")}
                      style={cellStyle}
                    >
                      <Link
                        href={`/registre/${document.functional_location_id}`}
                        style={{ color: colors.accent }}
                      >
                        {document.functional_location_code} —{" "}
                        {document.functional_location_name}
                      </Link>
                    </td>
                    <td
                      data-label={t("web.documents_page.col_category")}
                      style={cellStyle}
                    >
                      {t(`web.documents_page.category.${document.category}`)}
                    </td>
                    <td
                      data-label={t("web.documents_page.col_filename")}
                      style={cellStyle}
                    >
                      {document.filename}
                    </td>
                    <td
                      data-label={t("web.documents_page.col_uploaded")}
                      style={cellStyle}
                    >
                      {t("web.registre.floor_plans_uploaded_by", {
                        actor: document.uploaded_by,
                        date: formatDateTime(locale, document.uploaded_at),
                      })}
                    </td>
                    <td style={cellStyle}>
                      <a
                        href={document.download_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {t("web.registre.floor_plans_view_link")}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section style={{ ...cardStyle, marginTop: 24 }}>
        <h2 style={sectionTitleStyle}>
          {t("web.documents_page.upload_title")}
        </h2>
        {locations.length === 0 ? (
          <p style={{ color: colors.textMuted }}>
            {t("web.documents_page.no_equipment")}
          </p>
        ) : (
          <form action={uploadDocument} style={{ maxWidth: 400 }}>
            <label style={labelStyle}>
              {t("web.documents_page.select_equipment")}
              <select name="functional_location_id" required style={fieldStyle}>
                {locations.map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.code} — {location.name}
                  </option>
                ))}
              </select>
            </label>
            <label style={labelStyle}>
              {t("web.documents_page.select_category")}
              <select name="category" required style={fieldStyle}>
                {CATEGORIES.map((category) => (
                  <option key={category} value={category}>
                    {t(`web.documents_page.category.${category}`)}
                  </option>
                ))}
              </select>
            </label>
            <label style={labelStyle}>
              {t("web.documents_page.file_label")}
              <input
                type="file"
                name="file"
                accept="application/pdf,image/png,image/jpeg"
                required
                style={fieldStyle}
              />
            </label>
            <button type="submit" style={submitStyle}>
              {t("web.documents_page.submit")}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
