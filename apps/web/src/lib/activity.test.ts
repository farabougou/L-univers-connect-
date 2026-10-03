import { describe, expect, it } from "vitest";

import {
  filterActivityEntries,
  toActivityFeedEntries,
  type ActivityFeedEntry,
  type PortfolioTimelineEntry,
} from "./activity";

function entry(overrides: Partial<PortfolioTimelineEntry>): PortfolioTimelineEntry {
  return {
    kind: "alarm",
    at: "2026-09-30T08:00:00Z",
    functional_location_id: "loc-1",
    reference_id: "ref-1",
    title: "Défaut haute pression",
    ...overrides,
  };
}

describe("toActivityFeedEntries", () => {
  const locationById = new Map([["loc-1", { code: "CTA-01", name: "CTA toiture" }]]);

  it("résout le lien vers l'équipement quand il existe dans le portefeuille", () => {
    const [result] = toActivityFeedEntries([entry({})], "fr", locationById);
    expect(result.locationId).toBe("loc-1");
    expect(result.locationLabel).toBe("CTA-01 — CTA toiture");
  });

  it("ne fabrique jamais de lien quand l'équipement est introuvable", () => {
    const [result] = toActivityFeedEntries(
      [entry({ functional_location_id: "loc-inconnu" })],
      "fr",
      locationById,
    );
    expect(result.locationId).toBeNull();
    expect(result.locationLabel).toBeNull();
  });

  it("ne fabrique jamais de lien quand l'entrée n'a aucun équipement", () => {
    const [result] = toActivityFeedEntries(
      [entry({ functional_location_id: null })],
      "fr",
      locationById,
    );
    expect(result.locationId).toBeNull();
  });

  it("garde le titre et le type tels quels", () => {
    const [result] = toActivityFeedEntries(
      [entry({ kind: "work_order", title: "Remplacer le filtre" })],
      "fr",
      locationById,
    );
    expect(result.kind).toBe("work_order");
    expect(result.title).toBe("Remplacer le filtre");
  });

  it("produit une clé unique par entrée", () => {
    const results = toActivityFeedEntries(
      [entry({ reference_id: "a" }), entry({ reference_id: "b" })],
      "fr",
      locationById,
    );
    expect(new Set(results.map((r) => r.key)).size).toBe(2);
  });
});

describe("filterActivityEntries", () => {
  function feedEntry(overrides: Partial<ActivityFeedEntry>): ActivityFeedEntry {
    return {
      kind: "alarm",
      key: "alarm-1",
      formattedAt: "30/09/2026 08:00",
      locationId: null,
      locationLabel: null,
      title: null,
      ...overrides,
    };
  }

  it("ne garde que les catégories demandées", () => {
    const entries = [
      feedEntry({ kind: "alarm", key: "a" }),
      feedEntry({ kind: "work_order", key: "b" }),
      feedEntry({ kind: "intervention", key: "c" }),
    ];
    const result = filterActivityEntries(entries, new Set(["alarm", "intervention"]));
    expect(result.map((e) => e.key)).toEqual(["a", "c"]);
  });

  it("renvoie une liste vide quand aucune catégorie n'est sélectionnée", () => {
    const entries = [feedEntry({ kind: "alarm" })];
    expect(filterActivityEntries(entries, new Set())).toEqual([]);
  });
});
