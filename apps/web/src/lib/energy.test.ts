import { describe, expect, it } from "vitest";

import {
  countMetersWithoutData,
  summarizeEnergyByUnit,
  type PortfolioEnergyMeter,
} from "./energy";

function meter(overrides: Partial<PortfolioEnergyMeter>): PortfolioEnergyMeter {
  return {
    point_id: "point-1",
    functional_location_id: "loc-1",
    unit: "kW.h",
    consumption: 100,
    previous_consumption: 80,
    ...overrides,
  };
}

describe("summarizeEnergyByUnit", () => {
  it("additionne les compteurs disponibles d'une même unité", () => {
    const meters = [
      meter({ point_id: "a", consumption: 100 }),
      meter({ point_id: "b", consumption: 50 }),
    ];
    const [summary] = summarizeEnergyByUnit(meters);
    expect(summary.unit).toBe("kW.h");
    expect(summary.meterCount).toBe(2);
    expect(summary.availableCount).toBe(2);
    expect(summary.totalConsumption).toBe(150);
  });

  it("ne mélange jamais deux unités différentes", () => {
    const meters = [
      meter({ point_id: "a", unit: "kW.h", consumption: 100 }),
      meter({ point_id: "b", unit: "m3", consumption: 30 }),
    ];
    const summaries = summarizeEnergyByUnit(meters);
    expect(summaries).toHaveLength(2);
    expect(summaries.find((s) => s.unit === "kW.h")?.totalConsumption).toBe(100);
    expect(summaries.find((s) => s.unit === "m3")?.totalConsumption).toBe(30);
  });

  it("totalConsumption est nul quand aucun compteur n'a de donnée", () => {
    const meters = [meter({ consumption: null, previous_consumption: null })];
    const [summary] = summarizeEnergyByUnit(meters);
    expect(summary.availableCount).toBe(0);
    expect(summary.totalConsumption).toBeNull();
  });

  it("un compteur sans donnée courante n'entre pas dans le total mais ne casse pas les autres", () => {
    const meters = [
      meter({ point_id: "a", consumption: 100 }),
      meter({ point_id: "b", consumption: null, previous_consumption: null }),
    ];
    const [summary] = summarizeEnergyByUnit(meters);
    expect(summary.meterCount).toBe(2);
    expect(summary.availableCount).toBe(1);
    expect(summary.totalConsumption).toBe(100);
  });

  it("calcule la tendance uniquement sur les compteurs ayant les deux jours", () => {
    const meters = [
      meter({ point_id: "a", consumption: 120, previous_consumption: 100 }),
      meter({ point_id: "b", consumption: 60, previous_consumption: null }),
    ];
    const [summary] = summarizeEnergyByUnit(meters);
    // Seul le compteur "a" est comparable : (120-100)/100 = 20%.
    expect(summary.trendPercent).toBe(20);
  });

  it("la tendance est nulle si aucun compteur n'a les deux jours", () => {
    const meters = [meter({ consumption: 100, previous_consumption: null })];
    const [summary] = summarizeEnergyByUnit(meters);
    expect(summary.trendPercent).toBeNull();
  });

  it("la tendance est nulle si le total de la veille est nul", () => {
    const meters = [meter({ consumption: 10, previous_consumption: 0 })];
    const [summary] = summarizeEnergyByUnit(meters);
    expect(summary.trendPercent).toBeNull();
  });
});

describe("countMetersWithoutData", () => {
  it("compte les compteurs sans consommation exploitable pour le jour de référence", () => {
    const meters = [
      meter({ point_id: "a", consumption: 100 }),
      meter({ point_id: "b", consumption: null }),
      meter({ point_id: "c", consumption: null }),
    ];
    expect(countMetersWithoutData(meters)).toBe(2);
  });
});
