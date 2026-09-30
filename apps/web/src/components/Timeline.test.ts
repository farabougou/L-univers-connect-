import { describe, expect, it } from "vitest";

import { timelineStatusLabel, type TimelineEntry } from "./Timeline";

function entry(overrides: Partial<TimelineEntry>): TimelineEntry {
  return {
    kind: "work_order",
    at: "2026-09-30T08:00:00Z",
    reference_id: "ref-1",
    title: null,
    field: null,
    status: null,
    changed_by: null,
    note: null,
    ...overrides,
  };
}

function t(key: string): string {
  return key;
}

describe("timelineStatusLabel", () => {
  it("renvoie null sans statut", () => {
    expect(timelineStatusLabel(entry({ status: null }), t)).toBeNull();
  });

  it("traduit un changement de statut d'ordre de travail avec son propre catalogue", () => {
    const label = timelineStatusLabel(
      entry({ kind: "work_order", field: "status", status: "in_progress" }),
      t,
    );
    expect(label).toBe("work_order.status.in_progress");
  });

  it("traduit un champ connu via le catalogue de la chronologie", () => {
    const label = timelineStatusLabel(
      entry({ kind: "alarm", field: "ack_state", status: "acknowledged" }),
      t,
    );
    expect(label).toBe("ack_state.acknowledged");
  });

  it("traduit un changement de cycle de vie via son propre catalogue", () => {
    const label = timelineStatusLabel(
      entry({ kind: "lifecycle", field: "lifecycle_state", status: "in_service" }),
      t,
    );
    expect(label).toBe("lifecycle.in_service");
  });

  it("renvoie la valeur brute pour un champ sans catalogue connu, jamais une traduction devinée", () => {
    const label = timelineStatusLabel(
      entry({ kind: "intervention", field: "unknown_field", status: "raw_value" }),
      t,
    );
    expect(label).toBe("raw_value");
  });
});
