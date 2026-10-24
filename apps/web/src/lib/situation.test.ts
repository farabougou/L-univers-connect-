import { describe, expect, it } from "vitest";

import { type AssetStatusDistribution } from "./health";
import { type SeverityCounts } from "./portfolio";
import { healthSegments, highestSeverity, severityAccent, severityTotal } from "./situation";

function counts(overrides: Partial<SeverityCounts>): SeverityCounts {
  return { critical: 0, major: 0, warning: 0, info: 0, ...overrides };
}

function distribution(overrides: Partial<Record<keyof AssetStatusDistribution, number>>) {
  const result: AssetStatusDistribution = {
    normal: [],
    attention: [],
    critical: [],
    offline: [],
    stale: [],
    unknown: [],
    maintenance: [],
  };
  for (const [status, count] of Object.entries(overrides)) {
    result[status as keyof AssetStatusDistribution] = Array.from(
      { length: count },
      (_, index) => `${status}-${index}`,
    );
  }
  return result;
}

describe("highestSeverity", () => {
  it("renvoie null quand rien n'est ouvert", () => {
    expect(highestSeverity(counts({}))).toBeNull();
  });

  it("renvoie la gravité la plus élevée présente, même minoritaire", () => {
    expect(highestSeverity(counts({ critical: 1, warning: 9, info: 4 }))).toBe("critical");
    expect(highestSeverity(counts({ major: 2, warning: 5 }))).toBe("major");
    expect(highestSeverity(counts({ warning: 1, info: 3 }))).toBe("warning");
    expect(highestSeverity(counts({ info: 7 }))).toBe("info");
  });
});

describe("healthSegments", () => {
  it("ne garde que les états présents, dans l'ordre de la directive", () => {
    const segments = healthSegments(distribution({ critical: 2, normal: 9, offline: 1 }));

    expect(segments.map((segment) => segment.status)).toEqual(["normal", "critical", "offline"]);
    expect(segments.map((segment) => segment.count)).toEqual([9, 2, 1]);
  });

  it("calcule la part de chaque état sur le total des équipements classés", () => {
    const segments = healthSegments(distribution({ normal: 3, critical: 1 }));

    expect(segments.map((segment) => segment.percent)).toEqual([75, 25]);
  });

  it("la somme des parts fait 100 quand il y a des équipements", () => {
    const segments = healthSegments(distribution({ normal: 9, critical: 2, offline: 1, stale: 1, unknown: 1 }));
    const total = segments.reduce((sum, segment) => sum + segment.percent, 0);

    expect(total).toBeCloseTo(100, 10);
  });

  it("renvoie une liste vide quand aucun équipement n'est classé (jamais une barre inventée)", () => {
    expect(healthSegments(distribution({}))).toEqual([]);
  });

  it("garde un état présent même très minoritaire (un seul équipement sur mille)", () => {
    const segments = healthSegments(distribution({ normal: 999, critical: 1 }));

    expect(segments.find((segment) => segment.status === "critical")?.count).toBe(1);
  });
});

describe("severityTotal", () => {
  it("additionne toutes les gravités", () => {
    expect(severityTotal(counts({ critical: 2, major: 1, warning: 2, info: 1 }))).toBe(6);
    expect(severityTotal(counts({}))).toBe(0);
  });
});

describe("severityAccent", () => {
  it("prend la couleur de la gravité la plus élevée ouverte", () => {
    expect(severityAccent(counts({ critical: 1 }), "neutre")).toBe("#dc2626");
    expect(severityAccent(counts({ major: 1, warning: 4 }), "neutre")).toBe("#ea580c");
  });

  it("garde la couleur neutre quand rien n'est ouvert (jamais un vert rassurant)", () => {
    expect(severityAccent(counts({}), "neutre")).toBe("neutre");
  });
});

