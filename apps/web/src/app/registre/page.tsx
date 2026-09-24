import Link from "next/link";
import QRCode from "qrcode";

import type { Translator } from "@/i18n/translator";
import { apiFetch, requireAccessToken } from "@/lib/api";
import {
  cellStyle,
  fieldStyle,
  headerCellStyle,
  labelStyle,
  submitStyle,
} from "@/lib/formStyles";
import { errorMessage, getTranslator } from "@/lib/i18n";

import {
  closeSpace,
  createEquipment,
  createSite,
  createSpace,
  showTag,
  updateSiteTimezone,
} from "./actions";

type Me = { roles: string[] };
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

const MANAGE_ROLES = ["responsable_exploitation", "admin_tenant"];
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
  searchParams: Promise<{ error?: string; tag?: string; label?: string }>;
}) {
  const accessToken = await requireAccessToken();
  const translator = await getTranslator();
  const { t } = translator;
  const params = await searchParams;
  const error = creationError(translator, params.error);

  const meResponse = await apiFetch("/me", accessToken);
  const me: Me = meResponse.ok ? await meResponse.json() : { roles: [] };
  const canManage = me.roles.some((role) => MANAGE_ROLES.includes(role));

  if (!canManage) {
    return (
      <main style={{ maxWidth: 720, margin: "40px auto", padding: "0 16px" }}>
        <Link href="/">← {t("common.back")}</Link>
        <h1>{t("web.registre.title")}</h1>
        <p>{t("web.registre.access_denied")}</p>
      </main>
    );
  }

  const [sitesResponse, locationsResponse, typesResponse, spacesResponse] = await Promise.all([
    apiFetch("/sites", accessToken),
    apiFetch("/functional-locations", accessToken),
    apiFetch("/equipment-types", accessToken),
    apiFetch("/spaces", accessToken),
  ]);
  const sites: Site[] = sitesResponse.ok ? await sitesResponse.json() : [];
  const locations: FunctionalLocation[] = locationsResponse.ok ? await locationsResponse.json() : [];
  const equipmentTypes: EquipmentType[] = typesResponse.ok
    ? (await typesResponse.json()).types
    : [];
  const spaces: Space[] = spacesResponse.ok ? await spacesResponse.json() : [];
  const siteName = (siteId: string) => sites.find((site) => site.id === siteId)?.name ?? siteId;
  const spaceLabel = (spaceId: string) => {
    const space = spaces.find((candidate) => candidate.id === spaceId);
    return space ? `${t(`space_type.${space.space_type}`)} — ${space.name}` : spaceId;
  };

  let tagSvg: string | null = null;
  if (params.tag) {
    tagSvg = await QRCode.toString(params.tag, { type: "svg", margin: 1, width: 220 });
  }

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
