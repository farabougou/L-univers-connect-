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
import { getTranslator } from "@/lib/i18n";
import { keycloakAdminConsoleUrl } from "@/lib/keycloak";
import { config } from "@/lib/config";
import { roleLabels } from "@/lib/roles";

/**
 * Page Users & Access (directive UI/dashboard, section 36, point 11).
 *
 * Les comptes et les rôles vivent uniquement dans Keycloak
 * (`realm_access.roles` du jeton, voir app/auth.py) : il n'existe aucune
 * table locale d'utilisateurs. Lister ou gérer les comptes d'un tenant
 * exigerait d'appeler l'API d'administration Keycloak — un compte de
 * service avec droits d'administration sur le realm, donc un nouveau
 * secret et une nouvelle intégration externe (voir
 * docs/spec/feature-benchmark-matrix.md, section 36 point 11 : signalé
 * comme arrêt explicite, décision requise avant ce code-là).
 *
 * Ce que cette page montre sans rien de tout cela : l'identité et les
 * rôles de la personne connectée (déjà disponibles via GET /me), le
 * catalogue des rôles du produit et ce que chacun permet, et un lien
 * direct vers la console d'administration Keycloak pour gérer les
 * comptes — dérivé de l'adresse OIDC déjà configurée, jamais un nouveau
 * secret.
 */

type Me = { sub: string | null; roles: string[]; tenant_id: string | null };

const PRODUCT_ROLES = [
  "technicien",
  "responsable_exploitation",
  "admin_tenant",
] as const;

export default async function AccessPage() {
  const accessToken = await requireAccessToken();
  const { t } = await getTranslator();

  const meResponse = await apiFetch("/me", accessToken);
  const me: Me = meResponse.ok
    ? await meResponse.json()
    : { sub: null, roles: [], tenant_id: null };
  const adminConsoleUrl = keycloakAdminConsoleUrl(config.oidcIssuer);

  return (
    <main style={pageContainerStyle}>
      <Link href="/" style={{ color: colors.accent }}>
        ← {t("common.back")}
      </Link>
      <h1 style={{ fontSize: 24, margin: "12px 0 20px" }}>
        {t("web.access_page.title")}
      </h1>
      <p style={{ color: colors.textMuted, marginBottom: 20, maxWidth: 720 }}>
        {t("web.access_page.intro")}
      </p>

      <section style={{ ...cardStyle, marginBottom: 24 }}>
        <h2 style={sectionTitleStyle}>{t("web.access_page.you_title")}</h2>
        <p>
          {t("web.access_page.you_identity", { identity: me.sub ?? "—" })}
          <br />
          {t("web.access_page.you_roles", {
            roles: me.roles.length > 0 ? roleLabels(me.roles, t) : "—",
          })}
        </p>
      </section>

      <section
        style={{
          ...cardStyle,
          padding: 0,
          overflow: "hidden",
          marginBottom: 24,
        }}
      >
        <div style={{ padding: "20px 24px 0" }}>
          <h2 style={sectionTitleStyle}>{t("web.access_page.roles_title")}</h2>
        </div>
        <div style={tableScrollStyle}>
          <table
            className="responsive-table"
            style={{ width: "100%", borderCollapse: "collapse" }}
          >
            <thead>
              <tr>
                <th style={headerCellStyle}>{t("web.access_page.col_role")}</th>
                <th style={headerCellStyle}>
                  {t("web.access_page.col_capability")}
                </th>
              </tr>
            </thead>
            <tbody>
              {PRODUCT_ROLES.map((role) => (
                <tr key={role}>
                  <td
                    data-label={t("web.access_page.col_role")}
                    style={cellStyle}
                  >
                    {t(`role.${role}`)}
                  </td>
                  <td
                    data-label={t("web.access_page.col_capability")}
                    style={cellStyle}
                  >
                    {t(`web.access_page.capability.${role}`)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>{t("web.access_page.manage_title")}</h2>
        <p style={{ color: colors.textMuted, marginBottom: 12 }}>
          {t("web.access_page.manage_explanation")}
        </p>
        {adminConsoleUrl ? (
          <a
            href={adminConsoleUrl}
            target="_blank"
            rel="noreferrer"
            style={{ color: colors.accent }}
          >
            {t("web.access_page.manage_link")} ↗
          </a>
        ) : (
          <p style={{ color: colors.textMuted }}>
            {t("web.access_page.manage_unavailable")}
          </p>
        )}
      </section>
    </main>
  );
}
