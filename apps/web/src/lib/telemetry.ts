/**
 * Données et résumé de l'écran Télémétrie (directive UI/dashboard, section 36
 * point 9). Calcul pur, sans appel réseau : la dernière valeur de chaque point
 * validé vient de GET /telemetry/portfolio-latest.
 *
 * Le résumé ne dit que ce que l'API sait. Un point jamais mesuré n'est ni « à
 * jour » ni « ancien » ; un point mesuré dont la fraîcheur est inconnue
 * (`stale` nul) n'entre dans aucune des trois catégories, seulement dans le
 * total : jamais classé « à jour » faute de preuve.
 */

export type TelemetryEntry = {
  point_id: string;
  functional_location_id: string | null;
  code: string;
  name: string;
  point_class: string | null;
  unit: string | null;
  value: number | null;
  measured_at: string | null;
  stale: boolean | null;
};

export type TelemetrySummary = {
  total: number;
  /** Mesuré, dans le délai attendu de son intervalle. */
  current: number;
  /** Mesuré, mais plus récemment que l'intervalle attendu ne le permet. */
  stale: number;
  /** Aucune mesure reçue. */
  neverMeasured: number;
};

export function summarizeTelemetry(
  entries: Pick<TelemetryEntry, "measured_at" | "stale">[],
): TelemetrySummary {
  const summary: TelemetrySummary = { total: entries.length, current: 0, stale: 0, neverMeasured: 0 };
  for (const entry of entries) {
    if (entry.measured_at === null) {
      summary.neverMeasured += 1;
    } else if (entry.stale === true) {
      summary.stale += 1;
    } else if (entry.stale === false) {
      summary.current += 1;
    }
  }
  return summary;
}
