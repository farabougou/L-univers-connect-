// SQLite réel (Node) : le SQL de syncStore.ts et les migrations de localSchema.ts
// s'exécutent pour de vrai, avec de vraies transactions. Un simulacre ne
// prouverait ni l'atomicité d'une page, ni la reprise après une panne en plein
// enregistrement.
import { DatabaseSync } from "node:sqlite";
import { beforeEach, describe, expect, it } from "vitest";

import { LOCAL_MIGRATIONS } from "./localSchema";
import {
  CursorRejectedError,
  pullFeed,
  type FeedPage,
  type FeedStore,
} from "./syncFeed";
import {
  createFeedStore,
  getLastSyncedAt,
  listCachedInterventions,
  type FeedItem,
  type InterventionItem,
  type LocationItem,
  type SqlDatabase,
  type SqlValue,
} from "./syncStore";

type Harness = {
  raw: DatabaseSync;
  db: SqlDatabase;
  store: FeedStore<FeedItem>;
  /** Fait échouer l'instruction suivante qui contient ce texte (panne en plein enregistrement). */
  failNextStatementContaining(fragment: string): void;
};

function openHarness(): Harness {
  const raw = new DatabaseSync(":memory:");
  for (const migration of LOCAL_MIGRATIONS) raw.exec(migration);
  let failFragment: string | null = null;

  const run = (sql: string, params: SqlValue[]) => {
    if (failFragment && sql.includes(failFragment)) {
      failFragment = null;
      throw new Error("panne injectée");
    }
    return raw.prepare(sql).run(...params);
  };
  const db: SqlDatabase = {
    getFirstAsync: async <T,>(sql: string, ...params: SqlValue[]) => {
      const row = raw.prepare(sql).get(...params);
      return (row ? { ...row } : null) as T | null;
    },
    getAllAsync: async <T,>(sql: string, ...params: SqlValue[]) =>
      raw
        .prepare(sql)
        .all(...params)
        .map((row) => ({ ...row })) as T[],
    withExclusiveTransactionAsync: async (task) => {
      raw.exec("BEGIN EXCLUSIVE");
      try {
        await task({ runAsync: async (sql: string, ...params: SqlValue[]) => run(sql, params) });
        raw.exec("COMMIT");
      } catch (error) {
        raw.exec("ROLLBACK");
        throw error;
      }
    },
  };
  return {
    raw,
    db,
    store: createFeedStore(db),
    failNextStatementContaining: (fragment) => {
      failFragment = fragment;
    },
  };
}

function intervention(n: number, overrides: Partial<InterventionItem> = {}): InterventionItem {
  return {
    id: `iv-${String(n).padStart(4, "0")}`,
    intervention_type: "intervention",
    started_at: new Date(Date.UTC(2026, 9, 1, 8, 0, n)).toISOString(),
    ended_at: null,
    summary: `Résumé ${n}`,
    functional_location_id: "loc-1",
    work_order_id: null,
    ...overrides,
  };
}

function location(n: number, overrides: Partial<LocationItem> = {}): LocationItem {
  return { id: `loc-${n}`, code: `cta-${n}`, name: `CTA ${n}`, archived: false, ...overrides };
}

/** Serveur factice du protocole : des pages, un curseur, une suite annoncée. */
function serverFor<T>(all: T[], pageSize: number) {
  const calls: (string | null)[] = [];
  const fetchPage = async (after: string | null): Promise<FeedPage<T>> => {
    calls.push(after);
    const start = after ? Number(after.slice(1)) : 0;
    const items = all.slice(start, start + pageSize);
    const end = start + items.length;
    return { items, next_cursor: `c${end}`, has_more: end < all.length };
  };
  return { fetchPage, calls };
}

const count = (h: Harness, table: string) =>
  (h.raw.prepare(`SELECT count(*) AS n FROM ${table}`).get() as { n: number }).n;

let h: Harness;
beforeEach(() => {
  h = openHarness();
});

describe("parcours complet", () => {
  it("enregistre toutes les lignes, le curseur et la date de synchronisation", async () => {
    const items = Array.from({ length: 25 }, (_, i) => intervention(i));
    const server = serverFor(items, 10);

    const result = await pullFeed({
      feed: "interventions",
      store: h.store,
      fetchPage: server.fetchPage,
      now: () => "2026-10-21T12:00:00.000Z",
    });

    expect(result).toEqual({ pages: 3, items: 25, complete: true });
    expect(count(h, "interventions_cache")).toBe(25);
    expect(await h.store.getCursor("interventions")).toBe("c25");
    expect(await getLastSyncedAt(h.db, "interventions")).toBe("2026-10-21T12:00:00.000Z");
  });

  it("au parcours suivant, ne redemande que la suite (pas tout l'historique)", async () => {
    const items = Array.from({ length: 25 }, (_, i) => intervention(i));
    await pullFeed({ feed: "interventions", store: h.store, fetchPage: serverFor(items, 10).fetchPage });

    const second = serverFor(items, 10);
    await pullFeed({ feed: "interventions", store: h.store, fetchPage: second.fetchPage });

    expect(second.calls).toEqual(["c25"]);
  });
});

