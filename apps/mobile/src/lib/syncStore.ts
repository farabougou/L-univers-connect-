/**
 * Stockage local de la synchronisation incrémentale (voir syncFeed.ts).
 *
 * Écrit contre une interface minimale de base SQLite plutôt que contre
 * `expo-sqlite` : le même code SQL tourne sur le téléphone (expo-sqlite) et dans
 * les tests (SQLite réel de Node), ce qui prouve le SQL lui-même et non un
 * simulacre.
 */

import type { FeedName, FeedStore } from "./syncFeed";

export type SqlValue = string | number | null;

export type SqlTransaction = {
  runAsync(sql: string, ...params: SqlValue[]): Promise<unknown>;
};

export type SqlDatabase = {
  getFirstAsync<T>(sql: string, ...params: SqlValue[]): Promise<T | null>;
  getAllAsync<T>(sql: string, ...params: SqlValue[]): Promise<T[]>;
  withExclusiveTransactionAsync(task: (txn: SqlTransaction) => Promise<void>): Promise<void>;
};

export type InterventionItem = {
  id: string;
  intervention_type: string;
  started_at: string;
  ended_at: string | null;
  summary: string | null;
  functional_location_id: string | null;
  work_order_id: string | null;
};

export type LocationItem = {
  id: string;
  code: string;
  name: string;
  archived: boolean;
};

export type FeedItem = InterventionItem | LocationItem;

export type CachedIntervention = Omit<InterventionItem, "ended_at" | "work_order_id">;

/**
 * Dates normalisées à largeur fixe (millisecondes, UTC) à l'enregistrement : le
 * tri alphabétique de SQLite doit coïncider avec l'ordre chronologique. Les
 * dates du serveur n'ont pas toutes les mêmes décimales (« …:00Z » contre
 * « …:00.5Z »), et « Z » se classe après « . ».
 */
function normalizeDate(value: string): string {
  return new Date(value).toISOString();
}

async function applyIntervention(txn: SqlTransaction, item: InterventionItem): Promise<void> {
  await txn.runAsync(
    `INSERT INTO interventions_cache
       (id, intervention_type, started_at, ended_at, summary, functional_location_id, work_order_id)
     VALUES (?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET
       intervention_type = excluded.intervention_type,
       started_at = excluded.started_at,
       ended_at = excluded.ended_at,
       summary = excluded.summary,
       functional_location_id = excluded.functional_location_id,
       work_order_id = excluded.work_order_id`,
    item.id,
    item.intervention_type,
    normalizeDate(item.started_at),
    item.ended_at ? normalizeDate(item.ended_at) : null,
    item.summary,
    item.functional_location_id,
    item.work_order_id,
  );
}

async function applyLocation(txn: SqlTransaction, item: LocationItem): Promise<void> {
  if (item.archived) {
    // L'archivage est la seule « suppression » de la plateforme : l'équipement
    // sort de la liste locale, et y revient s'il est désarchivé.
    await txn.runAsync("DELETE FROM functional_locations_cache WHERE id = ?", item.id);
    return;
  }
  await txn.runAsync(
    `INSERT INTO functional_locations_cache (id, code, name) VALUES (?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET code = excluded.code, name = excluded.name`,
    item.id,
    item.code,
    item.name,
  );
}

export function createFeedStore(db: SqlDatabase): FeedStore<FeedItem> {
  return {
    async getCursor(feed: FeedName) {
      const row = await db.getFirstAsync<{ cursor: string | null }>(
        "SELECT cursor FROM sync_state WHERE feed = ?",
        feed,
      );
      return row?.cursor ?? null;
    },

    async applyPage(feed, items, cursor, syncedAt) {
      // Une seule transaction : les lignes et le curseur sont enregistrés ensemble
      // ou pas du tout (reprise après interruption sans perte).
      await db.withExclusiveTransactionAsync(async (txn) => {
        for (const item of items) {
          if (feed === "interventions") {
            await applyIntervention(txn, item as InterventionItem);
          } else {
            await applyLocation(txn, item as LocationItem);
          }
        }
        await txn.runAsync(
          `INSERT INTO sync_state (feed, cursor, synced_at) VALUES (?, ?, ?)
           ON CONFLICT(feed) DO UPDATE SET cursor = excluded.cursor, synced_at = excluded.synced_at`,
          feed,
          cursor,
          syncedAt,
        );
      });
    },

    async resetCursor(feed) {
      await db.withExclusiveTransactionAsync(async (txn) => {
        await txn.runAsync("DELETE FROM sync_state WHERE feed = ?", feed);
      });
    },
  };
}

/**
 * Page d'historique lue dans la base locale (jamais sur le réseau), du plus
 * récent au plus ancien. Pagination par clé (date, identifiant) et non par
 * décalage : une ligne qui arrive pendant le défilement ne décale pas la
 * page suivante, donc aucune ligne n'est sautée ni répétée.
 */
export async function listCachedInterventions(
  db: SqlDatabase,
  args: { limit: number; before?: { startedAt: string; id: string } },
): Promise<CachedIntervention[]> {
  const columns =
    "id, intervention_type, started_at, summary, functional_location_id FROM interventions_cache";
  if (args.before) {
    return db.getAllAsync<CachedIntervention>(
      `SELECT ${columns} WHERE (started_at, id) < (?, ?) ORDER BY started_at DESC, id DESC LIMIT ?`,
      args.before.startedAt,
      args.before.id,
      args.limit,
    );
  }
  return db.getAllAsync<CachedIntervention>(
    `SELECT ${columns} ORDER BY started_at DESC, id DESC LIMIT ?`,
    args.limit,
  );
}

export async function getLastSyncedAt(db: SqlDatabase, feed: FeedName): Promise<string | null> {
  const row = await db.getFirstAsync<{ synced_at: string }>(
    "SELECT synced_at FROM sync_state WHERE feed = ?",
    feed,
  );
  return row?.synced_at ?? null;
}
