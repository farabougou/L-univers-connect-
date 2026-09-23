// Aucun texte visible écrit en dur dans une page : tout passe par le
// catalogue (ADR 013, point 9). Un texte en dur ne serait ni traduit ni relu.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const pages = resolve(process.cwd(), "src/app");
const letters = "A-Za-zÀ-ÖØ-öø-ÿ";
// Texte entre deux balises ; les parenthèses, « = » et « ; » signalent du code
// TypeScript (types génériques), pas un texte affiché.
const jsxText = new RegExp(`>\\s*[^<>{}()=;\\n]*[${letters}][^<>{}()=;\\n]*\\s*<`, "g");
const textProps = new RegExp(`\\b(title|placeholder|aria-label|alt)="[^"]*[${letters}]`, "g");

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return tsxFiles(path);
    return name.endsWith(".tsx") ? [path] : [];
  });
}

describe("pages web", () => {
  it.each(tsxFiles(pages))("%s n'affiche aucun texte en dur", (path) => {
    const source = readFileSync(path, "utf8");
    expect(source.match(jsxText) ?? []).toEqual([]);
    expect(source.match(textProps) ?? []).toEqual([]);
  });
});
