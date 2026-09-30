import { describe, expect, it } from "vitest";

import { equipmentStatusToAssetStatus } from "./StatusBadge";

function status(overrides: Partial<Parameters<typeof equipmentStatusToAssetStatus>[0]>) {
  return {
    operational_status: "running",
    communication_status: "online",
    current: true,
    reason: null,
    ...overrides,
  };
}

describe("equipmentStatusToAssetStatus", () => {
  it("est normal quand tout va bien", () => {
    expect(equipmentStatusToAssetStatus(status({}))).toBe("normal");
  });

  it("est inconnu sans point d'état ni mesure, jamais un autre état deviné", () => {
    expect(equipmentStatusToAssetStatus(status({ reason: "no_status_point" }))).toBe("unknown");
    expect(equipmentStatusToAssetStatus(status({ reason: "no_measurement" }))).toBe("unknown");
  });

  it("est hors ligne si la communication est coupée ou injoignable", () => {
    expect(equipmentStatusToAssetStatus(status({ communication_status: "offline" }))).toBe(
      "offline",
    );
    expect(equipmentStatusToAssetStatus(status({ communication_status: "unreachable" }))).toBe(
      "offline",
    );
  });

  it("est critique en cas de défaut, même si la communication fonctionne", () => {
    expect(equipmentStatusToAssetStatus(status({ operational_status: "fault" }))).toBe("critical");
  });

  it("la coupure de communication l'emporte sur le défaut opérationnel", () => {
    expect(
      equipmentStatusToAssetStatus(
        status({ operational_status: "fault", communication_status: "offline" }),
      ),
    ).toBe("offline");
  });

  it("est une donnée ancienne si la mesure n'est plus courante", () => {
    expect(equipmentStatusToAssetStatus(status({ current: false }))).toBe("stale");
  });

  it("reste inconnu si l'état opérationnel lui-même est inconnu", () => {
    expect(equipmentStatusToAssetStatus(status({ operational_status: "unknown" }))).toBe(
      "unknown",
    );
  });
});
