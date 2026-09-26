/**
 * Schéma de la base locale du téléphone, versionné (PRAGMA user_version).
 *
 * Une application installée garde sa base d'une version à l'autre : on ne
 * recrée jamais les tables, on applique seulement les étapes manquantes, dans
 * l'ordre, et chacune dans une transaction. Les interventions en attente
 * d'envoi survivent donc à une mise à jour de l'application (ADR 010).
 * Une étape publiée ne se modifie plus : on en ajoute une nouvelle.
 */
export const LOCAL_MIGRATIONS: string[] = [
  // 1 — tables d'origine (IF NOT EXISTS : déjà présentes sur les téléphones
  // installés avant le versionnement).
  `CREATE TABLE IF NOT EXISTS pending_interventions (
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
   );`,
  // 2 — clôture structurée saisie hors ligne, envoyée après la photo.
  `ALTER TABLE pending_interventions ADD COLUMN closure TEXT;
   ALTER TABLE pending_interventions ADD COLUMN closure_sent INTEGER NOT NULL DEFAULT 0;`,
];

export type LocalDatabase = {
  getFirstAsync<T>(sql: string): Promise<T | null>;
  withExclusiveTransactionAsync(
    task: (txn: { execAsync(sql: string): Promise<void> }) => Promise<void>,
  ): Promise<void>;
};

export async function migrateLocalDatabase(db: LocalDatabase): Promise<number> {
  const row = await db.getFirstAsync<{ user_version: number }>("PRAGMA user_version");
  const current = row?.user_version ?? 0;
  for (let version = current + 1; version <= LOCAL_MIGRATIONS.length; version += 1) {
    await db.withExclusiveTransactionAsync(async (txn) => {
      await txn.execAsync(LOCAL_MIGRATIONS[version - 1]);
      await txn.execAsync(`PRAGMA user_version = ${version}`);
    });
  }
  return LOCAL_MIGRATIONS.length;
}