describe("reprise après interruption, sans perte ni doublon", () => {
  it("une panne EN PLEIN enregistrement de la page 2 annule toute la page 2, curseur compris", async () => {
    const items = Array.from({ length: 30 }, (_, i) => intervention(i));
    const server = serverFor(items, 10);
    // Les lignes de la page 2 sont écrites, puis la mise à jour du curseur échoue.
    let applied = 0;
    const store: FeedStore<FeedItem> = {
      ...h.store,
      applyPage: async (feed, page, cursor, at) => {
        applied += 1;
        if (applied === 2) h.failNextStatementContaining("INTO sync_state");
        return h.store.applyPage(feed, page, cursor, at);
      },
    };

    await expect(pullFeed({ feed: "interventions", store, fetchPage: server.fetchPage })).rejects.toThrow(
      "panne injectée",
    );

    // Page 1 entière et cohérente ; page 2 totalement absente (annulée), pas à moitié écrite.
    expect(count(h, "interventions_cache")).toBe(10);
    expect(await h.store.getCursor("interventions")).toBe("c10");
  });

  it("après cette panne, la reprise repart de la page 2 (pas du début) et finit sans doublon", async () => {
    const items = Array.from({ length: 30 }, (_, i) => intervention(i));
    let applied = 0;
    const flaky: FeedStore<FeedItem> = {
      ...h.store,
      applyPage: async (feed, page, cursor, at) => {
        applied += 1;
        if (applied === 2) h.failNextStatementContaining("INTO sync_state");
        return h.store.applyPage(feed, page, cursor, at);
      },
    };
    await pullFeed({ feed: "interventions", store: flaky, fetchPage: serverFor(items, 10).fetchPage }).catch(
      () => undefined,
    );

    const retry = serverFor(items, 10);
    const result = await pullFeed({ feed: "interventions", store: h.store, fetchPage: retry.fetchPage });

    expect(retry.calls[0]).toBe("c10");
    expect(result.complete).toBe(true);
    expect(count(h, "interventions_cache")).toBe(30);
    const ids = (h.raw.prepare("SELECT id FROM interventions_cache").all() as { id: string }[]).map(
      (row) => row.id,
    );
    expect(new Set(ids).size).toBe(30);
  });

  it("une coupure du réseau après 2 pages conserve ces 2 pages et reprend à la troisième", async () => {
    const items = Array.from({ length: 50 }, (_, i) => intervention(i));
    const server = serverFor(items, 10);
    let requests = 0;
    const cutting = async (after: string | null) => {
      requests += 1;
      if (requests === 3) throw new Error("réseau perdu");
      return server.fetchPage(after);
    };

    await expect(pullFeed({ feed: "interventions", store: h.store, fetchPage: cutting })).rejects.toThrow(
      "réseau perdu",
    );
    expect(count(h, "interventions_cache")).toBe(20);

    const resumed = serverFor(items, 10);
    await pullFeed({ feed: "interventions", store: h.store, fetchPage: resumed.fetchPage });

    expect(resumed.calls[0]).toBe("c20");
    expect(count(h, "interventions_cache")).toBe(50);
  });
});

