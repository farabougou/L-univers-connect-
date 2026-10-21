import { describe, expect, it } from "vitest";

import { LOCAL_MIGRATIONS, migrateLocalDatabase } from "./localSchema";

function fakeDb(userVersion: number) {
  const executed: string[] = [];
  return {
    executed,
    getFirstAsync: async <T,>() => ({ user_version: userVersion }) as T,
    withExclusiveTransactionAsync: async (
      task: (txn: { execAsync(sql: string): Promise<void> }) => Promise<void>,
    ) => {
      await task({ execAsync: async (sql: string) => void executed.push(sql) });
    },
  };
}

describe("base locale versionnée", () => {
  it("un téléphone neuf reçoit toutes les étapes, dans l'ordre", async () => {
    const db = fakeDb(0);
    await migrateLocalDatabase(db);
    expect(db.executed.filter((sql) => sql.startsWith("PRAGMA"))).toEqual(
      LOCAL_MIGRATIONS.map((_, index) => `PRAGMA user_version = ${index + 1}`),
    );
  });

  it("un téléphone déjà installé ne reçoit que les étapes manquantes", async () => {
    const db = fakeDb(1);
    await migrateLocalDatabase(db);
    // Toutes les étapes après la première, dans l'ordre, chacune suivie de son numéro de version.
    expect(db.executed).toEqual(
      LOCAL_MIGRATIONS.slice(1).flatMap((step, index) => [step, `PRAGMA user_version = ${index + 2}`]),
    );
  });

  it("un téléphone à jour ne change rien", async () => {
    const db = fakeDb(LOCAL_MIGRATIONS.length);
    await migrateLocalDatabase(db);
    expect(db.executed).toEqual([]);
  });

  it("aucune étape ne supprime de données", () => {
    for (const step of LOCAL_MIGRATIONS) {
      expect(step).not.toMatch(/\b(DROP|DELETE)\b/i);
    }
  });
});
