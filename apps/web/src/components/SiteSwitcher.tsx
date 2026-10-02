import Link from "next/link";

import { colors } from "@/lib/formStyles";

/**
 * Changement rapide de site (directive Command Center, ADR 014 §36.2, même
 * ligne que Breadcrumb.tsx) : une liste déroulante pure HTML (`<details>`),
 * sans JavaScript, vers la vue Portfolio déjà filtrable par site
 * (`/?site={id}`, apps/web/src/app/page.tsx — mécanisme existant, pas
 * construit pour ce composant). N'affiche rien pour un client à un seul
 * site — rien à changer.
 */
export function SiteSwitcher({
  sites,
  currentSiteId,
  label,
}: {
  sites: { id: string; name: string }[];
  currentSiteId: string | null;
  label: string;
}) {
  const others = sites.filter((site) => site.id !== currentSiteId);
  if (others.length === 0) return null;
  return (
    <details style={{ display: "inline-block", marginLeft: 8, position: "relative" }}>
      <summary
        style={{ cursor: "pointer", fontSize: 13, color: colors.accent, display: "inline" }}
      >
        {label}
      </summary>
      <ul
        style={{
          listStyle: "none",
          margin: "4px 0 0",
          padding: 4,
          position: "absolute",
          zIndex: 1,
          background: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: 6,
          boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
          minWidth: 160,
        }}
      >
        {others.map((site) => (
          <li key={site.id}>
            <Link
              href={`/?site=${site.id}`}
              style={{
                display: "block",
                padding: "6px 10px",
                color: colors.textPrimary,
                whiteSpace: "nowrap",
              }}
            >
              {site.name}
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}