describe("lignes renvoyées plusieurs fois (recouvrement du serveur, réponse perdue)", () => {
  it("la même page appliquée deux fois ne crée aucun doublon", async () => {
    const page = Array.from({ length: 10 }, (_, i) => intervention(i));

    await h.store.applyPage("interventions", page, "c10", "t1");
    await h.store.applyPage("interventions", page, "c10", "t2");

    expect(count(h, "interventions_cache")).toBe(10);
  });

  it("une ligne revue mais modifiée est mise à jour, pas ajoutée", async () => {
    await h.store.applyPage("interventions", [intervention(1)], "c1", "t1");

    await h.store.applyPage(
      "interventions",
      [intervention(1, { summary: "Corrigé", ended_at: "2026-10-01T09:00:00Z" })],
      "c1",
      "t2",
    );

    const row = h.raw.prepare("SELECT summary, ended_at FROM interventions_cache").get() as {
      summary: string;
      ended_at: string;
    };
    expect(count(h, "interventions_cache")).toBe(1);
    expect(row.summary).toBe("Corrigé");
    expect(row.ended_at).toBe("2026-10-01T09:00:00.000Z");
  });

  it("un recouvrement en fin de parcours ne duplique pas les lignes déjà reçues", async () => {
    const items = Array.from({ length: 12 }, (_, i) => intervention(i));
    await pullFeed({ feed: "interventions", store: h.store, fetchPage: serverFor(items, 50).fetchPage });

    // Le serveur renvoie les 5 dernières lignes déjà vues + 1 nouvelle.
    const overlapped = [...items.slice(-5), intervention(99)];
    await pullFeed({
      feed: "interventions",
      store: h.store,
      fetchPage: async () => ({ items: overlapped, next_cursor: "c13", has_more: false }),
    });

    expect(count(h, "interventions_cache")).toBe(13);
    expect(await h.store.getCursor("interventions")).toBe("c13");
  });
});

describe("équipements : modification et archivage", () => {
  it("une modification de nom est appliquée à la ligne existante", async () => {
    await h.store.applyPage("functional_locations", [location(1)], "c1", "t1");

    await h.store.applyPage("functional_locations", [location(1, { name: "CTA renommée" })], "c2", "t2");

    const rows = h.raw.prepare("SELECT code, name FROM functional_locations_cache").all();
    expect(rows).toHaveLength(1);
    expect({ ...rows[0] }).toEqual({ code: "cta-1", name: "CTA renommée" });
  });

  it("un équipement archivé sort de la liste locale, un équipement désarchivé y revient", async () => {
    await h.store.applyPage("functional_locations", [location(1), location(2)], "c2", "t1");

    await h.store.applyPage("functional_locations", [location(1, { archived: true })], "c3", "t2");
    expect(count(h, "functional_locations_cache")).toBe(1);

    await h.store.applyPage("functional_locations", [location(1, { archived: false })], "c4", "t3");
    expect(count(h, "functional_locations_cache")).toBe(2);
  });

  it("archiver un équipement jamais reçu ne produit aucune erreur", async () => {
    await expect(
      h.store.applyPage("functional_locations", [location(9, { archived: true })], "c1", "t1"),
    ).resolves.toBeUndefined();
    expect(count(h, "functional_locations_cache")).toBe(0);
  });

  it("les deux flux ont chacun leur point de reprise", async () => {
    await h.store.applyPage("interventions", [intervention(1)], "iv-c", "t1");
    await h.store.applyPage("functional_locations", [location(1)], "loc-c", "t2");

    expect(await h.store.getCursor("interventions")).toBe("iv-c");
    expect(await h.store.getCursor("functional_locations")).toBe("loc-c");
  });
});

describe("travail borné et protections", () => {
  it("s'arrête au plafond de pages et reprend ensuite, sans rien refaire", async () => {
    const items = Array.from({ length: 50 }, (_, i) => intervention(i));

    const first = await pullFeed({
      feed: "interventions",
      store: h.store,
      fetchPage: serverFor(items, 10).fetchPage,
      maxPages: 2,
    });
    const next = serverFor(items, 10);
    const second = await pullFeed({ feed: "interventions", store: h.store, fetchPage: next.fetchPage });

    expect(first).toEqual({ pages: 2, items: 20, complete: false });
    expect(next.calls[0]).toBe("c20");
    expect(second.complete).toBe(true);
    expect(count(h, "interventions_cache")).toBe(50);
  });

  it("refuse de boucler si le serveur annonce une suite sans faire avancer le curseur", async () => {
    const stuck = async (): Promise<FeedPage<FeedItem>> => ({
      items: [intervention(1)],
      next_cursor: "c1",
      has_more: true,
    });
    await h.store.applyPage("interventions", [], "c1", "t0");

    await expect(pullFeed({ feed: "interventions", store: h.store, fetchPage: stuck })).rejects.toThrow(
      "n'avance plus",
    );
  });

  it("un curseur refusé par le serveur déclenche un nouveau parcours complet, sans doublon", async () => {
    const items = Array.from({ length: 15 }, (_, i) => intervention(i));
    await pullFeed({ feed: "interventions", store: h.store, fetchPage: serverFor(items, 50).fetchPage });
    const server = serverFor(items, 50);
    let rejected = false;
    const fetchPage = async (after: string | null) => {
      if (after && !rejected) {
        rejected = true;
        throw new CursorRejectedError();
      }
      return server.fetchPage(after);
    };

    const result = await pullFeed({ feed: "interventions", store: h.store, fetchPage });

    expect(result.complete).toBe(true);
    expect(server.calls[0]).toBeNull();
    expect(count(h, "interventions_cache")).toBe(15);
  });
});

