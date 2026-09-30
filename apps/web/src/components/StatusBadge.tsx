/**
 * Langage d'état universel (directive de Mohamed du 30/09/2026, section 5) :
 * un seul vocabulaire et un seul jeu de couleurs pour l'état d'un actif,
 * partout où il apparaît (accueil, sites, équipements, Edge...). Jamais de
 * couleur codée en dur dans une page — tout passe par `ASSET_STATUS_COLOR`
 * ici.
 *
 * Ce badge est pour l'état d'un ACTIF (opérationnel/communication/
 * fraîcheur), jamais pour la gravité d'une alarme ou d'un constat : les deux
 * notions restent distinctes (directive, section 24 — « éviter de tout
 * appeler alarme »), même si elles partagent la même charte de couleurs par
 * cohérence visuelle.
 */
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

// Glyphe simple (pas de bibliothèque d'icônes) : jamais la couleur seule
// pour porter le sens (directive, section 33 — accessibilité).
const ASSET_STATUS_GLYPH: Record<AssetStatus, string> = {
  normal: "●",
  attention: "▲",
  critical: "■",
  offline: "○",
  stale: "◐",
  unknown: "?",
  maintenance: "⚙",
};

export function StatusBadge({ status, label }: { status: AssetStatus; label: string }) {
  return (
    <span
      role="status"
      aria-label={label}
      title={label}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        color: "white",
        background: ASSET_STATUS_COLOR[status],
        borderRadius: 999,
        padding: "2px 10px",
        fontSize: 12,
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      <span aria-hidden="true">{ASSET_STATUS_GLYPH[status]}</span>
      {label}
    </span>
  );
}

/**
 * État d'un équipement (`app/equipment_status.py` via `GET
 * /functional-locations/{id}/status`) traduit vers le vocabulaire universel.
 * Ne devine jamais « attention » ni « maintenance » : ces deux états
 * demanderaient une donnée que cette réponse ne porte pas aujourd'hui
 * (intervention en cours, seuil d'alerte) — jamais un état affiché sans
 * preuve (règle « on n'invente jamais »).
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
