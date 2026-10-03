// Fichier copié depuis shared/i18n (ne pas modifier la copie).
/// <reference types="node" />
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Les tests s'exécutent depuis le dossier de l'application (apps/web ou apps/mobile).
const copyDir = resolve(process.cwd(), "src/i18n");
const sharedDir = resolve(process.cwd(), "../../shared/i18n");

function files(dir: string, prefix = ""): string[] {
  return readdirSync(dir).flatMap((name: string) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path, `${prefix}${name}/`) : [`${prefix}${name}`];
  });
}

describe("copies de shared/i18n", () => {
  it.each(files(copyDir))("%s est identique à l'original", (file) => {
    expect(readFileSync(join(copyDir, file), "utf8")).toBe(
      readFileSync(join(sharedDir, file), "utf8"),
    );
  });
});
