/**
 * Calculs purs du bandeau « Vue d'ensemble » de l'accueil (directive
 * UI/dashboard du 30/09/2026) : quelle gravité colore une tuile, et quelle
 * part de la barre de santé revient à chaque état. Aucun appel réseau, aucun
 * texte : l'affichage vit dans `components/KpiTile.tsx` et `HealthBar.tsx`.
 *
 * Rien n'est inventé ici : la couleur d'une tuile vient de la gravité la plus
 * élevée réellement ouverte, la barre ne montre que les équipements dont l'état
 * est connu de l'API (jamais un score global composé).
 */

import { ASSET_STATUS_ORDER, type AssetStatusDistribution } from "./health";
import { SEVERITIES, type Severity, type SeverityCounts } from "./portfolio";
import { type AssetStatus } from "@/components/StatusBadge";

/** La gravité la plus élevée présente, ou `null` si rien n'est ouvert. */
export function highestSeverity(counts: SeverityCounts): Severity | null {
  return SEVERITIES.find((severity) => counts[severity] > 0) ?? null;
}

export type HealthSegment = {
  status: AssetStatus;
  count: number;
  /** Part du total des équipements classés, de 0 à 100. */
  percent: number;
};

/**
 * Les états réellement présents, dans l'ordre de la directive (section 15),
 * avec leur part du total. Liste vide si aucun équipement n'est classé : le
 * bandeau affiche alors l'absence d'équipement, pas une barre vide.
 */
export function healthSegments(distribution: AssetStatusDistribution): HealthSegment[] {
  const total = ASSET_STATUS_ORDER.reduce((sum, status) => sum + distribution[status].length, 0);
  if (total === 0) return [];
  return ASSET_STATUS_ORDER.filter((status) => distribution[status].length > 0).map((status) => ({
    status,
    count: distribution[status].length,
    percent: (distribution[status].length / total) * 100,
  }));
}
