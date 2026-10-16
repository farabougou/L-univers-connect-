/**
 * Agrégation pure pour le bloc « Énergie » du Global Command Center
 * (directive UI/dashboard du 30/09/2026, section 13). Aucun appel réseau
 * ici : la donnée brute par compteur vient de GET /energy/portfolio-summary
 * (voir apps/web/src/app/page.tsx), calculée côté API sur les compteurs
 * d'énergie validés du tenant (app/energy/aggregation.py).
 *
 * Ne calcule ni n'affiche jamais : économies, CO2 évité, ROI, conformité,
 * KPI réglementaires — strictement exclus par la directive. Production,
 * batterie, groupe électrogène et anomalie énergétique ne sont pas
 * modélisés dans le système aujourd'hui (aucune classe de point
 * correspondante) : ils ne figurent pas ici, plutôt qu'une case
 * « indisponible » permanente pour une fonctionnalité qui n'existe pas.
 */

export type PortfolioEnergyMeter = {
  point_id: string;
  functional_location_id: string;
  unit: string;
  consumption: number | null;
  previous_consumption: number | null;
};

export type EnergyUnitSummary = {
  unit: string;
  meterCount: number;
  availableCount: number;
  totalConsumption: number | null;
  trendPercent: number | null;
};

/**
 * Regroupe les compteurs par unité (jamais additionner des unités
 * différentes, par exemple kWh et m³ pour un futur compteur d'eau ou de
 * gaz). `totalConsumption` est `null` tant qu'aucun compteur de cette
 * unité n'a de donnée exploitable pour le jour de référence.
 * `trendPercent` ne compare que les compteurs disposant des deux jours
 * (courant et veille) : un compteur sans historique suffisant n'entre
 * dans aucun des deux totaux, jamais remplacé par zéro.
 */
export function summarizeEnergyByUnit(meters: PortfolioEnergyMeter[]): EnergyUnitSummary[] {
  const byUnit = new Map<string, PortfolioEnergyMeter[]>();
  for (const meter of meters) {
    const list = byUnit.get(meter.unit) ?? [];
    list.push(meter);
    byUnit.set(meter.unit, list);
  }

  return [...byUnit.entries()].map(([unit, unitMeters]) => {
    const available = unitMeters.filter((meter) => meter.consumption !== null);
    const totalConsumption = available.length
      ? available.reduce((sum, meter) => sum + (meter.consumption as number), 0)
      : null;

    const comparable = unitMeters.filter(
      (meter) => meter.consumption !== null && meter.previous_consumption !== null,
    );
    let trendPercent: number | null = null;
    if (comparable.length) {
      const currentSum = comparable.reduce((sum, meter) => sum + (meter.consumption as number), 0);
      const previousSum = comparable.reduce(
        (sum, meter) => sum + (meter.previous_consumption as number),
        0,
      );
      trendPercent = previousSum > 0 ? ((currentSum - previousSum) / previousSum) * 100 : null;
    }

    return {
      unit,
      meterCount: unitMeters.length,
      availableCount: available.length,
      totalConsumption,
      trendPercent,
    };
  });
}

export function countMetersWithoutData(meters: PortfolioEnergyMeter[]): number {
  return meters.filter((meter) => meter.consumption === null).length;
}
