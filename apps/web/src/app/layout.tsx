import type { Metadata, Viewport } from "next";
import "./globals.css";

import { Sidebar, type SidebarGroup } from "@/components/Sidebar";
import { getLocale, getTranslator } from "@/lib/i18n";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getTranslator();
  return {
    title: t("common.app_name"),
    description: `${t("common.app_name")} — ${t("common.tagline")} — ${t("web.console")}`,
  };
}

/**
 * Sans cette balise, un navigateur mobile suppose une page conçue pour un
 * écran de bureau (~980px) et l'affiche dédézoomée plutôt que de respecter
 * nos règles `@media` (sidebar, tableaux responsives) — trouvé le
 * 03/10/2026 (capture d'écran mobile de Mohamed, console zoomée et
 * illisible). `width: device-width` fait correspondre la largeur CSS à la
 * largeur réelle de l'écran ; `initialScale: 1` démarre sans zoom.
 */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { t } = await getTranslator();
  const groups: SidebarGroup[] = [
    {
      label: t("web.sidebar.group_overview"),
      items: [{ href: "/", label: t("common.home") }],
    },
    {
      label: t("web.sidebar.group_operations"),
      items: [
        { href: "/registre", label: t("web.registre.title") },
        { href: "/alarmes", label: t("web.alarms_page.title") },
        { href: "/ordres-de-travail", label: t("web.work_orders.page_title") },
        { href: "/telemetrie", label: t("web.telemetry_page.title") },
      ],
    },
    {
      label: t("web.sidebar.group_energy"),
      items: [
        { href: "/energie", label: t("web.energy_page.title") },
        { href: "/operat", label: t("web.operat_page.title") },
      ],
    },
    {
      label: t("web.sidebar.group_automation"),
      items: [
        { href: "/automation", label: t("web.automation_page.title") },
        { href: "/plans", label: t("web.spatial_page.title") },
      ],
    },
    {
      label: t("web.sidebar.group_platform"),
      items: [
        { href: "/edge", label: t("web.edge.title") },
        { href: "/documents", label: t("web.documents_page.title") },
        { href: "/acces", label: t("web.access_page.title") },
      ],
    },
  ];

  return (
    <html lang={await getLocale()}>
      <body>
        <div style={{ display: "flex", minHeight: "100vh" }}>
          <Sidebar appName={t("common.app_name")} groups={groups} />
          <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
        </div>
      </body>
    </html>
  );
}
