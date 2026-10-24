import { describe, expect, it } from "vitest";

import { summarizeTelemetry, type TelemetryEntry, originLabelKey } from "./telemetry";

function entry(overrides: Partial<TelemetryEntry>): TelemetryEntry {
  return {
    point_id: "point-1",
    functional_location_id: "loc-1",
    code: "sdm120.puissance",
    name: "Puissance active",
    point_class: "electric_power_sensor",
    unit: "W",
    value: 548,
    measured_at: "2026-10-23T08:00:00Z",
    stale: false,
    ...overrides,
  };
}

describe("summarizeTelemetry", () => {
  it("renvoie des zéros pour un portefeuille sans point", () => {
    expect(summarizeTelemetry([])).toEqual({ total: 0, current: 0, stale: 0, neverMeasured: 0 });
  });

  it("compte les points à jour, anciens et jamais mesurés", () => {
    const summary = summarizeTelemetry([
      entry({ point_id: "a" }),
      entry({ point_id: "b" }),
      entry({ point_id: "c", stale: true }),
      entry({ point_id: "d", measured_at: null, value: null, stale: null }),
    ]);

    expect(summary).toEqual({ total: 4, current: 2, stale: 1, neverMeasured: 1 });
  });

  it("un point jamais mesuré n'est jamais compté comme à jour ni comme ancien", () => {
    const summary = summarizeTelemetry([entry({ measured_at: null, value: null, stale: false })]);

    expect(summary.current).toBe(0);
    expect(summary.stale).toBe(0);
    expect(summary.neverMeasured).toBe(1);
  });

  it("ne classe pas dans « à jour » un point dont la fraîcheur est inconnue", () => {
    const summary = summarizeTelemetry([entry({ stale: null })]);

    expect(summary).toEqual({ total: 1, current: 0, stale: 0, neverMeasured: 0 });
  });

  it("la somme des trois catégories ne dépasse jamais le total", () => {
    const entries = [
      entry({ point_id: "a" }),
      entry({ point_id: "b", stale: true }),
      entry({ point_id: "c", measured_at: null, stale: null }),
      entry({ point_id: "d", stale: null }),
    ];
    const summary = summarizeTelemetry(entries);

    expect(summary.current + summary.stale + summary.neverMeasured).toBeLessThanOrEqual(
      summary.total,
    );
  });
});

describe("originLabelKey", () => {
  it("ne dit rien d'une mesure : c'est le cas normal", () => {
    expect(originLabelKey("measured")).toBeNull();
  });

  it("ne dit rien sans relevé (origine absente)", () => {
    expect(originLabelKey(null)).toBeNull();
    expect(originLabelKey(undefined)).toBeNull();
  });

  it("nomme toute valeur qui n'est pas une mesure (jamais présentée comme telle)", () => {
    expect(originLabelKey("manual")).toBe("web.telemetry_page.origin_manual");
    expect(originLabelKey("simulated")).toBe("web.telemetry_page.origin_simulated");
    expect(originLabelKey("derived")).toBe("web.telemetry_page.origin_derived");
    expect(originLabelKey("estimated")).toBe("web.telemetry_page.origin_estimated");
  });

  it("ignore une origine inconnue plutôt que d'afficher un code technique", () => {
    expect(originLabelKey("autre-chose")).toBeNull();
  });
});
