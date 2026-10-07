import { describe, expect, it } from "vitest";

import {
  countCriticalOpen,
  countInProgress,
  recentClosures,
  repeatingFailures,
  type MaintenanceIntervention,
  type MaintenanceWorkOrder,
} from "./maintenance";

function wo(overrides: Partial<MaintenanceWorkOrder>): MaintenanceWorkOrder {
  return {
    id: "wo-1",
    functional_location_id: "loc-1",
    title: "Intervention",
    work_order_type: "corrective",
    priority: "medium",
    status: "open",
    ...overrides,
  };
}

describe("countInProgress", () => {
  it("ne compte que les ordres de travail en cours", () => {
    const workOrders = [
      wo({ status: "in_progress" }),
      wo({ status: "open" }),
      wo({ status: "completed" }),
    ];
    expect(countInProgress(workOrders)).toBe(1);
  });
});

describe("countCriticalOpen", () => {
  it("compte les urgents encore ouverts ou en cours, jamais les clos", () => {
    const workOrders = [
      wo({ priority: "urgent", status: "open" }),
      wo({ priority: "urgent", status: "in_progress" }),
      wo({ priority: "urgent", status: "completed" }),
      wo({ priority: "medium", status: "open" }),
    ];
    expect(countCriticalOpen(workOrders)).toBe(2);
  });
});

describe("repeatingFailures", () => {
  it("signale un équipement à partir de deux correctifs", () => {
    const workOrders = [
      wo({ functional_location_id: "loc-1", work_order_type: "corrective" }),
      wo({ functional_location_id: "loc-1", work_order_type: "corrective" }),
      wo({ functional_location_id: "loc-2", work_order_type: "corrective" }),
    ];
    expect(repeatingFailures(workOrders)).toEqual([{ functional_location_id: "loc-1", count: 2 }]);
  });

  it("ignore les ordres de travail préventifs", () => {
    const workOrders = [
      wo({ functional_location_id: "loc-1", work_order_type: "preventive" }),
      wo({ functional_location_id: "loc-1", work_order_type: "preventive" }),
    ];
    expect(repeatingFailures(workOrders)).toEqual([]);
  });

  it("trie du plus fréquent au moins fréquent", () => {
    const workOrders = [
      wo({ functional_location_id: "loc-1" }),
      wo({ functional_location_id: "loc-1" }),
      wo({ functional_location_id: "loc-2" }),
      wo({ functional_location_id: "loc-2" }),
      wo({ functional_location_id: "loc-2" }),
    ];
    expect(repeatingFailures(workOrders)).toEqual([
      { functional_location_id: "loc-2", count: 3 },
      { functional_location_id: "loc-1", count: 2 },
    ]);
  });
});

describe("recentClosures", () => {
  function intervention(overrides: Partial<MaintenanceIntervention>): MaintenanceIntervention {
    return {
      id: "int-1",
      functional_location_id: "loc-1",
      technician: "Mohamed",
      summary: null,
      ended_at: null,
      ...overrides,
    };
  }

  it("ignore les interventions jamais closes", () => {
    const interventions = [intervention({ ended_at: null })];
    expect(recentClosures(interventions, 5)).toEqual([]);
  });

  it("trie de la plus récente à la plus ancienne", () => {
    const interventions = [
      intervention({ id: "old", ended_at: "2026-09-01T00:00:00Z" }),
      intervention({ id: "new", ended_at: "2026-09-29T00:00:00Z" }),
    ];
    expect(recentClosures(interventions, 5).map((i) => i.id)).toEqual(["new", "old"]);
  });

  it("respecte la limite demandée", () => {
    const interventions = Array.from({ length: 5 }, (_, i) =>
      intervention({ id: `int-${i}`, ended_at: `2026-09-0${i + 1}T00:00:00Z` }),
    );
    expect(recentClosures(interventions, 2)).toHaveLength(2);
  });
});
