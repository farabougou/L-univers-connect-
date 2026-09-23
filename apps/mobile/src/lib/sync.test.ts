import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PendingIntervention } from "./db";

const db = vi.hoisted(() => ({
  listPendingInterventions: vi.fn(),
  deletePendingIntervention: vi.fn(),
  markInterventionCreated: vi.fn(),
  markPhotoUploaded: vi.fn(),
  replaceFunctionalLocationsCache: vi.fn(),
}));

vi.mock("./db", () => db);

const { syncPendingInterventions } = await import("./sync");

function baseRow(overrides: Partial<PendingIntervention> = {}): PendingIntervention {
  return {
    id: "local-1",
    intervention_type: "intervention",
    summary: "Résumé",
    checklist: "{}",
    started_at: "2026-09-23T08:00:00.000Z",
    photo_path: "file:///photo.jpg",
    functional_location_id: null,
    server_id: null,
    photo_uploaded: 0,
    ...overrides,
  };
}

function jsonResponse(body: unknown, ok = true) {
  return { ok, status: ok ? 200 : 500, json: async () => body };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("syncPendingInterventions", () => {
  it("crée l'intervention puis envoie sa photo, et supprime la ligne locale une fois synchronisée", async () => {
    db.listPendingInterventions.mockResolvedValue([baseRow()]);

    const fetchMock = vi
      .fn()
      // POST /interventions
      .mockResolvedValueOnce(jsonResponse({ id: "server-1" }))
      // POST /interventions/{id}/photos/upload-url
      .mockResolvedValueOnce(
        jsonResponse({ upload_url: "https://storage/upload", object_key: "key.jpg" }),
      )
      // GET file:///photo.jpg (lecture locale pour l'envoi)
      .mockResolvedValueOnce({ blob: async () => new Blob() })
      // PUT vers l'URL pré-signée
      .mockResolvedValueOnce({ ok: true, status: 200 })
      // POST /interventions/{id}/photos (confirmation)
      .mockResolvedValueOnce(jsonResponse({ id: "photo-1" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await syncPendingInterventions("https://api.test", "token");

    expect(result).toEqual({ synced: 1, failed: 0 });
    expect(db.markInterventionCreated).toHaveBeenCalledWith("local-1", "server-1");
    expect(db.markPhotoUploaded).toHaveBeenCalledWith("local-1");
    expect(db.deletePendingIntervention).toHaveBeenCalledWith("local-1");
  });

  it("ne recrée jamais l'intervention si server_id est déjà connu (reprise après coupure)", async () => {
    db.listPendingInterventions.mockResolvedValue([
      baseRow({ server_id: "server-1", photo_uploaded: 0 }),
    ]);

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ upload_url: "https://storage/upload", object_key: "key.jpg" }),
      )
      .mockResolvedValueOnce({ blob: async () => new Blob() })
      .mockResolvedValueOnce({ ok: true, status: 200 })
      .mockResolvedValueOnce(jsonResponse({ id: "photo-1" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await syncPendingInterventions("https://api.test", "token");

    expect(result).toEqual({ synced: 1, failed: 0 });
    // Un seul appel réseau pour la création aurait ciblé /interventions ;
    // ici aucun des appels ne doit être un POST /interventions (sans
    // suffixe), seulement les étapes liées à la photo.
    const postedToInterventionsRoot = fetchMock.mock.calls.some(
      ([url, options]) =>
        url === "https://api.test/interventions" && (options as RequestInit)?.method === "POST",
    );
    expect(postedToInterventionsRoot).toBe(false);
    expect(db.markInterventionCreated).not.toHaveBeenCalled();
  });

  it("ne supprime pas la ligne locale si l'envoi de la photo échoue : elle reste pour une reprise", async () => {
    db.listPendingInterventions.mockResolvedValue([baseRow()]);

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "server-1" }))
      .mockRejectedValueOnce(new Error("réseau coupé"));
    vi.stubGlobal("fetch", fetchMock);

    const result = await syncPendingInterventions("https://api.test", "token");

    expect(result).toEqual({ synced: 0, failed: 1 });
    // L'intervention a bien été créée côté serveur avant l'échec : la
    // reprise ne doit pas la recréer (voir le test précédent).
    expect(db.markInterventionCreated).toHaveBeenCalledWith("local-1", "server-1");
    expect(db.deletePendingIntervention).not.toHaveBeenCalled();
  });

  it("ne renvoie pas une photo déjà confirmée (photo_uploaded)", async () => {
    db.listPendingInterventions.mockResolvedValue([
      baseRow({ server_id: "server-1", photo_uploaded: 1 }),
    ]);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const result = await syncPendingInterventions("https://api.test", "token");

    expect(result).toEqual({ synced: 1, failed: 0 });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(db.deletePendingIntervention).toHaveBeenCalledWith("local-1");
  });
});
