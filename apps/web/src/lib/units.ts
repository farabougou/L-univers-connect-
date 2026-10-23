/**
 * Symbole d'affichage d'une unité à partir de son code UCUM (le code est ce que
 * l'API enregistre et compare ; le symbole est ce qu'une personne lit : « Cel »
 * s'écrit °C, « kW.h » s'écrit kWh).
 *
 * Cette table reprend exactement `UNITS` de services/api/app/point_vocabulary.py ;
 * `units.test.ts` compare les deux, pour qu'elles ne dérivent jamais. Une unité
 * inconnue garde son code tel quel : jamais un symbole inventé.
 */
const UNIT_SYMBOLS: Record<string, string> = {
  Cel: "°C",
  K: "K",
  Pa: "Pa",
  kPa: "kPa",
  bar: "bar",
  "%": "%",
  W: "W",
  kW: "kW",
  "kW.h": "kWh",
  "[ppm]": "ppm",
  "m3/h": "m³/h",
  kg: "kg",
};

export function unitSymbol(code: string): string {
  return UNIT_SYMBOLS[code] ?? code;
}
