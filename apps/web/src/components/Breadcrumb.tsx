import Link from "next/link";

import { colors } from "@/lib/formStyles";

/**
 * Navigation universelle (directive Command Center, ADR 014 §36.2) : fil
 * d'Ariane commun à toute la console, construit progressivement écran par
 * écran plutôt qu'en un seul passage (feature-benchmark-matrix.md, ligne
 * « Navigation universelle »). Un segment sans destination connue (ex. un
 * espace, qui n'a pas encore de fiche dédiée) reste du texte, jamais un lien
 * mort — la hiérarchie doit rester exploitable même quand un niveau n'a pas
 * encore d'écran.
 */
export type BreadcrumbSegment = { label: string; href: string | null };

export function Breadcrumb({ segments }: { segments: BreadcrumbSegment[] }) {
  return (
    <nav aria-label="fil d’Ariane" style={{ fontSize: 13, color: colors.textMuted }}>
      {segments.map((segment, index) => (
        <span key={index}>
          {index > 0 && " › "}
          {segment.href ? (
            <Link href={segment.href} style={{ color: colors.textMuted }}>
              {segment.label}
            </Link>
          ) : (
            segment.label
          )}
        </span>
      ))}
    </nav>
  );
}
