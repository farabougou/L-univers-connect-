import * as SQLite from "expo-sqlite";

/**
 * Stockage local des interventions créées hors ligne (voir ADR 010). Une
 * ligne disparaît de cette table dès qu'elle est entièrement synchronisée
 * avec l'API : ce n'est qu'une file d'attente, jamais un historique.
 */
export type PendingIntervention = {
  id: string;
  intervention_type: string;
  summary: string | null;
  checklist: string;
  started_at: string;
  photo_path: string;
  functional_location_id: string | null;
  server_id: string | null;
  photo_uploaded: 0 | 1;
};

export type CachedFunctionalLocation = {
  id: string;
  code: string;
  name: string;
};

let dbPromise: Promise<SQLite.SQLiteDatabase> | null = null;

function getDb(): Promise<SQLite.SQLiteDatabase> {
  if (!dbPromise) {
    dbPromise = SQLite.openDatabaseAsync("paios.db").then(async (db) => {
      await db.execAsync(`
        CREATE TABLE IF NOT EXISTS pending_interventions (
          id TEXT PRIMARY KEY,
          intervention_type TEXT NOT NULL,
          summary TEXT,
          checklist TEXT NOT NULL,
          started_at TEXT NOT NULL,
          photo_path TEXT NOT NULL,
          functional_location_id TEXT,
          server_id TEXT,
          photo_uploaded INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS functional_locations_cache (
          id TEXT PRIMARY KEY,
          code TEXT NOT NULL,
          name TEXT NOT NULL
        );
      `);
      return db;
    });
  }
  return dbPromise;
}

export async function insertPendingIntervention(input: {
  id: string;
  interventionType: string;
  summary: string | null;
  checklist: Record<string, boolean>;
  startedAt: string;
  photoPath: string;
  functionalLocationId: string | null;
}): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    "INSERT INTO pending_interventions (id, intervention_type, summary, checklist, started_at, photo_path, functional_location_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
    input.id,
    input.interventionType,
    input.summary,
    JSON.stringify(input.checklist),
    input.startedAt,
    input.photoPath,
    input.functionalLocationId,
  );
}

export async function replaceFunctionalLocationsCache(
  locations: CachedFunctionalLocation[],
): Promise<void> {
  const db = await getDb();
  await db.withExclusiveTransactionAsync(async (txn) => {
    await txn.execAsync("DELETE FROM functional_locations_cache");
    for (const location of locations) {
      await txn.runAsync(
        "INSERT INTO functional_locations_cache (id, code, name) VALUES (?, ?, ?)",
        location.id,
        location.code,
        location.name,
      );
    }
  });
}

export async function listCachedFunctionalLocations(): Promise<CachedFunctionalLocation[]> {
  const db = await getDb();
  return db.getAllAsync<CachedFunctionalLocation>(
    "SELECT id, code, name FROM functional_locations_cache ORDER BY code",
  );
}

export async function listPendingInterventions(): Promise<PendingIntervention[]> {
  const db = await getDb();
  return db.getAllAsync<PendingIntervention>("SELECT * FROM pending_interventions");
}

export async function countPendingInterventions(): Promise<number> {
  const db = await getDb();
  const row = await db.getFirstAsync<{ count: number }>(
    "SELECT COUNT(*) as count FROM pending_interventions",
  );
  return row?.count ?? 0;
}

export async function markInterventionCreated(id: string, serverId: string): Promise<void> {
  const db = await getDb();
  await db.runAsync("UPDATE pending_interventions SET server_id = ? WHERE id = ?", serverId, id);
}

export async function markPhotoUploaded(id: string): Promise<void> {
  const db = await getDb();
  await db.runAsync("UPDATE pending_interventions SET photo_uploaded = 1 WHERE id = ?", id);
}

export async function deletePendingIntervention(id: string): Promise<void> {
  const db = await getDb();
  await db.runAsync("DELETE FROM pending_interventions WHERE id = ?", id);
}
