import * as SQLite from "expo-sqlite";

import type { ClosureBody } from "./closure";
import { migrateLocalDatabase } from "./localSchema";

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
  /** Clôture structurée (JSON), ou null si l'intervention n'est pas clôturée. */
  closure: string | null;
  closure_sent: 0 | 1;
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
      // Le mode WAL autorise une lecture pendant qu'une écriture est en
      // cours (ex. countPendingInterventions() au démarrage, en même temps
      // que le rafraîchissement du cache des équipements dès que le réseau
      // revient) : sans lui, SQLite renvoie "database is locked" dès que
      // deux appels se chevauchent sur cette connexion.
      await db.execAsync("PRAGMA journal_mode = WAL;");
      await migrateLocalDatabase(db);
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
  closure: ClosureBody | null;
}): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    "INSERT INTO pending_interventions (id, intervention_type, summary, checklist, started_at, photo_path, functional_location_id, closure) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    input.id,
    input.interventionType,
    input.summary,
    JSON.stringify(input.checklist),
    input.startedAt,
    input.photoPath,
    input.functionalLocationId,
    input.closure ? JSON.stringify(input.closure) : null,
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

export async function markClosureSent(id: string): Promise<void> {
  const db = await getDb();
  await db.runAsync("UPDATE pending_interventions SET closure_sent = 1 WHERE id = ?", id);
}
