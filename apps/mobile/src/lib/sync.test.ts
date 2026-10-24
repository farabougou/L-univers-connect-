import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PendingIntervention } from "./db";

const db = vi.hoisted(() => ({
  listPendingInterventions: vi.fn(),
  deletePendingIntervention: vi.fn(),
  markInterventionCreated: vi.fn(),
  markPhotoUploaded: vi.fn(),
  markClosureSent: vi.fn(),
  markFgasSent: vi.fn(),
  getFeedStore: vi.fn(),
}));

vi.mock("./db", () => db);

const { syncPendingInterventions, pullFromServer } = await import("./sync");

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
    closure: null,
    closure_sent: 0,
    fgas: null,
    fgas_sent: 0,
    work_order_id: null,
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

  it("envoie l'identifiant local comme client_ref : un renvoi après une réponse perdue ne crée pas de doublon", async () => {
    db.listPendingInterventions.mockResolvedValue([baseRow({ id: "local-1727078400000-a1b2c3d4" })]);

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "server-1" }))
      .mockResolvedValueOnce(
        jsonResponse({ upload_url: "https://storage/upload", object_key: "key.jpg" }),
      )
      .mockResolvedValueOnce({ blob: async () => new Blob() })
      .mockResolvedValueOnce({ ok: true, status: 200 })
      .mockResolvedValueOnce(jsonResponse({ id: "photo-1" }));
    vi.stubGlobal("fetch", fetchMock);

    await syncPendingInterventions("https://api.test", "token");

    const bodyOf = (url: string) => {
      const call = fetchMock.mock.calls.find(([u]) => u === url);
      return JSON.parse((call?.[1] as RequestInit).body as string);
    };
    expect(bodyOf("https://api.test/interventions").client_ref).toBe(
      "local-1727078400000-a1b2c3d4",
    );
    expect(bodyOf("https://api.test/interventions/server-1/photos").client_ref).toBe(
      "local-1727078400000-a1b2c3d4",
    );
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

  it("envoie la clôture après la photo, puis supprime la ligne", async () => {
    const closure = JSON.stringify({ symptom_code: "no_heating", labor_minutes: 30 });
    db.listPendingInterventions.mockResolvedValue([
      baseRow({ server_id: "server-1", photo_uploaded: 1, closure }),
    ]);
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ id: "closure-1" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await syncPendingInterventions("https://api.test", "token");

    expect(result).toEqual({ synced: 1, failed: 0 });
    expect(fetchMock).toHaveBeenCalledWith("https://api.test/interventions/server-1/closure", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer token" },
      body: closure,
    });
    expect(db.markClosureSent).toHaveBeenCalledWith("local-1");
    expect(db.deletePendingIntervention).toHaveBeenCalledWith("local-1");
  });

  it("garde la ligne si la clôture est refusée, sans la perdre", async () => {
    db.listPendingInterventions.mockResolvedValue([
      baseRow({ server_id: "server-1", photo_uploaded: 1, closure: "{}" }),
    ]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(jsonResponse({}, false)));

    const result = await syncPendingInterventions("https://api.test", "token");

    expect(result).toEqual({ synced: 0, failed: 1 });
    expect(db.markClosureSent).not.toHaveBeenCalled();
    expect(db.deletePendingIntervention).not.toHaveBeenCalled();
  });

  it("ne renvoie pas une clôture déjà confirmée", async () => {
    db.listPendingInterventions.mockResolvedValue([
      baseRow({ server_id: "server-1", photo_uploaded: 1, closure: "{}", closure_sent: 1 }),
    ]);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await syncPendingInterventions("https://api.test", "token");

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("envoie la fiche F-Gas après la photo, puis supprime la ligne", async () => {
    const fgas = JSON.stringify({ refrigerant_name: "R410A", total_charge_kg: 12.5 });
    db.listPendingInterventions.mockResolvedValue([
      baseRow({ server_id: "server-1", photo_uploaded: 1, fgas }),
    ]);
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ id: "fgas-1" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await syncPendingInterventions("https://api.test", "token");

    expect(result).toEqual({ synced: 1, failed: 0 });
    expect(fetchMock).toHaveBeenCalledWith("https://api.test/interventions/server-1/fgas", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer token" },
      body: fgas,
    });
    expect(db.markFgasSent).toHaveBeenCalledWith("local-1");
    expect(db.deletePendingIntervention).toHaveBeenCalledWith("local-1");
  });

  it("garde la ligne si la fiche F-Gas est refusée, sans la perdre", async () => {
    db.listPendingInterventions.mockResolvedValue([
      baseRow({ server_id: "server-1", photo_uploaded: 1, fgas: "{}" }),
    ]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(jsonResponse({}, false)));

    const result = await syncPendingInterventions("https://api.test", "token");

    expect(result).toEqual({ synced: 0, failed: 1 });
    expect(db.markFgasSent).not.toHaveBeenCalled();
    expect(db.deletePendingIntervention).not.toHaveBeenCalled();
  });

  it("ne renvoie pas une fiche F-Gas déjà confirmée", async () => {
    db.listPendingInterventions.mockResolvedValue([
      baseRow({ server_id: "server-1", photo_uploaded: 1, fgas: "{}", fgas_sent: 1 }),
    ]);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await syncPendingInterventions("https://api.test", "token");

    expect(fetchMock).not.toHaveBeenCalled();
  });
});


