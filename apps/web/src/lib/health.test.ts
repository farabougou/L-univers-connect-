import { describe, expect, it } from "vitest";

import { distributeByAssetStatus, type PortfolioEquipmentStatus } from "./health";

function status(overrides: Partial<PortfolioEquipmentStatus>): PortfolioEquipmentStatus {
  return {
    functional_location_id: "loc-1",
    operational_status: "running",
    communication_status: "online",
    current: true,
    reason: null,
    ...overrides,
  };
}

describe("distributeByAssetStatus", () => {
  it("classe un équipement sans point d'état comme inconnu", () => {
    const distribution = distributeByAssetStatus([
      status({ functional_location_id: "a", reason: "no_status_point" }),
    ]);
    expect(distribution.unknown).toEqual(["a"]);
    expect(distribution.normal).toEqual([]);
  });

  it("classe un équipement hors ligne indépendamment de son dernier état de fonctionnement", () => {
    const distribution = distributeByAssetStatus([
      status({
        functional_location_id: "a",
        communication_status: "offline",
        operational_status: "running",
        current: false,
      }),
    ]);
    expect(distribution.offline).toEqual(["a"]);
  });

  it("classe un défaut signalé comme critique", () => {
    const distribution = distributeByAssetStatus([
      status({ functional_location_id: "a", operational_status: "fault" }),
    ]);
    expect(distribution.critical).toEqual(["a"]);
  });

  it("classe une donnée non actuelle comme donnée ancienne, hors le cas hors ligne", () => {
    const distribution = distributeByAssetStatus([
      status({ functional_location_id: "a", current: false }),
    ]);
    expect(distribution.stale).toEqual(["a"]);
  });

  it("classe un équipement sain comme normal", () => {
    const distribution = distributeByAssetStatus([status({ functional_location_id: "a" })]);
    expect(distribution.normal).toEqual(["a"]);
  });

  it("répartit plusieurs équipements sur plusieurs catégories", () => {
    const distribution = distributeByAssetStatus([
      status({ functional_location_id: "a" }),
      status({ functional_location_id: "b", reason: "no_status_point" }),
      status({ functional_location_id: "c", operational_status: "fault" }),
    ]);
    expect(distribution.normal).toEqual(["a"]);
    expect(distribution.unknown).toEqual(["b"]);
    expect(distribution.critical).toEqual(["c"]);
  });

  it("ne classe jamais rien comme attention ou maintenance (aucune donnée ne le prouve aujourd'hui)", () => {
    const distribution = distributeByAssetStatus([
      status({ functional_location_id: "a" }),
      status({ functional_location_id: "b", reason: "no_status_point" }),
      status({ functional_location_id: "c", operational_status: "fault" }),
      status({ functional_location_id: "d", communication_status: "offline", current: false }),
      status({ functional_location_id: "e", current: false }),
    ]);
    expect(distribution.attention).toEqual([]);
    expect(distribution.maintenance).toEqual([]);
  });
});
