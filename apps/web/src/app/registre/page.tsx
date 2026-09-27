import Link from "next/link";

import { type Translator, formatDateTime } from "@/i18n/translator";
import { apiFetch, requireAccessToken } from "@/lib/api";
import {
  cellStyle,
  fieldStyle,
  headerCellStyle,
  labelStyle,
  submitStyle,
} from "@/lib/formStyles";
import { errorMessage, getLocale, getTranslator } from "@/lib/i18n";
import { type Me, canManage as computeCanManage } from "@/lib/roles";
import { renderTagQr } from "@/lib/tagQr";

import {
  acceptIfcImportProposal,
  closeSpace,
  createEquipment,
  createProvider,
  createSite,
  createSpace,
  rejectIfcImportProposal,
  showTag,
  updateProvider,
  updateSiteTimezone,
  uploadFloorPlan,
  uploadIfcImport,
} from "./actions";

type Site = { id: string; name: string; timezone: string | null };
type EquipmentType = { code: string; label: string };
type FunctionalLocation = { id: string; site_id: string; code: string; name: string };
type Space = {
  id: string;
  site_id: string;
  parent_id: string | null;
  space_type: string;
  code: string;
  name: string;
};
type FloorPlan = {
  id: string;
  version: number;
  filename: string;
  content_type: string;
  download_url: string;
  uploaded_by: string;
  uploaded_at: string;
};
type IfcImportBatch = {
  id: string;
  site_id: string;
  filename: string;
  status: string;
  error_code: string | null;
  space_proposal_count: number | null;
  equipment_proposal_count: number | null;
  skipped_element_count: number | null;
  uploaded_by: string;
  uploaded_at: string;
};
type IfcImportProposal = {
  id: string;
  batch_id: string;
  proposal_type: string;
  ifc_class: string;
  name: string;
  status: string;
  rejection_reason: string | null;
};
type Provider = {
  id: string;
  name: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
};

// Même vocabulaire que app/spatial_vocabulary.py (ADR 011) ; un jeu de cinq
// types stables, comme les priorités d'ordre de travail plus bas.
const SPACE_TYPES = ["building", "floor", "zone", "room", "outdoor_area"];

function creationError(translator: Translator, code: string | undefined): string | null {
  if (!code) return null;
  return errorMessage(translator.locale, code) ?? translator.t("web.registre.creation_failed");
}

