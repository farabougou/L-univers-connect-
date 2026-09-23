/// <reference types="node" />
// Aucun texte visible écrit en dur dans un écran : tout passe par le
// catalogue (ADR 013, point 9). Un texte en dur ne serait ni traduit ni relu.
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const screens = resolve(process.cwd(), "app");
const letters = "A-Za-zÀ-ÖØ-öø-ÿ";
// Texte entre deux balises ; les parenthèses, « = » et « ; » signalent du code
// TypeScript (types génériques), pas un texte affiché.
const jsxText = new RegExp(`>\\s*[^<>{}()=;\\n]*[${letters}][^<>{}()=;\\n]*\\s*<`, "g");
const textProps = new RegExp(`\\b(title|placeholder|accessibilityLabel)="[^"]*[${letters}]`, "g");

describe("écrans mobiles", () => {
  it.each(readdirSync(screens).filter((name) => name.endsWith(".tsx")))(
    "%s n'affiche aucun texte en dur",
    (name) => {
      const source = readFileSync(join(screens, name), "utf8");
      expect(source.match(jsxText) ?? []).toEqual([]);
      expect(source.match(textProps) ?? []).toEqual([]);
    },
  );
});
