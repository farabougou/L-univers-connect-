import Link from "next/link";
import type { ReactNode } from "react";

import { colors } from "@/lib/formStyles";

/**
 * Tuile d'indicateur du bandeau « Vue d'ensemble » de l'accueil : un grand
 * nombre, son libellé, une barre de couleur en haut. La couleur ne porte
 * jamais le sens seule (directive UI/dashboard, section 33) : le nombre, le
 * libellé et les pastilles de gravité passées en `children` le disent aussi.
 * Toute la tuile est un lien quand `href` est fourni.
 */
export function KpiTile({
  label,
  value,
  accent,
  href,
  children,
}: {
  label: string;
  value: string;
  accent: string;
  href?: string;
  children?: ReactNode;
}) {
  const style = {
    background: colors.pageBackground,
    border: `1px solid ${colors.border}`,
    borderTop: `3px solid ${accent}`,
    borderRadius: 10,
    padding: "14px 16px",
    minWidth: 0,
  };
  const body = (
    <>
      <div
        style={{
          fontSize: 34,
          fontWeight: 700,
          lineHeight: 1.1,
          color: colors.textPrimary,
        }}
      >
        {value}
      </div>
      <div style={{ color: colors.textMuted, fontSize: 13, marginTop: 4 }}>
        {label}
      </div>
      {children ? <div style={{ marginTop: 10 }}>{children}</div> : null}
    </>
  );
  if (!href) {
    return <div style={style}>{body}</div>;
  }
  return (
    <Link
      href={href}
      style={{
        ...style,
        display: "block",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      {body}
    </Link>
  );
}
