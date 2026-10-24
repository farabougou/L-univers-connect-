// Vérifie qu'un compte peut se connecter à la console web du staging et y administrer, sans jamais
// afficher le mot de passe.
//
// Conçu pour être lancé par `services/api/scripts/staging_owner_account.py` après `--` : l'identifiant
// et le mot de passe arrivent par l'environnement (STAGING_OWNER_USERNAME, STAGING_OWNER_PASSWORD),
// jamais par les arguments. Argument : l'adresse de la console web.
//
//   node infra/staging-web-login-check.mjs https://CONSOLE_WEB_STAGING
//
// Playwright n'est pas une dépendance du dépôt : il est cherché dans le dossier donné par
// PLAYWRIGHT_NODE_PATH (celui qui contient node_modules/playwright), sinon dans le dossier courant.
// PLAYWRIGHT_CHROMIUM_PATH désigne un navigateur précis si celui par défaut ne convient pas.
//
// Ce qui est contrôlé : la connexion par Keycloak aboutit, l'accueil affiche « Session de
// <identifiant> », et l'écran Registre (réservé aux responsables et administrateurs) s'ouvre.
// Code de sortie : 0 tout est bon, 1 un contrôle a échoué, 2 mauvaise utilisation.
import { createRequire } from "node:module";

const base = process.argv[2]?.replace(/\/$/, "");
const username = process.env.STAGING_OWNER_USERNAME;
const password = process.env.STAGING_OWNER_PASSWORD;
if (!base || !username || !password) {
  console.error("Usage : STAGING_OWNER_USERNAME et STAGING_OWNER_PASSWORD dans l'environnement, adresse en argument.");
  process.exit(2);
}

const require = createRequire(`${process.env.PLAYWRIGHT_NODE_PATH ?? process.cwd()}/`);
const { chromium } = require("playwright");

const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined,
  args: ["--no-sandbox"],
});
let failed = false;
const check = (label, ok) => {
  console.log(`  ${label} : ${ok ? "oui" : "NON"}`);
  if (!ok) failed = true;
};

try {
  const page = await (await browser.newContext({ locale: "fr-FR" })).newPage();
  await page.goto(`${base}/`, { waitUntil: "networkidle", timeout: 90000 });
  await page.locator("a, button").filter({ hasText: /connect|sign in|log in/i }).first().click();
  await page.waitForLoadState("networkidle");
  await page.fill("#username", username);
  await page.fill("#password", password);
  await Promise.all([page.waitForNavigation({ timeout: 90000 }), page.click("#kc-login")]);
  await page.waitForLoadState("networkidle");

  // Une page de Keycloak encore affichée (mauvais mot de passe, changement imposé...) n'est pas
  // une connexion à la console.
  const onConsole = page.url().startsWith(base);
  check("connexion à la console web", onConsole);
  if (onConsole) {
    const home = await page.innerText("main");
    check("accueil : « Session de <identifiant> »", home.includes(`Session de ${username}`));
    await page.goto(`${base}/registre`, { waitUntil: "networkidle", timeout: 90000 });
    const registry = await page.innerText("main");
    check("écran Registre ouvert (droits d'administration)", !registry.includes("réservé aux responsables"));
  }
} catch (error) {
  // Le nom de l'erreur seulement : son message peut citer une adresse ou un champ rempli.
  console.log(`  erreur pendant le contrôle : ${error?.name ?? "inconnue"}`);
  failed = true;
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
