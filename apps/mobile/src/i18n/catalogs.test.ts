// Fichier copié depuis shared/i18n (ne pas modifier la copie).
// Qualité rédactionnelle vérifiée automatiquement (ADR 013, critères d'acceptation).
import { describe, expect, it } from "vitest";

import fr from "./fr/ui.json";
import en from "./en/ui.json";

type Node = string | { [key: string]: Node };

function entries(node: Node, prefix = ""): [string, string][] {
  if (typeof node === "string") return [[prefix, node]];
  return Object.entries(node).flatMap(([key, value]) =>
    entries(value, prefix ? `${prefix}.${key}` : key),
  );
}

const frEntries = new Map(entries(fr as Node));
const enEntries = new Map(entries(en as Node));
const placeholders = (text: string) => [...text.matchAll(/\{([a-z_]+)\}/g)].map((m) => m[1]).sort();

describe("catalogues d'interface", () => {
  it("ont exactement les mêmes clés en français et en anglais", () => {
    expect([...frEntries.keys()].sort()).toEqual([...enEntries.keys()].sort());
  });

  it("ont les mêmes paramètres dans les deux langues", () => {
    for (const [key, text] of frEntries) {
      expect(placeholders(text), key).toEqual(placeholders(enEntries.get(key) ?? ""));
    }
  });

  it("n'ont aucun texte vide ni double espace", () => {
    for (const [key, text] of [...frEntries, ...enEntries]) {
      expect(text.trim().length, key).toBeGreaterThan(0);
      expect(text.includes("  "), key).toBe(false);
    }
  });

  it("respectent la typographie française", () => {
    for (const [key, text] of frEntries) {
      expect(text.includes("'"), `${key} : apostrophe droite`).toBe(false);
      for (const mark of [":", ";", "?", "!"]) {
        expect(text.includes(` ${mark}`), `${key} : espace ordinaire avant ${mark}`).toBe(false);
      }
    }
  });

  it("vouvoient et n'emploient ni familiarité ni émoji", () => {
    const familiar = /\b(tu|toi|ton|ta|tes|te)\b|-toi\b|\b(ça|ok|oups)\b/i;
    const emoji = /\p{Extended_Pictographic}/u;
    for (const [key, text] of frEntries) {
      expect(familiar.test(text), `${key} : ${text}`).toBe(false);
      expect(emoji.test(text), `${key} : émoji`).toBe(false);
    }
    for (const [key, text] of enEntries) {
      expect(emoji.test(text), `${key} : emoji`).toBe(false);
    }
  });
});
