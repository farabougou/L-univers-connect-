import { describe, expect, it } from "vitest";

import { aggregatePortfolio, emptySeverityCounts, mergeSeverityCounts } from "./portfolio";

const siteA = { id: "site-a", name: "Site A" };
const siteB = { id: "site-b", name: "Site B" };
const locA1 = { id: "loc-a1", site_id: "site-a" };
const locA2 = { id: "loc-a2", site_id: "site-a" };
const locB1 = { id: "loc-b1", site_id: "site-b" };

describe("aggregatePortfolio", () => {
  it("regroupe le nombre d'équipements par site", () => {
    const { bySite } = aggregatePortfolio(
      [siteA, siteB],
      [locA1, locA2, locB1],
      [],
      [],
      [],
      null,
    );

    expect(bySite.find((entry) => entry.site.id === "site-a")?.equipmentCount).toBe(2);
    expect(bySite.find((entry) => entry.site.id === "site-b")?.equipmentCount).toBe(1);
  });

  it("répartit les alarmes ouvertes par gravité et par site", () => {
    const { bySite } = aggregatePortfolio(
      [siteA, siteB],
      [locA1, locB1],
      [
        { functional_location_id: "loc-a1", severity: "critical" },
        { functional_location_id: "loc-a1", severity: "warning" },
        { functional_location_id: "loc-b1", severity: "major" },
      ],
      [],
      [],
      null,
    );

    const entryA = bySite.find((entry) => entry.site.id === "site-a")!;
    const entryB = bySite.find((entry) => entry.site.id === "site-b")!;
    expect(entryA.alarmSeverity).toEqual({ critical: 1, major: 0, warning: 1, info: 0 });
    expect(entryB.alarmSeverity).toEqual({ critical: 0, major: 1, warning: 0, info: 0 });
  });

  it("ignore un constat dont le sujet n'est pas un équipement connu", () => {
    // Un constat porté par un espace ou un point (subject_node_id ne
    // correspond à aucun functional_location) ne casse rien : il n'est
    // simplement pas encore rattaché à un site.
    const { bySite, totals } = aggregatePortfolio(
      [siteA],
      [locA1],
      [],
      [{ subject_node_id: "space-inconnu", severity: "critical" }],
      [],
      null,
    );

    expect(bySite[0].findingSeverity).toEqual(emptySeverityCounts());
    expect(totals.findingSeverity).toEqual(emptySeverityCounts());
  });

  it("ignore une gravité hors du référentiel plutôt que de planter", () => {
    const { bySite } = aggregatePortfolio(
      [siteA],
      [locA1],
      [{ functional_location_id: "loc-a1", severity: "inconnue" }],
      [],
      [],
      null,
    );

    expect(bySite[0].alarmSeverity).toEqual(emptySeverityCounts());
  });

  it("compte les ordres de travail ouverts, jamais les clos ou annulés", () => {
    const { bySite } = aggregatePortfolio(
      [siteA],
      [locA1],
      [],
      [],
      [
        { functional_location_id: "loc-a1", status: "open" },
        { functional_location_id: "loc-a1", status: "in_progress" },
        { functional_location_id: "loc-a1", status: "completed" },
        { functional_location_id: "loc-a1", status: "cancelled" },
      ],
      null,
    );

    expect(bySite[0].openWorkOrders).toBe(2);
  });

  it("répartit les passerelles Edge par état de communication, par site", () => {
    const { bySite } = aggregatePortfolio(
      [siteA, siteB],
      [],
      [],
      [],
      [],
      [
        { site_id: "site-a", communication_status: "online" },
        { site_id: "site-a", communication_status: "offline" },
        { site_id: "site-b", communication_status: "unknown" },
      ],
    );

    expect(bySite.find((entry) => entry.site.id === "site-a")?.devices).toEqual({
      online: 1,
      offline: 1,
      unknown: 0,
    });
    expect(bySite.find((entry) => entry.site.id === "site-b")?.devices).toEqual({
      online: 0,
      offline: 0,
      unknown: 1,
    });
  });

  it("ne fabrique jamais de colonne Edge quand l'appel a été refusé (rôle terrain)", () => {
    const { bySite } = aggregatePortfolio([siteA], [locA1], [], [], [], null);

    expect(bySite[0].devices).toBeNull();
  });

  it("agrège les totaux sur l'ensemble des sites", () => {
    const { totals } = aggregatePortfolio(
      [siteA, siteB],
      [locA1, locA2, locB1],
      [
        { functional_location_id: "loc-a1", severity: "critical" },
        { functional_location_id: "loc-b1", severity: "critical" },
      ],
      [],
      [{ functional_location_id: "loc-a1", status: "open" }],
      null,
    );

    expect(totals.equipmentCount).toBe(3);
    expect(totals.alarmSeverity.critical).toBe(2);
    expect(totals.openWorkOrders).toBe(1);
  });
});

describe("mergeSeverityCounts", () => {
  it("additionne chaque gravité indépendamment", () => {
    const merged = mergeSeverityCounts(
      { critical: 1, major: 2, warning: 0, info: 0 },
      { critical: 0, major: 1, warning: 3, info: 0 },
    );

    expect(merged).toEqual({ critical: 1, major: 3, warning: 3, info: 0 });
  });
});
