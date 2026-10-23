import { describe, expect, it } from "vitest";

import { indexLocations, isArchivedLocation } from "./locations";

const active = { id: "actif", code: "CTA-01", archived_at: null };
const archived = { id: "archive", code: "GF-02", archived_at: "2026-10-23T21:00:00+00:00" };

describe("indexLocations", () => {
  it("retrouve un équipement archivé par son identifiant (jamais un « — » muet)", () => {
    const { byId } = indexLocations([active, archived]);

    expect(byId.get("archive")).toBe(archived);
    expect(byId.get("actif")).toBe(active);
  });

  it("ne garde dans `active` que les équipements non archivés", () => {
    const { active: kept } = indexLocations([active, archived]);

    expect(kept).toEqual([active]);
  });

  it("traite l'absence de date d'archivage comme un équipement actif", () => {
    const withoutField = { id: "sans-champ", code: "POM-01" };

    expect(indexLocations([withoutField]).active).toEqual([withoutField]);
    expect(isArchivedLocation(withoutField)).toBe(false);
  });

  it("renvoie un index vide pour une liste vide", () => {
    const { active: kept, byId } = indexLocations([]);

    expect(kept).toEqual([]);
    expect(byId.size).toBe(0);
  });
});
