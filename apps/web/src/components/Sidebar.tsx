"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { BrandMark } from "@/components/BrandMark";
import { colors } from "@/lib/formStyles";

export type SidebarGroup = {
  label: string;
  items: { href: string; label: string }[];
};

/**
 * Navigation persistante de la console web (directive de Mohamed, 02/10/2026 :
 * « centre de contrôle moderne », sidebar + navigation claire). Remplace
 * progressivement la page d'accueil comme seul point d'entrée vers chaque
 * section — reste additive, n'efface aucun écran existant. Masquée sur
 * `/login` (pas de session à faire naviguer) et sous 900px de large : en
 * dessous, l'application mobile dédiée (Expo) reste le point d'entrée
 * terrain, par choix d'architecture (voir CLAUDE.md, répartition
 * web/mobile), pas par oubli de responsive.
 */
export function Sidebar({ appName, groups }: { appName: string; groups: SidebarGroup[] }) {
  const pathname = usePathname();
  if (pathname === "/login") return null;

  return (
    <nav
      className="app-sidebar"
      style={{
        width: 240,
        flexShrink: 0,
        background: colors.surface,
        borderRight: `1px solid ${colors.border}`,
        padding: "20px 12px",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        gap: 24,
      }}
    >
      <Link
        href="/"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 8px",
          color: colors.textPrimary,
        }}
      >
        <BrandMark variant="mono" size={24} label={appName} />
        <span style={{ fontSize: 15, fontWeight: 700, letterSpacing: "0.02em" }}>{appName}</span>
      </Link>

      {groups.map((group) => (
        <div key={group.label}>
          <p
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: colors.textMuted,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              padding: "0 8px",
              marginBottom: 6,
            }}
          >
            {group.label}
          </p>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {group.items.map((item) => {
              const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    style={{
                      display: "block",
                      padding: "8px 8px",
                      borderRadius: 6,
                      fontSize: 14,
                      color: active ? colors.textPrimary : colors.textMuted,
                      background: active ? colors.accentStrong : "transparent",
                    }}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
