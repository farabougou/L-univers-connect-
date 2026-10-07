/**
 * Portefeuille énergie — écran terrain « Énergie » (app/energie.tsx).
 * Réutilise GET /energy/portfolio-summary (déjà existant, même endpoint que
 * le bloc « Énergie » du Global Command Center web) et GET
 * /functional-locations pour le code/nom de l'équipement de chaque
 * compteur — aucun nouvel endpoint.
 *
 * Lecture brute uniquement (consommation par compteur, actuelle et
 * précédente) : jamais d'économies, de CO2 évité ni de ROI fabriqués ici —
 * ce que le moteur énergétique (app/energy/) ne calcule pas, cet écran ne
 * l'invente pas non plus.
 */

type RawFunctionalLocation = { id: string; code: string; name: string };

type RawMeter = {
  point_id: string;
  functional_location_id: string;
  unit: string;
  consumption: number | null;
  previous_consumption: number | null;
};

type RawPortfolioSummary = { reference_date: string; meters: RawMeter[] };

export type EnergyMeter = {
  pointId: string;
  equipmentCode: string;
  equipmentName: string;
  unit: string;
  consumption: number | null;
  previousConsumption: number | null;
};

export async function fetchEnergyPortfolio(
  apiUrl: string,
  accessToken: string,
): Promise<{ referenceDate: string | null; meters: EnergyMeter[] }> {
  const [summaryResponse, locationsResponse] = await Promise.all([
    fetch(`${apiUrl}/energy/portfolio-summary`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    }),
    fetch(`${apiUrl}/functional-locations`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    }),
  ]);
  if (!summaryResponse.ok) {
    return { referenceDate: null, meters: [] };
  }
  const summary = (await summaryResponse.json()) as RawPortfolioSummary;
  const locationList: RawFunctionalLocation[] = locationsResponse.ok
    ? await locationsResponse.json()
    : [];
  const locationById = new Map(locationList.map((location) => [location.id, location]));

  const meters: EnergyMeter[] = summary.meters.map((meter) => {
    const location = locationById.get(meter.functional_location_id);
    return {
      pointId: meter.point_id,
      equipmentCode: location?.code ?? "",
      equipmentName: location?.name ?? "",
      unit: meter.unit,
      consumption: meter.consumption,
      previousConsumption: meter.previous_consumption,
    };
  });

  return { referenceDate: summary.reference_date, meters };
}