describe("pullFromServer (flux incrémental)", () => {
  function fakeStore(initialCursor: string | null = null) {
    const state = { cursor: initialCursor, applied: [] as unknown[][], resets: 0 };
    db.getFeedStore.mockResolvedValue({
      getCursor: async () => state.cursor,
      applyPage: async (_feed: string, items: unknown[], cursor: string | null) => {
        state.applied.push(items);
        state.cursor = cursor;
      },
      resetCursor: async () => {
        state.cursor = null;
        state.resets += 1;
      },
    });
    return state;
  }

  it("demande une page courte avec le curseur enregistré et le jeton d'accès", async () => {
    fakeStore("c-42");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ items: [], next_cursor: "c-42", has_more: false }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await pullFromServer("https://api.test", "token", "interventions");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.test/sync/interventions?limit=100&after=c-42");
    expect(init.headers.Authorization).toBe("Bearer token");
  });

  it("sans point de reprise, ne demande pas de curseur (premier parcours)", async () => {
    fakeStore(null);
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ items: [], next_cursor: null, has_more: false }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await pullFromServer("https://api.test", "token", "functional_locations");

    expect(fetchMock.mock.calls[0][0]).toBe("https://api.test/sync/functional-locations?limit=100");
  });

  it("au premier parcours, l'historique est limité aux 30 derniers jours", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-31T12:00:00.000Z"));
    try {
      fakeStore(null);
      const fetchMock = vi.fn().mockResolvedValue(
        jsonResponse({ items: [], next_cursor: null, has_more: false }),
      );
      vi.stubGlobal("fetch", fetchMock);

      await pullFromServer("https://api.test", "token", "interventions");

      expect(fetchMock.mock.calls[0][0]).toBe(
        "https://api.test/sync/interventions?limit=100&since=2026-10-01T12%3A00%3A00.000Z",
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it("à la reprise, le point de reprise fait foi : aucune fenêtre n'est ajoutée", async () => {
    fakeStore("c-42");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ items: [], next_cursor: "c-42", has_more: false }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await pullFromServer("https://api.test", "token", "interventions");

    expect(fetchMock.mock.calls[0][0]).not.toContain("since=");
  });

  it("un curseur refusé (400 SYNC_CURSOR_INVALID) repart du début au lieu d'échouer", async () => {
    const state = fakeStore("c-perime");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ code: "SYNC_CURSOR_INVALID" }),
      })
      .mockResolvedValueOnce(
        jsonResponse({
          items: [{ id: "iv-1" }],
          next_cursor: "c-neuf",
          has_more: false,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await pullFromServer("https://api.test", "token", "interventions");

    expect(state.resets).toBe(1);
    // Le nouveau parcours est un premier parcours : sans curseur, avec la fenêtre récente.
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/sync\/interventions\?limit=100&since=/);
    expect(fetchMock.mock.calls[1][0]).not.toContain("after=");
    expect(result.complete).toBe(true);
    expect(state.cursor).toBe("c-neuf");
  });

  it("une autre erreur du serveur n'enregistre rien et ne touche pas au curseur", async () => {
    const state = fakeStore("c-1");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) }));

    await expect(pullFromServer("https://api.test", "token", "interventions")).rejects.toThrow("503");

    expect(state.applied).toEqual([]);
    expect(state.cursor).toBe("c-1");
    expect(state.resets).toBe(0);
  });

  it("abandonne une requête qui ne répond jamais, au lieu de bloquer toute la synchronisation", async () => {
    vi.useFakeTimers();
    try {
      fakeStore(null);
      vi.stubGlobal(
        "fetch",
        vi.fn(
          (_url: string, init: { signal: AbortSignal }) =>
            new Promise((_resolve, reject) => {
              init.signal.addEventListener("abort", () => reject(new Error("abandonnée")));
            }),
        ),
      );

      const pending = pullFromServer("https://api.test", "token", "interventions");
      const outcome = expect(pending).rejects.toThrow("abandonnée");
      await vi.advanceTimersByTimeAsync(20_000);

      await outcome;
    } finally {
      vi.useRealTimers();
    }
  });
});