describe("lecture locale page par page", () => {
  it("rend les pages du plus récent au plus ancien, disjointes et complètes", async () => {
    await h.store.applyPage(
      "interventions",
      Array.from({ length: 25 }, (_, i) => intervention(i)),
      "c25",
      "t",
    );

    const first = await listCachedInterventions(h.db, { limit: 10 });
    const second = await listCachedInterventions(h.db, {
      limit: 10,
      before: { startedAt: first[9].started_at, id: first[9].id },
    });
    const third = await listCachedInterventions(h.db, {
      limit: 10,
      before: { startedAt: second[9].started_at, id: second[9].id },
    });

    const ids = [...first, ...second, ...third].map((row) => row.id);
    expect(ids).toHaveLength(25);
    expect(new Set(ids).size).toBe(25);
    expect(ids).toEqual([...ids].sort().reverse());
  });

  it("des lignes à date identique ne sont ni sautées ni répétées entre deux pages", async () => {
    const same = "2026-10-01T08:00:00Z";
    await h.store.applyPage(
      "interventions",
      Array.from({ length: 12 }, (_, i) => intervention(i, { started_at: same })),
      "c12",
      "t",
    );

    const first = await listCachedInterventions(h.db, { limit: 5 });
    const second = await listCachedInterventions(h.db, {
      limit: 5,
      before: { startedAt: first[4].started_at, id: first[4].id },
    });
    const third = await listCachedInterventions(h.db, {
      limit: 5,
      before: { startedAt: second[4].started_at, id: second[4].id },
    });

    expect([...first, ...second, ...third].map((row) => row.id).sort()).toEqual(
      Array.from({ length: 12 }, (_, i) => intervention(i).id).sort(),
    );
  });

  it("une ligne arrivée pendant le défilement ne décale pas la page suivante", async () => {
    await h.store.applyPage(
      "interventions",
      Array.from({ length: 20 }, (_, i) => intervention(i)),
      "c20",
      "t",
    );
    const first = await listCachedInterventions(h.db, { limit: 10 });

    // Une intervention plus récente arrive avant que l'on demande la page suivante.
    await h.store.applyPage("interventions", [intervention(500)], "c21", "t");
    const second = await listCachedInterventions(h.db, {
      limit: 10,
      before: { startedAt: first[9].started_at, id: first[9].id },
    });

    expect(second.map((row) => row.id)).toEqual(
      Array.from({ length: 10 }, (_, i) => intervention(9 - i).id),
    );
  });

  it("classe correctement des dates à décimales différentes (« …:00Z » et « …:00.5Z »)", async () => {
    await h.store.applyPage(
      "interventions",
      [
        intervention(1, { started_at: "2026-10-01T08:00:00Z" }),
        intervention(2, { started_at: "2026-10-01T08:00:00.5Z" }),
        intervention(3, { started_at: "2026-10-01T07:59:59.9Z" }),
      ],
      "c3",
      "t",
    );

    const rows = await listCachedInterventions(h.db, { limit: 10 });

    // Plus récent d'abord : 08:00:00.5, puis 08:00:00, puis 07:59:59.9.
    expect(rows.map((row) => row.id)).toEqual([intervention(2).id, intervention(1).id, intervention(3).id]);
  });
});

describe("migration 5 de la base locale", () => {
  it("conserve les interventions en attente d'un téléphone déjà installé", () => {
    const raw = new DatabaseSync(":memory:");
    for (const migration of LOCAL_MIGRATIONS.slice(0, 4)) raw.exec(migration);
    raw.exec(
      `INSERT INTO pending_interventions (id, intervention_type, checklist, started_at, photo_path)
       VALUES ('local-1', 'intervention', '{}', '2026-10-01T08:00:00Z', 'file:///p.jpg')`,
    );
    raw.exec(`INSERT INTO functional_locations_cache (id, code, name) VALUES ('l1', 'c', 'n')`);

    raw.exec(LOCAL_MIGRATIONS[4]);

    expect((raw.prepare("SELECT count(*) AS n FROM pending_interventions").get() as { n: number }).n).toBe(1);
    expect(
      (raw.prepare("SELECT count(*) AS n FROM functional_locations_cache").get() as { n: number }).n,
    ).toBe(1);
  });
});
