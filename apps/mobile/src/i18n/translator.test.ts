// Fichier copié depuis shared/i18n (ne pas modifier la copie).
import { describe, expect, it } from "vitest";

import fr from "./fr/ui.json";
import en from "./en/ui.json";
import {
  type Catalog,
  createTranslator,
  formatDateTime,
  localeFromTag,
  negotiateLocale,
  pluralCategory,
} from "./translator";

const catalogs = { fr: fr as Catalog, en: en as Catalog };

describe("choix de la langue", () => {
  it.each([
    [null, "fr"],
    ["", "fr"],
    ["en", "en"],
    ["en-US", "en"],
    ["de-DE,en;q=0.5", "en"],
    ["de-DE", "fr"],
    ["fr;q=0.2,en;q=0.8", "en"],
    ["en;q=0,fr", "fr"],
    ["n'importe quoi;;;", "fr"],
  ])("Accept-Language %s → %s (même règle que l'API)", (header, expected) => {
    expect(negotiateLocale(header)).toBe(expected);
  });

  it("déduit la langue d'une étiquette de région", () => {
    expect(localeFromTag("fr-FR")).toBe("fr");
    expect(localeFromTag("en_GB")).toBe("en");
    expect(localeFromTag("de-DE")).toBe("fr");
  });
});

describe("traduction", () => {
  it("insère les paramètres et choisit le pluriel", () => {
    const t = createTranslator(catalogs, "fr").t;
    expect(t("mobile.home.pending", { count: 1 })).toBe("1 intervention en attente d’envoi");
    expect(t("mobile.home.pending", { count: 3 })).toBe("3 interventions en attente d’envoi");
    expect(createTranslator(catalogs, "en").t("mobile.home.pending", { count: 1 })).toBe(
      "1 intervention waiting to be sent",
    );
  });

  it("respecte les règles de pluriel du français (0 et 1 au singulier)", () => {
    expect(pluralCategory("fr", 0)).toBe("one");
    expect(pluralCategory("en", 0)).toBe("other");
  });

  it("laisse une clé absente visible plutôt que d'inventer un texte", () => {
    expect(createTranslator(catalogs, "fr").t("cle.inexistante")).toBe("cle.inexistante");
  });

  it("affiche l'heure dans le fuseau du site quand il est connu", () => {
    const instant = "2026-09-23T06:30:00Z";
    expect(formatDateTime("fr", instant, "Europe/Paris")).toContain("08:30");
    expect(formatDateTime("fr", instant, "America/New_York")).toContain("02:30");
  });
});
