import { beforeEach, describe, expect, it, vi } from "vitest";

const db = vi.hoisted(() => ({ listCachedFunctionalLocations: vi.fn() }));
vi.mock("./db", () => db);

const { loadEquipmentLabels } = await import("./equipmentLabels");

beforeEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("loadEquipmentLabels", () => {
  it("lit la liste locale sans aucun appel réseau quand elle existe", async () => {
    db.listCachedFunctionalLocations.mockResolvedValue([{ id: "l1", code: "cta-1", name: "CTA 1" }]);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const labels = await loadEquipmentLabels("https://api.test", "token");

    expect(labels).toEqual([{ id: "l1", code: "cta-1", name: "CTA 1" }]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("au tout premier lancement (liste locale vide), interroge le serveur", async () => {
    db.listCachedFunctionalLocations.mockResolvedValue([]);
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: "l2", code: "pac-1", name: "PAC 1" }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const labels = await loadEquipmentLabels("https://api.test", "token");

    expect(labels).toEqual([{ id: "l2", code: "pac-1", name: "PAC 1" }]);
    expect(fetchMock.mock.calls[0][0]).toBe("https://api.test/functional-locations");
  });

  it("sans liste locale ni réseau, renvoie une liste vide au lieu d'échouer", async () => {
    db.listCachedFunctionalLocations.mockResolvedValue([]);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("hors ligne")));

    await expect(loadEquipmentLabels("https://api.test", "token")).resolves.toEqual([]);
  });

  it("une base locale illisible ne bloque pas l'écran : repli sur le serveur", async () => {
    db.listCachedFunctionalLocations.mockRejectedValue(new Error("base verrouillée"));
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => [{ id: "l3", code: "c", name: "n" }] }),
    );

    await expect(loadEquipmentLabels("https://api.test", "token")).resolves.toHaveLength(1);
  });
});
