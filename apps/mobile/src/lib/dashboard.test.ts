import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./equipmentLabels", () => ({
  loadEquipmentLabels: vi.fn().mockResolvedValue([
    { id: "l1", code: "cta-1", name: "CTA 1" },
    { id: "l2", code: "pac-1", name: "PAC 1" },
  ]),
}));

const { fetchDashboardCounts } = await import("./dashboard");

type Route = { total?: number; list?: unknown[] };

/** Serveur factice : répond selon le chemin, avec ou sans l'en-tête de total. */
function serverWith(routes: Record<string, Route>) {
  const calls: string[] = [];
  const fetchMock = vi.fn(async (url: string) => {
    calls.push(url);
    const parsed = new URL(url);
    const key = `${parsed.pathname}?${parsed.searchParams.get("handling_status") ?? ""}`;
    const route = routes[key] ?? routes[parsed.pathname] ?? { list: [] };
    const limited = parsed.searchParams.has("limit");
    const list = route.list ?? [];
    return {
      ok: true,
      headers: {
        get: (name: string) =>
          name === "X-Total-Count" && limited && route.total !== undefined
            ? String(route.total)
            : null,
      },
      json: async () => (limited ? list.slice(0, 1) : list),
    };
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("compteurs de l'accueil", () => {
  it("compte les alertes avec le total du serveur, sans télécharger les listes", async () => {
    const calls = serverWith({
      "/alarms?open": { total: 1200 },
      "/alarms?in_progress": { total: 30 },
      "/findings?open": { total: 7 },
      "/findings?in_progress": { total: 3 },
    });

    const counts = await fetchDashboardCounts("https://api.test", "token");

    expect(counts.openAlerts).toBe(1200 + 30 + 7 + 3);
    const signalCalls = calls.filter((url) => /\/(alarms|findings)\?/.test(url));
    expect(signalCalls).toHaveLength(4);
    expect(signalCalls.every((url) => url.includes("&limit=1"))).toBe(true);
  });

  it("compte les équipements dans la liste locale, sans appel réseau dédié", async () => {
    const calls = serverWith({});

    const counts = await fetchDashboardCounts("https://api.test", "token");

    expect(counts.equipment).toBe(2);
    expect(calls.some((url) => url.includes("/functional-locations"))).toBe(false);
  });

  it("si le serveur n'envoie pas le total, repasse par la liste complète plutôt qu'un faux nombre", async () => {
    const list = [{ id: "a" }, { id: "b" }, { id: "c" }];
    serverWith({
      "/alarms?open": { list },
      "/alarms?in_progress": { list: [] },
      "/findings?open": { list: [] },
      "/findings?in_progress": { list: [] },
    });

    const counts = await fetchDashboardCounts("https://api.test", "token");

    expect(counts.openAlerts).toBe(3);
  });
});