export default async function RegistrePage({
  searchParams,
}: {
  searchParams: Promise<{
    error?: string;
    tag?: string;
    label?: string;
    space?: string;
    import_site?: string;
    import_batch?: string;
  }>;
}) {
  const accessToken = await requireAccessToken();
  const translator = await getTranslator();
  const { t } = translator;
  const locale = await getLocale();
  const params = await searchParams;
  const error = creationError(translator, params.error);

  const meResponse = await apiFetch("/me", accessToken);
  const me: Me = meResponse.ok ? await meResponse.json() : { roles: [] };
  const canManage = computeCanManage(me);

  if (!canManage) {
    return (
      <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
        <Link href="/">← {t("common.back")}</Link>
        <h1>{t("web.registre.title")}</h1>
        <p>{t("web.registre.access_denied")}</p>
      </main>
    );
  }

  const [sitesResponse, locationsResponse, typesResponse, spacesResponse, providersResponse] =
    await Promise.all([
      apiFetch("/sites", accessToken),
      apiFetch("/functional-locations", accessToken),
      apiFetch("/equipment-types", accessToken),
      apiFetch("/spaces", accessToken),
      apiFetch("/providers", accessToken),
    ]);
  const sites: Site[] = sitesResponse.ok ? await sitesResponse.json() : [];
  const locations: FunctionalLocation[] = locationsResponse.ok ? await locationsResponse.json() : [];
  const equipmentTypes: EquipmentType[] = typesResponse.ok
    ? (await typesResponse.json()).types
    : [];
  const spaces: Space[] = spacesResponse.ok ? await spacesResponse.json() : [];
  const providers: Provider[] = providersResponse.ok ? await providersResponse.json() : [];
  const siteName = (siteId: string) => sites.find((site) => site.id === siteId)?.name ?? siteId;
  const spaceLabel = (spaceId: string) => {
    const space = spaces.find((candidate) => candidate.id === spaceId);
    return space ? `${t(`space_type.${space.space_type}`)} — ${space.name}` : spaceId;
  };

  let tagSvg: string | null = null;
  if (params.tag) {
    tagSvg = await renderTagQr(params.tag);
  }

  let floorPlans: FloorPlan[] = [];
  if (params.space) {
    const floorPlansResponse = await apiFetch(`/spaces/${params.space}/floor-plans`, accessToken);
    floorPlans = floorPlansResponse.ok ? await floorPlansResponse.json() : [];
  }

  let ifcImportBatches: IfcImportBatch[] = [];
  if (params.import_site) {
    const batchesResponse = await apiFetch(
      `/sites/${params.import_site}/ifc-imports`,
      accessToken,
    );
    ifcImportBatches = batchesResponse.ok ? await batchesResponse.json() : [];
  }
  let ifcImportProposals: IfcImportProposal[] = [];
  if (params.import_batch) {
    const proposalsResponse = await apiFetch(
      `/ifc-imports/${params.import_batch}/proposals`,
      accessToken,
    );
    ifcImportProposals = proposalsResponse.ok ? await proposalsResponse.json() : [];
  }
  const selectedImportBatch = ifcImportBatches.find((batch) => batch.id === params.import_batch);

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
      <Link href="/">← {t("common.back")}</Link>
      <h1>{t("web.registre.title")}</h1>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}

      {params.tag && tagSvg && (
        <section
          style={{ border: "1px solid #2563eb", borderRadius: 8, padding: 16, margin: "16px 0" }}
        >
          <h2>{t("web.registre.tag_banner_title", { name: params.label ?? "" })}</h2>
          <div dangerouslySetInnerHTML={{ __html: tagSvg }} />
          <p>
            {t("web.registre.tag_code_label")} : <strong>{params.tag}</strong>
          </p>
          <p style={{ color: "#666" }}>{t("web.registre.tag_hint")}</p>
          <Link href="/registre">{t("web.registre.tag_close")}</Link>
        </section>
      )}

      <h2>{t("web.registre.sites_title")}</h2>
      {sites.length === 0 ? (
        <p>{t("web.registre.no_sites")}</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 24 }}>
          <thead>
            <tr>
              <th style={headerCellStyle}>{t("web.registre.site_name")}</th>
              <th style={headerCellStyle}>{t("web.registre.site_timezone_label")}</th>
            </tr>
          </thead>
          <tbody>
            {sites.map((site) => (
              <tr key={site.id}>
                <td style={cellStyle}>{site.name}</td>
                <td style={cellStyle}>
                  <form action={updateSiteTimezone} style={{ display: "flex", gap: 4 }}>
                    <input type="hidden" name="site_id" value={site.id} />
                    <input name="timezone" defaultValue={site.timezone ?? ""} required />
                    <button type="submit">{t("web.registre.edit_timezone")}</button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3>{t("web.registre.create_site_title")}</h3>
      <form action={createSite} style={{ maxWidth: 400 }}>
        <label>
          {t("web.registre.site_name")}
          <input name="name" required style={fieldStyle} />
        </label>
        <label style={labelStyle}>
          {t("web.registre.site_timezone")}
          <input
            name="timezone"
            required
            placeholder={t("web.registre.site_timezone_placeholder")}
            style={fieldStyle}
          />
        </label>
        <button type="submit" style={submitStyle}>
          {t("web.registre.submit")}
        </button>
      </form>

      <h2 style={{ marginTop: 40 }}>{t("web.registre.spaces_title")}</h2>
      {spaces.length === 0 ? (
        <p>{t("web.registre.no_spaces")}</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 24 }}>
          <thead>
            <tr>
              <th style={headerCellStyle}>{t("web.registre.space_type")}</th>
              <th style={headerCellStyle}>{t("web.registre.space_name")}</th>
              <th style={headerCellStyle}>{t("web.registre.equipment_site")}</th>
              <th style={headerCellStyle}>{t("web.registre.space_parent")}</th>
              <th style={headerCellStyle} />
            </tr>
          </thead>
          <tbody>
            {spaces.map((space) => (
              <tr key={space.id}>
                <td style={cellStyle}>{t(`space_type.${space.space_type}`)}</td>
                <td style={cellStyle}>
                  {space.code} — {space.name}
                </td>
                <td style={cellStyle}>{siteName(space.site_id)}</td>
                <td style={cellStyle}>
                  {space.parent_id ? spaceLabel(space.parent_id) : t("web.registre.space_parent_none")}
                </td>
                <td style={cellStyle}>
                  <form action={closeSpace} style={{ display: "flex", gap: 4 }}>
                    <input type="hidden" name="space_id" value={space.id} />
                    <input name="reason" required placeholder={t("web.registre.close_space_reason")} />
                    <button type="submit">{t("web.registre.close_space")}</button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3>{t("web.registre.create_space_title")}</h3>
      {sites.length === 0 ? (
        <p>{t("web.registre.no_sites_yet")}</p>
      ) : (
        <form action={createSpace} style={{ maxWidth: 400 }}>
          <label>
            {t("web.registre.space_site")}
            <select name="site_id" required style={fieldStyle}>
              {sites.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.name}
                </option>
              ))}
            </select>
          </label>
          <label style={labelStyle}>
            {t("web.registre.space_type")}
            <select name="space_type" required style={fieldStyle}>
              {SPACE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {t(`space_type.${type}`)}
                </option>
              ))}
            </select>
          </label>
          <label style={labelStyle}>
            {t("web.registre.space_parent")}
            <select name="parent_id" style={fieldStyle} defaultValue="">
              <option value="">{t("web.registre.space_parent_none")}</option>
              {spaces.map((space) => (
                <option key={space.id} value={space.id}>
                  {siteName(space.site_id)} — {t(`space_type.${space.space_type}`)} — {space.name}
                </option>
              ))}
            </select>
          </label>
          <label style={labelStyle}>
            {t("web.registre.space_code")}
            <input name="code" required style={fieldStyle} />
          </label>
          <label style={labelStyle}>
            {t("web.registre.space_name")}
            <input name="name" required style={fieldStyle} />
          </label>
          <button type="submit" style={submitStyle}>
            {t("web.registre.submit")}
          </button>
        </form>
      )}

      <h2 style={{ marginTop: 40 }}>{t("web.registre.floor_plans_title")}</h2>
      <form method="get" style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
        <label style={{ flex: 1 }}>
          {t("web.registre.floor_plans_select_space")}
          <select name="space" defaultValue={params.space ?? ""} style={fieldStyle}>
            <option value="" disabled>
              {t("web.registre.floor_plans_select_space")}
            </option>
            {spaces.map((space) => (
              <option key={space.id} value={space.id}>
                {siteName(space.site_id)} — {t(`space_type.${space.space_type}`)} — {space.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" style={submitStyle}>
          {t("web.registre.floor_plans_view_button")}
        </button>
      </form>

      {params.space && (
        <section style={{ marginTop: 16 }}>
          <h3>{t("web.registre.floor_plans_for", { name: spaceLabel(params.space) })}</h3>
          {floorPlans.length === 0 ? (
            <p>{t("web.registre.floor_plans_none")}</p>
          ) : (
            <ul>
              {floorPlans.map((plan) => (
                <li key={plan.id}>
                  {t("web.registre.floor_plans_version", { version: plan.version })} —{" "}
                  {plan.filename} —{" "}
                  <a href={plan.download_url} target="_blank" rel="noreferrer">
                    {t("web.registre.floor_plans_view_link")}
                  </a>
                  {(plan.content_type === "image/png" || plan.content_type === "image/jpeg") && (
                    <>
                      {" — "}
                      <Link href={`/registre/plans/${plan.id}`}>
                        {t("web.registre.floor_plans_open_editor")}
                      </Link>
                    </>
                  )}
                  <br />
                  <span style={{ color: "#666" }}>
                    {t("web.registre.floor_plans_uploaded_by", {
                      actor: plan.uploaded_by,
                      date: formatDateTime(locale, plan.uploaded_at),
                    })}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <h4>{t("web.registre.floor_plans_upload_title")}</h4>
          <form action={uploadFloorPlan} style={{ maxWidth: 400 }}>
            <input type="hidden" name="space_id" value={params.space} />
            <label style={labelStyle}>
              {t("web.registre.floor_plans_file_label")}
              <input
                type="file"
                name="file"
                accept="application/pdf,image/png,image/jpeg"
                required
                style={fieldStyle}
              />
            </label>
            <button type="submit" style={submitStyle}>
              {t("web.registre.submit")}
            </button>
          </form>
        </section>
      )}

      <h2 style={{ marginTop: 40 }}>{t("web.registre.ifc_import_title")}</h2>
      <form method="get" style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
        <label style={{ flex: 1 }}>
          {t("web.registre.ifc_import_select_site")}
          <select name="import_site" defaultValue={params.import_site ?? ""} style={fieldStyle}>
            <option value="" disabled>
              {t("web.registre.ifc_import_select_site")}
            </option>
            {sites.map((site) => (
              <option key={site.id} value={site.id}>
                {site.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" style={submitStyle}>
          {t("web.registre.ifc_import_view_button")}
        </button>
      </form>

      {params.import_site && (
        <section style={{ marginTop: 16 }}>
          <h3>{t("web.registre.ifc_import_for", { name: siteName(params.import_site) })}</h3>
          {ifcImportBatches.length === 0 ? (
            <p>{t("web.registre.ifc_import_none")}</p>
          ) : (
            <ul>
              {ifcImportBatches.map((batch) => (
                <li key={batch.id} style={{ marginBottom: 8 }}>
                  <strong>{batch.filename}</strong> —{" "}
                  {t(`web.registre.ifc_import_status_${batch.status}`)}
                  {batch.status === "ready" &&
                    " — " +
                      t("web.registre.ifc_import_counts", {
                        spaces: batch.space_proposal_count ?? 0,
                        equipment: batch.equipment_proposal_count ?? 0,
                        skipped: batch.skipped_element_count ?? 0,
                      })}
                  {batch.status === "failed" &&
                    ` — ${errorMessage(locale, batch.error_code ?? "") ?? batch.error_code}`}
                  <br />
                  <span style={{ color: "#666" }}>
                    {t("web.registre.ifc_import_uploaded_by", {
                      actor: batch.uploaded_by,
                      date: formatDateTime(locale, batch.uploaded_at),
                    })}
                  </span>
                  {batch.status === "ready" && (
                    <>
                      {" — "}
                      <Link href={`/registre?import_site=${params.import_site}&import_batch=${batch.id}`}>
                        {t("web.registre.ifc_import_view_proposals")}
                      </Link>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}

          <h4>{t("web.registre.ifc_import_upload_title")}</h4>
          <form action={uploadIfcImport} style={{ maxWidth: 400 }}>
            <input type="hidden" name="site_id" value={params.import_site} />
            <label style={labelStyle}>
              {t("web.registre.ifc_import_file_label")}
              <input type="file" name="file" accept=".ifc" required style={fieldStyle} />
            </label>
            <button type="submit" style={submitStyle}>
              {t("web.registre.submit")}
            </button>
          </form>

          {selectedImportBatch && (
            <section style={{ marginTop: 16 }}>
              <h4>
                {t("web.registre.ifc_import_proposals_title", {
                  filename: selectedImportBatch.filename,
                })}
              </h4>
              {ifcImportProposals.length === 0 ? (
                <p>{t("web.registre.ifc_import_proposals_none")}</p>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={headerCellStyle}>{t("web.dashboard.name")}</th>
                      <th style={headerCellStyle} />
                      <th style={headerCellStyle} />
                    </tr>
                  </thead>
                  <tbody>
                    {ifcImportProposals.map((proposal) => (
                      <tr key={proposal.id}>
                        <td style={cellStyle}>
                          {t(`web.registre.ifc_import_proposal_type_${proposal.proposal_type}`)} —{" "}
                          {proposal.name} ({proposal.ifc_class})
                        </td>
                        <td style={cellStyle}>
                          {proposal.status === "proposed" ? (
                            <form action={acceptIfcImportProposal} style={{ display: "inline" }}>
                              <input type="hidden" name="proposal_id" value={proposal.id} />
                              <input type="hidden" name="site_id" value={params.import_site} />
                              <input type="hidden" name="batch_id" value={selectedImportBatch.id} />
                              <button type="submit">{t("web.registre.ifc_import_accept")}</button>
                            </form>
                          ) : proposal.status === "rejected" ? (
                            t("web.registre.ifc_import_rejected_reason", {
                              reason: proposal.rejection_reason ?? "",
                            })
                          ) : (
                            t("web.registre.ifc_import_proposal_status_accepted")
                          )}
                        </td>
                        <td style={cellStyle}>
                          {proposal.status === "proposed" && (
                            <form action={rejectIfcImportProposal} style={{ display: "flex", gap: 4 }}>
                              <input type="hidden" name="proposal_id" value={proposal.id} />
                              <input type="hidden" name="site_id" value={params.import_site} />
                              <input type="hidden" name="batch_id" value={selectedImportBatch.id} />
                              <input
                                name="reason"
                                required
                                placeholder={t("web.registre.ifc_import_reject_reason_label")}
                              />
                              <button type="submit">{t("web.registre.ifc_import_reject")}</button>
                            </form>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          )}
        </section>
      )}

      <h2 style={{ marginTop: 40 }}>{t("web.registre.providers_title")}</h2>
      {providers.length === 0 ? (
        <p>{t("web.registre.no_providers")}</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 24 }}>
          <thead>
            <tr>
              <th style={headerCellStyle}>{t("web.registre.provider_name")}</th>
              <th style={headerCellStyle}>{t("web.registre.provider_contact_name")}</th>
              <th style={headerCellStyle}>{t("web.registre.provider_contact_email")}</th>
              <th style={headerCellStyle}>{t("web.registre.provider_contact_phone")}</th>
              <th style={headerCellStyle} />
            </tr>
          </thead>
          <tbody>
            {providers.map((provider) => (
              <tr key={provider.id}>
                <td style={cellStyle}>{provider.name}</td>
                <td style={cellStyle}>{provider.contact_name ?? ""}</td>
                <td style={cellStyle}>{provider.contact_email ?? ""}</td>
                <td style={cellStyle}>{provider.contact_phone ?? ""}</td>
                <td style={cellStyle}>
                  <details>
                    <summary>{t("web.registre.edit_provider")}</summary>
                    <form action={updateProvider} style={{ maxWidth: 300 }}>
                      <input type="hidden" name="provider_id" value={provider.id} />
                      <label>
                        {t("web.registre.provider_name")}
                        <input name="name" defaultValue={provider.name} required style={fieldStyle} />
                      </label>
                      <label style={labelStyle}>
                        {t("web.registre.provider_contact_name")}
                        <input
                          name="contact_name"
                          defaultValue={provider.contact_name ?? ""}
                          style={fieldStyle}
                        />
                      </label>
                      <label style={labelStyle}>
                        {t("web.registre.provider_contact_email")}
                        <input
                          name="contact_email"
                          defaultValue={provider.contact_email ?? ""}
                          style={fieldStyle}
                        />
                      </label>
                      <label style={labelStyle}>
                        {t("web.registre.provider_contact_phone")}
                        <input
                          name="contact_phone"
                          defaultValue={provider.contact_phone ?? ""}
                          style={fieldStyle}
                        />
                      </label>
                      <button type="submit" style={submitStyle}>
                        {t("web.registre.submit")}
                      </button>
                    </form>
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3>{t("web.registre.create_provider_title")}</h3>
      <form action={createProvider} style={{ maxWidth: 400 }}>
        <label>
          {t("web.registre.provider_name")}
          <input name="name" required style={fieldStyle} />
        </label>
        <label style={labelStyle}>
          {t("web.registre.provider_contact_name")}
          <input name="contact_name" style={fieldStyle} />
        </label>
        <label style={labelStyle}>
          {t("web.registre.provider_contact_email")}
          <input name="contact_email" style={fieldStyle} />
        </label>
        <label style={labelStyle}>
          {t("web.registre.provider_contact_phone")}
          <input name="contact_phone" style={fieldStyle} />
        </label>
        <button type="submit" style={submitStyle}>
          {t("web.registre.submit")}
        </button>
      </form>

      <h2 style={{ marginTop: 40 }}>{t("web.registre.equipment_title")}</h2>
      {locations.length === 0 ? (
        <p>{t("web.registre.no_equipment")}</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 24 }}>
          <thead>
            <tr>
              <th style={headerCellStyle}>{t("web.dashboard.code")}</th>
              <th style={headerCellStyle}>{t("web.dashboard.name")}</th>
              <th style={headerCellStyle}>{t("web.registre.equipment_site")}</th>
              <th style={headerCellStyle} />
            </tr>
          </thead>
          <tbody>
            {locations.map((location) => (
              <tr key={location.id}>
                <td style={cellStyle}>
                  <Link href={`/registre/${location.id}`}>{location.code}</Link>
                </td>
                <td style={cellStyle}>{location.name}</td>
                <td style={cellStyle}>{siteName(location.site_id)}</td>
                <td style={cellStyle}>
                  <form action={showTag}>
                    <input type="hidden" name="functional_location_id" value={location.id} />
                    <input type="hidden" name="label" value={location.name} />
                    <button type="submit">{t("web.registre.tag_action")}</button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3>{t("web.registre.create_equipment_title")}</h3>
      {sites.length === 0 ? (
        <p>{t("web.registre.no_sites_yet")}</p>
      ) : (
        <form action={createEquipment} style={{ maxWidth: 400 }}>
          <label>
            {t("web.registre.equipment_site")}
            <select name="site_id" required style={fieldStyle}>
              {sites.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.name}
                </option>
              ))}
            </select>
          </label>
          <label style={labelStyle}>
            {t("web.registre.equipment_space")}
            <select name="space_id" style={fieldStyle} defaultValue="">
              <option value="">{t("web.registre.equipment_space_none")}</option>
              {spaces.map((space) => (
                <option key={space.id} value={space.id}>
                  {siteName(space.site_id)} — {t(`space_type.${space.space_type}`)} — {space.name}
                </option>
              ))}
            </select>
          </label>
          <label style={labelStyle}>
            {t("web.registre.equipment_code")}
            <input name="code" required style={fieldStyle} />
          </label>
          <label style={labelStyle}>
            {t("web.registre.equipment_name")}
            <input name="name" required style={fieldStyle} />
          </label>
          <label style={labelStyle}>
            {t("web.registre.equipment_type")}
            <select name="equipment_type" required style={fieldStyle}>
              {equipmentTypes.map((type) => (
                <option key={type.code} value={type.code}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>
          <label style={labelStyle}>
            {t("web.registre.manufacturer")}
            <input name="manufacturer" required style={fieldStyle} />
          </label>
          <label style={labelStyle}>
            {t("web.registre.reference")}
            <input name="reference" required style={fieldStyle} />
          </label>
          <label style={labelStyle}>
            {t("web.registre.serial_number")}
            <input name="serial_number" required style={fieldStyle} />
          </label>
          <button type="submit" style={submitStyle}>
            {t("web.registre.submit")}
          </button>
        </form>
      )}
    </main>
  );
}
