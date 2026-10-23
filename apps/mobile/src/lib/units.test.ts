import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { unitSymbol } from "./units";

describe("unitSymbol", () => {
  it("affiche le symbole d'usage d'une unité connue", () => {
    expect(unitSymbol("Cel")).toBe("°C");
    expect(unitSymbol("kW.h")).toBe("kWh");
    expect(unitSymbol("m3/h")).toBe("m³/h");
    expect(unitSymbol("W")).toBe("W");
  });

  it("garde le code tel quel pour une unité inconnue : jamais un symbole inventé", () => {
    expect(unitSymbol("V")).toBe("V");
    expect(unitSymbol("Hz")).toBe("Hz");
    expect(unitSymbol("")).toBe("");
  });

  it("ne confond pas W et kW (la différence est un facteur 1000)", () => {
    expect(unitSymbol("W")).not.toBe(unitSymbol("kW"));
  });

  it("reprend exactement la table des unités de l'API (app/point_vocabulary.py)", () => {
    const source = readFileSync(
      resolve(process.cwd(), "../../services/api/app/point_vocabulary.py"),
      "utf8",
    );
    const block = source.slice(source.indexOf("UNITS:"), source.indexOf("LINEAR_UNIT_FACTORS"));
    const entries = [...block.matchAll(/"([^"]+)":\s*\("([^"]+)",\s*"[a-z_]+"\)/g)];

    expect(entries.length).toBeGreaterThanOrEqual(10);
    for (const [, code, symbol] of entries) {
      expect(unitSymbol(code), `unité ${code}`).toBe(symbol);
    }
  });
});
