/**
 * Couleurs sémantiques partagées (ADR 014, Design System commun) : même
 * signification et mêmes teintes que côté web — `SEVERITY_COLOR`
 * (apps/web/src/lib/portfolio.ts) et `ASSET_STATUS_COLOR`
 * (apps/web/src/components/StatusBadge.tsx). Un rouge, un vert ou un orange
 * veulent dire la même chose sur les deux applications ; dupliqué ici
 * (comme `roles.ts`) car web et mobile ne partagent pas de code.
 *
 * Les jetons de confort (fond, bordure, texte) restent volontairement
 * différents de la palette sombre « centre de contrôle » du web
 * (apps/web/src/lib/formStyles.ts) : un technicien lit cet écran dehors, en
 * plein soleil, parfois avec des gants — fond clair et contrastes élevés,
 * jamais une version compressée de l'écran de bureau (directive de
 * Mohamed, 02/10/2026 : le mobile terrain n'est pas un desktop réduit).
 */

export const SEVERITY_COLOR: Record<string, string> = {
  critical: "#dc2626",
  major: "#ea580c",
  warning: "#d97706",
  info: "#6b7280",
};

export type AssetStatus =
  | "normal"
  | "attention"
  | "critical"
  | "offline"
  | "stale"
  | "unknown"
  | "maintenance";

export const ASSET_STATUS_COLOR: Record<AssetStatus, string> = {
  normal: "#16a34a",
  attention: "#d97706",
  critical: "#dc2626",
  offline: "#6b7280",
  stale: "#a16207",
  unknown: "#9ca3af",
  maintenance: "#2563eb",
};

// Même glyphe que ASSET_STATUS_GLYPH côté web : jamais la couleur seule pour
// porter le sens (ADR 013, accessibilité).
export const ASSET_STATUS_GLYPH: Record<AssetStatus, string> = {
  normal: "●",
  attention: "▲",
  critical: "■",
  offline: "○",
  stale: "◐",
  unknown: "?",
  maintenance: "⚙",
};

/**
 * Même règle que `equipmentStatusToAssetStatus` côté web : ne devine jamais
 * « attention » ni « maintenance » sans preuve, jamais un état affiché sans
 * donnée pour le justifier.
 */
export function equipmentStatusToAssetStatus(status: {
  operational_status: string;
  communication_status: string;
  current: boolean;
  reason: string | null;
}): AssetStatus {
  if (status.reason === "no_status_point" || status.reason === "no_measurement") {
    return "unknown";
  }
  if (status.communication_status === "offline" || status.communication_status === "unreachable") {
    return "offline";
  }
  if (status.operational_status === "fault") {
    return "critical";
  }
  if (!status.current) {
    return "stale";
  }
  if (status.operational_status === "unknown") {
    return "unknown";
  }
  return "normal";
}

export const colors = {
  background: "#ffffff",
  surface: "#f8fafc",
  border: "#d1d5db",
  divider: "#e5e7eb",
  textPrimary: "#111827",
  textMuted: "#4b5563",
  link: "#1d4ed8",
  danger: "#c0392b",
  // Non sélectionné (bouton de choix, option de secours) : même teinte que
  // ASSET_STATUS_COLOR.unknown, par cohérence plutôt que par coïncidence.
  inactive: "#9ca3af",
  selectedBorder: "#2563eb",
  selectedBackground: "#dbeafe",
};
