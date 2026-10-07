/**
 * Couleurs sémantiques partagées (ADR 014, Design System commun) : même
 * signification et mêmes teintes que côté web — `SEVERITY_COLOR`
 * (apps/web/src/lib/portfolio.ts) et `ASSET_STATUS_COLOR`
 * (apps/web/src/components/StatusBadge.tsx). Un rouge, un vert ou un orange
 * veulent dire la même chose sur les deux applications ; dupliqué ici
 * (comme `roles.ts`) car web et mobile ne partagent pas de code.
 *
 * Jetons de confort (06/10/2026, directive de Mohamed avec maquette de
 * référence) : palette sombre/navy premium, alignée sur celle du web
 * (`apps/web/src/lib/formStyles.ts`) — remplace le choix précédent (fond
 * clair pour la lecture en plein soleil, 02/10/2026). Décision produit
 * explicite et documentée, pas un oubli de cette justification antérieure :
 * Mohamed a fourni une maquette précise à reprendre telle quelle. Le bleu
 * reste réservé à la navigation/aux actions, le vert/orange/rouge
 * uniquement aux états opérationnels (`SEVERITY_COLOR`, `ASSET_STATUS_COLOR`
 * ci-dessous) — jamais à la décoration.
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
  background: "#050b1a",
  surface: "#0f1b33",
  surfaceRaised: "#15213d",
  border: "#1e293b",
  divider: "#1e293b",
  textPrimary: "#f8fafc",
  textMuted: "#94a3b8",
  link: "#38bdf8",
  accent: "#38bdf8",
  accentStrong: "#1d4ed8",
  danger: "#f87171",
  // Non sélectionné (bouton de choix, option de secours).
  inactive: "#64748b",
  selectedBorder: "#38bdf8",
  selectedBackground: "#15213d",
  // Superposition derrière le menu tiroir (Modal), jamais une vraie sidebar.
  overlay: "rgba(2, 6, 16, 0.6)",
};
