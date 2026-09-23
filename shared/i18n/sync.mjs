// Copie le traducteur et les catalogues partagés dans le web et le mobile
// (ADR 013, étape L4). Les outils de construction de chaque application ne
// lisent pas en dehors de leur dossier : on copie, et le test sync.test.ts de
// chaque application échoue si une copie diffère de l'original.
//
// Utilisation (depuis apps/web ou apps/mobile) : npm run i18n:sync
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const shared = dirname(fileURLToPath(import.meta.url));
const root = join(shared, "..", "..");

const common = [
  "translator.ts",
  "translator.test.ts",
  "catalogs.test.ts",
  "sync.test.ts",
  "fr/ui.json",
  "en/ui.json",
];
const targets = {
  // Le mobile affiche aussi les libellés de clôture hors ligne.
  "apps/mobile/src/i18n": [...common, "fr/closure.json", "en/closure.json"],
  // Le web affiche aussi les erreurs de l'API à partir de leur code.
  "apps/web/src/i18n": [...common, "fr/errors.json", "en/errors.json"],
};

for (const [target, files] of Object.entries(targets)) {
  for (const file of files) {
    const destination = join(root, target, file);
    mkdirSync(dirname(destination), { recursive: true });
    copyFileSync(join(shared, file), destination);
  }
  console.log(`${target} : ${files.length} fichiers copiés`);
}
