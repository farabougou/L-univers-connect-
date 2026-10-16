/**
 * Agrégation pure pour le bloc « Santé des actifs » du Global Command
 * Center (directive UI/dashboard du 30/09/2026, section 15). Aucun appel
 * réseau ici : la donnée brute par équipement vient de GET
 * /functional-locations/status-summary (voir apps/web/src/app/page.tsx),
 * calculée côté API sur tout le portefeuille en une poignée de requêtes
 * (app/equipment_status.py::compute_portfolio_equipment_status) — jamais un
 * appel par équipement depuis le navigateur.
 */

import { equipmentStatusToAssetStatus, type AssetStatus } from "@/components/StatusBadge";

export type PortfolioEquipmentStatus = {
  functional_location_id: string;
  operational_status: string;
  communication_status: string;
  current: boolean;
  reason: string | null;
};

// Ordre de la directive (section 15) : jamais alphabétique ni par gravité.
export const ASSET_STATUS_ORDER: AssetStatus[] = [
  "normal",
  "attention",
  "critical",
  "offline",
  "stale",
  "unknown",
  "maintenance",
];

export type AssetStatusDistribution = Record<AssetStatus, string[]>;

function emptyDistribution(): AssetStatusDistribution {
  return { normal: [], attention: [], critical: [], offline: [], stale: [], unknown: [], maintenance: [] };
}

/**
 * Répartit les identifiants d'équipement par catégorie de l'état universel,
 * via `equipmentStatusToAssetStatus` (même règle que la cellule de statut de
 * la vue Portfolio) — jamais une seconde logique de classement.
 */
export function distributeByAssetStatus(
  statuses: PortfolioEquipmentStatus[],
): AssetStatusDistribution {
  const distribution = emptyDistribution();
  for (const status of statuses) {
    distribution[equipmentStatusToAssetStatus(status)].push(status.functional_location_id);
  }
  return distribution;
}
